"""
Avy's voice: push-to-talk. app.py starts this when the voice packages are installed.

You hold Space (or double-tap it to lock) while you talk. When you let go:
    ears   faster-whisper writes down the whole recording in one go
    brain  DeepSeek answers (the same request text chat uses, via app.py)
    mouth  Kokoro 82M speaks the answer, a sentence at a time, while the rest is still coming
Pressing Space again while Avy talks cuts her off.

Every recording is written to data/recordings as it comes in, so a crash or a failed
transcription never loses what you said. The newest ones are kept; old ones are deleted.
The models are downloaded once into data/models.
"""

import asyncio
import json
import re
import threading
import time
import urllib.request
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from kokoro_onnx import Kokoro
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

PORT = 8001
MIC_RATE = 16000                 # the page sends 16-bit mono PCM at this rate
KEEP_RECORDINGS = 50             # keep at most this many recordings...
KEEP_RECORDINGS_MB = 300         # ...and at most this much disk; the oldest go first
KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}

status = {"ready": False, "problem": "Voice is starting..."}   # app.py shows this on the page
app = {}                                                        # filled in by start()


# ---------------------------------------------------------------------------
# 2. The models: downloaded once into data/models, loaded once, shared by every call
# ---------------------------------------------------------------------------

model_lock = threading.Lock()


def download(url, dest):
    """Download to a .part file and rename at the end, so a cut-off download is never mistaken for a good one."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60, context=app["ssl_context"]) as response, open(part, "wb") as out:
        total, done, shown = int(response.headers.get("Content-Length") or 0), 0, -1
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total and (pct := done * 100 // total) // 10 != shown:
                shown = pct // 10
                status["problem"] = f"Voice is downloading {dest.name}: {pct}%"
                print(f"Voice: downloading {dest.name} {pct}%")
    part.rename(dest)


@lru_cache(maxsize=None)
def whisper(name):
    with model_lock:
        return WhisperModel(name, device="auto", compute_type="int8",
                            download_root=str(app["data"] / "models" / "whisper"))


@lru_cache(maxsize=None)
def kokoro():
    folder = app["data"] / "models" / "kokoro"
    with model_lock:
        for name, url in KOKORO_FILES.items():
            if not (folder / name).exists():
                download(url, folder / name)
        return Kokoro(str(folder / "kokoro-v1.0.onnx"), str(folder / "voices-v1.0.bin"))


def warm_up():
    """Load both models and run each once, so your first sentence isn't the slow one."""
    try:
        status["problem"] = "Voice is loading its models (the first run downloads about 0.7 GB)..."
        kokoro().create("Ready.", voice="af_heart")
        whisper(app["settings"]()["whisper"]).transcribe(np.zeros(MIC_RATE, np.float32), language="en")
        status.update(ready=True, problem=None)
        print("Voice: ready. Hold Space in the chat to talk.")
    except Exception as e:
        status.update(ready=False, problem=f"Voice failed to load: {e}")
        print(f"Voice: failed to load: {e}")


def preload_whisper(name):
    threading.Thread(target=whisper, args=(name,), daemon=True).start()


# ---------------------------------------------------------------------------
# 3. Recordings: written to disk as they arrive, so nothing you say is lost
# ---------------------------------------------------------------------------

class Recording:
    def __init__(self):
        folder = app["data"] / "recordings"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.path, n = folder / f"{stamp}.wav", 2
        while self.path.exists():
            self.path, n = folder / f"{stamp}_{n}.wav", n + 1
        self.file = open(self.path, "wb")
        self.wav = wave.open(self.file, "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(MIC_RATE)
        self.pcm = bytearray()

    def add(self, chunk):
        self.wav.writeframes(chunk)        # also rewrites the WAV header, so the file is always playable
        self.pcm += chunk
        if len(self.pcm) % (MIC_RATE * 2) < len(chunk):
            self.file.flush()              # push to disk about once a second

    @property
    def seconds(self):
        return len(self.pcm) / (MIC_RATE * 2)

    def close(self):
        self.wav.close()
        self.file.close()
        prune_recordings()


def prune_recordings():
    folder = app["data"] / "recordings"
    wavs = sorted(folder.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    kept_bytes = 0
    for i, wav_file in enumerate(wavs):
        kept_bytes += wav_file.stat().st_size
        if i >= KEEP_RECORDINGS or kept_bytes > KEEP_RECORDINGS_MB * 1e6:
            wav_file.unlink(missing_ok=True)
            wav_file.with_suffix(".txt").unlink(missing_ok=True)


def transcribe(source):
    """A whole recording in (a .wav path or raw PCM), text out. Runs in a background thread."""
    if isinstance(source, Path):
        with wave.open(str(source)) as w:
            source = w.readframes(w.getnframes())
    audio = np.frombuffer(bytes(source), np.int16).astype(np.float32) / 32768
    if len(audio) < MIC_RATE // 4:
        return ""
    segments, _ = whisper(app["settings"]()["whisper"]).transcribe(
        audio, language="en", beam_size=5, without_timestamps=True,
        condition_on_previous_text=False, hotwords="Avy",
    )
    return " ".join(s.text.strip() for s in segments).strip()


# ---------------------------------------------------------------------------
# 4. Replies: DeepSeek streams text; finished sentences go to Kokoro while the rest is coming
# ---------------------------------------------------------------------------

def stream_deepseek(messages, put, cancel):
    """Runs in a background thread: reads DeepSeek's stream and hands pieces to the event loop."""
    try:
        upstream = app["ask"](messages)
    except Exception as e:
        return put(("error", getattr(e, "message", str(e))))
    try:
        with upstream:
            for line in upstream:
                if cancel.is_set():
                    return
                line = line.decode().strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[5:])
                if chunk.get("usage"):
                    put(("usage", chunk["usage"]))
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("reasoning_content"):
                        put(("thinking", None))
                    if delta.get("content"):
                        put(("text", delta["content"]))
    except Exception as e:
        return put(("error", f"Lost the connection to DeepSeek partway through ({e})."))
    put(("end", None))


def take_sentences(buffer, first):
    """Split finished sentences off the front of the buffer. Never cuts inside a code block."""
    sentences = []
    while buffer.count("```") % 2 == 0:
        match = re.search(r"[.!?…][\"')\]]*\s|\n", buffer)
        end = match.end() if match else None
        if end is None and first and not sentences and len(buffer) > 60:
            comma = re.search(r"[,;:]\s", buffer[40:])       # a long first sentence: start talking at a comma
            end = 40 + comma.end() if comma else None
        if end is None:
            break
        sentence, buffer = buffer[:end].strip(), buffer[end:]
        if sentence:
            sentences.append(sentence)
    return sentences, buffer


def speakable(text):
    """What Kokoro should actually say: no code, no markdown symbols."""
    text = re.sub(r"```.*?```", " (code on screen) ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-•*]\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`#>]+", "", text)
    return " ".join(text.split())


async def reply(ws, messages, speak):
    loop = asyncio.get_running_loop()
    pieces, sentences = asyncio.Queue(), asyncio.Queue()
    cancel = threading.Event()
    put = lambda item: loop.call_soon_threadsafe(pieces.put_nowait, item)
    threading.Thread(target=stream_deepseek, args=(messages, put, cancel), daemon=True).start()
    mouth = asyncio.create_task(speak_sentences(ws, sentences)) if speak else None

    text, pending, usage, told_thinking, queued_any = "", "", None, False, False
    try:
        while True:
            kind, value = await pieces.get()
            if kind == "thinking" and not told_thinking:
                told_thinking = True
                await ws.send(json.dumps({"type": "thinking"}))
            elif kind == "text":
                text += value
                if speak:
                    done, pending = take_sentences(pending + value, first=not queued_any)
                    for sentence in done:
                        sentences.put_nowait(sentence)
                        queued_any = True
                else:
                    await ws.send(json.dumps({"type": "delta", "text": value}))
            elif kind == "usage":
                usage = value
            elif kind == "error":
                await ws.send(json.dumps({"type": "error", "text": value}))
                break
            elif kind == "end":
                break
        if mouth:
            if pending.strip():
                sentences.put_nowait(pending.strip())
            sentences.put_nowait(None)
            await mouth
        await ws.send(json.dumps({"type": "done", "text": text, "usage": usage}))
    finally:
        cancel.set()          # stop reading DeepSeek if we were cut off
        if mouth:
            mouth.cancel()


async def speak_sentences(ws, sentences):
    choice = app["settings"]()
    voice, speed = choice["voice"], float(choice["speed"])
    while (sentence := await sentences.get()) is not None:
        words = speakable(sentence)
        if not words:
            await ws.send(json.dumps({"type": "say", "text": sentence, "silent": True}))
            continue
        samples, _rate = await asyncio.to_thread(
            kokoro().create, words, voice=voice, speed=speed, lang="en-gb" if voice.startswith("b") else "en-us")
        await ws.send(json.dumps({"type": "say", "text": sentence}))      # caption for the audio that follows
        await ws.send((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())   # 24 kHz 16-bit mono


# ---------------------------------------------------------------------------
# 5. One connection per page. Messages from the page:
#      {"type": "start"}       you pressed Space: stop Avy, start a new recording
#      <binary>                microphone audio while you hold Space
#      {"type": "stop"}        you let go: transcribe it
#      {"type": "cancel"}      just a tap: don't transcribe (still kept on disk if over 1 second)
#      {"type": "reply", "messages": [...], "speak": true}    answer the conversation
#      {"type": "retry"}       transcribe the newest recording again
# ---------------------------------------------------------------------------

async def session(ws):
    recording, job = None, None

    def stop_reply():
        nonlocal job
        if job and not job.done():
            job.cancel()
        job = None

    async def send_transcript(path, pcm=None):
        where = str(path.relative_to(app["data"].parent))
        await ws.send(json.dumps({"type": "transcribing"}))
        try:
            text = await asyncio.to_thread(transcribe, pcm if pcm is not None else path)
            if text:
                path.with_suffix(".txt").write_text(text)
            await ws.send(json.dumps({"type": "transcript", "text": text, "file": where}))
        except Exception as e:
            await ws.send(json.dumps({"type": "error", "text":
                f"Couldn't transcribe ({e}). Your recording is safe in {where}. Type /retry to try again."}))

    try:
        async for message in ws:
            if isinstance(message, bytes):
                if recording:
                    recording.add(message)
                continue
            m = json.loads(message)
            kind = m.get("type")
            if kind == "start":
                stop_reply()
                if recording:
                    recording.close()
                recording = Recording()
            elif kind == "cancel" and recording:
                recording.close()
                if recording.seconds < 1:
                    recording.path.unlink(missing_ok=True)
                recording = None
            elif kind == "stop" and recording:
                done, recording = recording, None
                done.close()
                asyncio.create_task(send_transcript(done.path, done.pcm))
            elif kind == "reply":
                stop_reply()
                job = asyncio.create_task(reply(ws, m.get("messages", []), m.get("speak", True)))
            elif kind == "retry":
                folder = app["data"] / "recordings"
                wavs = sorted(folder.glob("*.wav"), key=lambda p: p.stat().st_mtime) if folder.exists() else []
                if wavs:
                    asyncio.create_task(send_transcript(wavs[-1]))
                else:
                    await ws.send(json.dumps({"type": "error", "text": "There are no recordings yet."}))
    except ConnectionClosed:
        pass
    finally:
        stop_reply()
        if recording:
            recording.close()   # whatever arrived is safe on disk


# ---------------------------------------------------------------------------
# 6. Start (called by app.py)
# ---------------------------------------------------------------------------

async def serve_forever(origins):
    async with serve(session, "127.0.0.1", PORT, origins=origins, max_size=None):
        await asyncio.Future()


def start(ask, settings, data, page_port, ssl_context):
    app.update(ask=ask, settings=settings, data=Path(data), ssl_context=ssl_context)
    origins = [f"http://localhost:{page_port}", f"http://127.0.0.1:{page_port}"]   # only Avy's own page
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(serve_forever(origins)), daemon=True).start()
    print(f"Voice: starting on port {PORT}.")
