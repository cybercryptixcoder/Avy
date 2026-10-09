"""
Avy's voice. app.py starts this automatically when the voice packages are
installed (see requirements-voice.txt). Text chat works without it.

    ears   Silero VAD notices you talking, Smart Turn decides you're done,
           faster-whisper writes down what you said. All on this computer.
    brain  DeepSeek, same model as the text chat.
    mouth  Kokoro 82M turns the reply into speech. Also on this computer.

Pipecat wires them together and handles interruptions: start talking while
Avy is speaking and she stops.
"""

import asyncio
import json
import os
import threading
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    InputAudioRawFrame,
    InterruptionFrame,
    LLMMessagesAppendFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.services.deepseek.llm import DeepSeekLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner
import pipecat.services.kokoro.tts as kokoro_tts
import pipecat.services.whisper.stt as whisper_stt


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

PORT = 8001
WHISPER_MODEL = "distil-small.en"    # English only. Each transcription costs about the same however short
                                     # the clip, and adds that much delay to every reply. Slower but more
                                     # accurate: "distil-medium.en" (~2.4x), "distil-large-v3" (~4x).
KOKORO_VOICE = "af_bella"            # try "af_heart", "am_michael", "bf_emma"...
MIC_RATE = 16000                     # what the page sends: 16-bit mono PCM
SPEAKER_RATE = 24000                 # what the page plays: Kokoro's native rate

status = {"ready": False, "error": None}   # app.py shows this on the page


# ---------------------------------------------------------------------------
# 2. Loading the local models
#    Each service loads its model when it's created, which takes a second or
#    two and blocks. So we create them in a background thread, never inside
#    the async server loop. The first run also downloads the models (~1 GB).
#
#    Pipecat builds a fresh model for every new service, and the old ones are
#    never freed: each call to [ talk ] would add ~0.6 GB of memory. lru_cache
#    makes "build the model" return the same model every time instead.
# ---------------------------------------------------------------------------

whisper_stt.WhisperModel = lru_cache(maxsize=None)(whisper_stt.WhisperModel)
kokoro_tts.Kokoro = lru_cache(maxsize=None)(kokoro_tts.Kokoro)


def make_ears_and_mouth():
    stt = WhisperSTTService(
        settings=WhisperSTTService.Settings(model=WHISPER_MODEL),
        compute_type="int8",       # fast on a laptop CPU
        # The longest we'll wait for a transcript after you stop talking. A transcript
        # ends your turn the moment it arrives, so this adds no delay; it just stops a
        # slow transcription from being split off into a turn of its own.
        ttfs_p99_latency=2.0,
    )
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice=KOKORO_VOICE))
    return stt, tts


def warm_up():
    """Download and load the models once at startup, so the first call is quick."""
    try:
        logger.info("Voice: loading models (the first run downloads about 1 GB)...")
        make_ears_and_mouth()
        SileroVADAnalyzer()
        status["ready"] = True
        logger.info("Voice: ready.")
    except Exception as e:
        status["error"] = f"Voice failed to load: {e}"
        logger.exception("Voice: failed to load models")


# ---------------------------------------------------------------------------
# 3. The wire format between the page and the pipeline
#    Binary messages are raw audio (16-bit PCM, mono). Text messages are JSON.
# ---------------------------------------------------------------------------

class AvySerializer(FrameSerializer):

    def __init__(self):
        # Pass Pipecat's status messages (transcripts, who's speaking) to the page.
        super().__init__(FrameSerializer.InputParams(ignore_rtvi_messages=False))

    async def serialize(self, frame):
        """Pipeline -> page."""
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio                                   # Avy's voice
        if isinstance(frame, InterruptionFrame):
            return json.dumps({"type": "interrupt"})             # page: stop playing now
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            return json.dumps(frame.message)                     # transcripts and status
        return None

    async def deserialize(self, data):
        """Page -> pipeline."""
        if isinstance(data, bytes):
            return InputAudioRawFrame(audio=data, sample_rate=MIC_RATE, num_channels=1)
        message = json.loads(data)
        if message.get("type") == "text" and message.get("text"):
            # typed while live: answer it out loud
            return LLMMessagesAppendFrame(
                messages=[{"role": "user", "content": message["text"]}], run_llm=True
            )
        return None


# ---------------------------------------------------------------------------
# 4. One live conversation = one websocket = one pipeline
# ---------------------------------------------------------------------------

server = FastAPI()
get_system_prompt = lambda: "You are Avy."   # replaced by app.py through start()
allowed_origins = []                         # filled in by start()


@server.websocket("/live")
async def live(websocket: WebSocket):
    # Only Avy's own page may open the mic pipeline.
    if websocket.headers.get("origin") not in allowed_origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        await run_conversation(websocket)
    except WebSocketDisconnect:
        pass   # you hung up before it got going
    logger.info("Voice: call ended.")


async def run_conversation(websocket: WebSocket):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key or not status["ready"]:
        reason = "Add your DeepSeek key first." if not key else (status["error"] or "Voice is still loading. Try again in a moment.")
        await websocket.send_json({"type": "error", "text": reason})
        await websocket.close()
        return

    # The page's first message is the conversation so far, so voice picks up where text left off.
    hello = await websocket.receive_json()
    history = [m for m in hello.get("history", []) if m.get("role") in ("user", "assistant")]

    stt, tts = await asyncio.to_thread(make_ears_and_mouth)

    llm = DeepSeekLLMService(
        api_key=key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        settings=DeepSeekLLMService.Settings(
            model="deepseek-flash",   # DeepSeek V4.1 Flash, same as text chat
            system_instruction=get_system_prompt(),
            # Thinking off, for fast replies. Pipecat 1.12 has a "thinking" setting for this,
            # but a bug means it's never sent (and DeepSeek thinks by default), so we
            # send DeepSeek's own field directly.
            extra={"extra_body": {"thinking": {"type": "disabled"}}},
        ),
    )

    context = LLMContext(messages=history)
    user_turns, assistant_turns = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_in_sample_rate=MIC_RATE,
            audio_out_enabled=True,
            audio_out_sample_rate=SPEAKER_RATE,
            serializer=AvySerializer(),
            allowed_origins=allowed_origins,
        ),
    )

    pipeline = Pipeline([
        transport.input(),    # your mic audio comes in
        stt,                  # Whisper: audio -> text, one stretch of speech at a time
        user_turns,           # Silero (talking?) + Smart Turn (finished?) end your turn, then add it
        llm,                  # DeepSeek writes the reply
        tts,                  # Kokoro: reply -> audio, sentence by sentence
        transport.output(),   # audio goes back to the page
        assistant_turns,      # adds what Avy actually said (up to any interruption)
    ])

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=MIC_RATE,
            audio_out_sample_rate=SPEAKER_RATE,
            enable_usage_metrics=True,   # token counts go to the page's "Spent" tile
        ),
    )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, websocket):
        await worker.cancel()   # you turned live off or closed the tab

    await websocket.send_json({"type": "ready"})
    runner = WorkerRunner(handle_sigint=False, force_gc=True)   # app.py owns Ctrl+C; free memory after each call
    await runner.add_workers(worker)
    await runner.run()


# ---------------------------------------------------------------------------
# 5. Start (called by app.py)
# ---------------------------------------------------------------------------

def start(system_prompt, page_port):
    global get_system_prompt, allowed_origins
    get_system_prompt = system_prompt
    allowed_origins = [f"http://localhost:{page_port}", f"http://127.0.0.1:{page_port}"]
    threading.Thread(target=warm_up, daemon=True).start()
    config = uvicorn.Config(server, host="127.0.0.1", port=PORT, log_level="warning")
    threading.Thread(target=uvicorn.Server(config).run, daemon=True).start()
