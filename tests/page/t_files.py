# Attaching files in the page, against the fake Luminal: the button, dropping, pasting, the tray, sending,
# what reached the model, chips in the history, saving code, /export, /files, and importing a Claude export.
import base64, io, json, os, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True)
ASSETS = Path(__file__).resolve().parent / "assets"
REQS = f"{S}/requests.jsonl"
fails = []
def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({str(detail)[:400]})" if not cond else "")); fails.append(name) if not cond else None
def api(path): return json.loads(urllib.request.urlopen("http://localhost:8000" + path).read())
def last_request(): return [json.loads(l) for l in open(REQS)][-1]
def chat_requests(): return [r for r in (json.loads(l) for l in open(REQS)) if not r["body"].get("tools")]
def wait(pg, js, t=30):
    end = time.time() + t
    while time.time() < end:
        if pg.evaluate(js): return True
        time.sleep(0.2)
    return False
def idle(pg): wait(pg, "!document.getElementById('chat').classList.contains('busy')", 60)

from PIL import Image
png = io.BytesIO(); Image.new("RGB", (900, 600), "red").save(png, "PNG")
export = {"conversations.json": [{"uuid": "c1", "name": "Ants", "chat_messages": [
    {"uuid": "m1", "sender": "human", "created_at": "2025-01-01T10:00:00Z", "text": "ants are clever", "content": [{"type": "text", "text": "ants are clever"}]},
    {"uuid": "m2", "sender": "assistant", "created_at": "2025-01-01T10:00:05Z", "text": "they are", "content": [{"type": "text", "text": "they are"}]}]}]}

# Behind a proxy (a cloud workspace), the browser has to use it for everything but Avy.
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []
with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8000"); time.sleep(2.5)

    # ---- the button ----
    check("there's an [ attach ] button", pg.is_visible("#attach"))
    pg.set_input_files("#filePick", [
        {"name": "notes.md", "mimeType": "text/markdown", "buffer": b"# Basil pot\nThe pump is quiet.\n"},
        {"name": "plant.png", "mimeType": "image/png", "buffer": png.getvalue()},
        {"name": "prices.csv", "mimeType": "text/csv", "buffer": b"item,price\npump,12\n"}])
    check("attached files show in the tray", wait(pg, "document.querySelectorAll('#tray .chip').length === 3", 10))
    check("...each is read: lines, a picture", wait(pg, "[...document.querySelectorAll('#tray .chip .wh')].map(e => e.textContent).join('|') === '2 lines|picture, 900×600|2 lines'", 20),
          pg.evaluate("[...document.querySelectorAll('#tray .chip .wh')].map(e => e.textContent)"))
    check("the hint says enter sends them", "enter sends 3 files" in pg.inner_text("#how"), pg.inner_text("#how"))
    pg.screenshot(path=f"{S}/shots/f-tray.png")
    pg.click("#tray .chip:nth-child(3) button"); time.sleep(0.2)
    check("× takes one out", pg.evaluate("document.querySelectorAll('#tray .chip').length") == 2)
    pg.click("#input"); pg.keyboard.type("what's in these?"); pg.keyboard.press("Enter")
    time.sleep(0.5); idle(pg)
    you = pg.evaluate("[...document.querySelectorAll('.line.you')].pop().innerText")
    check("your line carries its files", "notes.md" in you and "plant.png" in you and "prices.csv" not in you, you)
    check("the tray is empty after sending", pg.evaluate("document.getElementById('tray').hidden"))
    reply = pg.evaluate("[...document.querySelectorAll('.line.avy')].pop().innerText")
    check("the model read the file and saw the picture", "I read notes.md" in reply and "I can see 1 image" in reply, reply)
    req = chat_requests()[-1]["body"]
    user = req["messages"][-1]["content"]
    check("...sent as text with <file> tags, then the picture as an image part",
          isinstance(user, list) and user[0]["text"].startswith("what's in these?\n\n[attached]\n<file name=\"notes.md\"")
          and "The pump is quiet." in user[0]["text"] and user[1]["type"] == "image_url" and user[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"),
          json.dumps(user)[:300])
    check("...always streamed, with reasoning_effort and max_tokens", req["stream"] and req["reasoning_effort"] == "none" and req["max_tokens"] == 8000)
    log = api("/api/log?limit=2")["messages"]
    check("the log keeps which files went with the message", [f["name"] for f in log[0]["meta"].get("files", [])] == ["notes.md", "plant.png"], log[0]["meta"])

    # ---- a follow-up: the file is still in front of the model ----
    pg.click("#input"); pg.keyboard.type("and is the pump loud?"); pg.keyboard.press("Enter"); time.sleep(0.5); idle(pg)
    req = chat_requests()[-1]["body"]
    check("a follow-up still has the file in the window", "The pump is quiet." in json.dumps(req["messages"][:-1]) and req["messages"][-1]["content"] == "and is the pump loud?")

    # ---- dropping, pasting, and files with no words ----
    pg.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['dropped words'], 'dropped.txt', {type: 'text/plain'}));
      document.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt, bubbles: true}));
      document.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    check("dropping a file attaches it", wait(pg, "[...document.querySelectorAll('#tray .nm')].some(e => e.textContent === 'dropped.txt')", 10))
    check("...and the drop outline goes away", not pg.evaluate("document.getElementById('chat').classList.contains('dropping')"))
    pg.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['pasted words'], 'image.txt', {type: 'text/plain'}));
      document.getElementById('input').dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    check("pasting a file attaches it", wait(pg, "document.querySelectorAll('#tray .chip').length === 2", 10))
    wait(pg, "[...document.querySelectorAll('#tray .chip')].every(c => !c.classList.contains('busy'))", 10)
    pg.click("#input"); pg.keyboard.press("Enter"); time.sleep(0.5); idle(pg)
    log = api("/api/log?limit=2")["messages"]
    check("files can be sent with no words", log[0]["text"] == "" and len(log[0]["meta"]["files"]) == 2 and log[1]["role"] == "assistant", log[0])
    check("...and the model got them", "I read dropped.txt, image.txt" in log[1]["text"], log[1]["text"][:80])

    # ---- a real recording: what's said ----
    speech = ASSETS / "speech16k.wav"
    if speech.exists():
        pg.set_input_files("#filePick", str(speech))
        ok = wait(pg, "[...document.querySelectorAll('#tray .chip')].every(c => !c.classList.contains('busy'))", 120)
        what = pg.evaluate("document.querySelector('#tray .chip .wh').textContent")
        check("a recording is listened to: transcribed", ok and "transcribed" in what, what)
        fid = api("/api/files")["files"][0]["id"]
        heard = urllib.request.urlopen(f"http://localhost:8000/api/files/{fid}/text").read().decode()
        check("...with times", heard.startswith("[0:0"), heard[:120])
        pg.click("#tray .chip button")

    # ---- reloading: the chips come back with the history ----
    pg.reload(); time.sleep(2.5)
    check("after a reload, messages still show their files", pg.evaluate("[...document.querySelectorAll('.line.you .chips .nm')].map(e => e.textContent).join(',')")
          .startswith("notes.md,plant.png"), pg.evaluate("[...document.querySelectorAll('.line.you .chips .nm')].map(e => e.textContent)"))
    href = pg.evaluate("document.querySelector('.line.you .chips a.nm').href")
    body = urllib.request.urlopen(href).read()
    check("a chip opens the file as it came", body == b"# Basil pot\nThe pump is quiet.\n", body[:60])
    read = pg.evaluate("document.querySelector('.line.you .chips a.act')?.href")
    check("...and 'read' shows what Avy read from it", read and urllib.request.urlopen(read).read().decode().startswith("# Basil pot"))

    # ---- saving code, and /export ----
    pg.click("#input"); pg.keyboard.type("show me some markdown please"); pg.keyboard.press("Enter"); time.sleep(0.5); idle(pg)
    with pg.expect_download() as d:
        pg.click(".codebox .save")
    check("a code box's [ save ] downloads it, named by its language", d.value.suggested_filename == "avy.py"
          and "def hello():" in open(d.value.path()).read(), d.value.suggested_filename)
    for cmd, name_part, check_text in [("/export", ".md", "# Avy: the conversation"), ("/export: json", ".json", '"messages"'),
                                       ("/export: memory", "avy-memory-main", '"nodes"')]:
        with pg.expect_download() as d:
            pg.click("#input"); pg.keyboard.type(cmd); pg.keyboard.press("Enter")
        got = open(d.value.path()).read()
        check(f"{cmd} downloads it", name_part in d.value.suggested_filename and check_text in got, (d.value.suggested_filename, got[:200]))
        if cmd == "/export":
            check("...the Markdown has each message, and what was attached", "**Shreyas**" in got and "*attached: notes.md, plant.png*" in got
                  and "what's in these?" in got, got[:600])
        time.sleep(0.3)

    # ---- /files ----
    pg.click("#input"); pg.keyboard.type("/files"); pg.keyboard.press("Enter"); time.sleep(1)
    check("/files lists what you've attached", pg.evaluate("[...document.querySelectorAll('.line.note .chips .nm')].length") >= 5)

    # ---- a Claude export: import it ----
    pg.set_input_files("#filePick", {"name": "claude-export.json", "mimeType": "application/json", "buffer": json.dumps(export).encode()})
    check("a Claude export is recognized, with [ import ]", wait(pg, "!!document.querySelector('#tray .chip button:not([title=\"Don\\'t send this one\"])')", 20)
          and "Claude export: 1 conversations, 2 messages" in pg.inner_text("#tray"), pg.inner_text("#tray"))
    pg.click("#tray .chip button:has-text('[ import ]')")
    check("importing it reports what went in, and what comes next", wait(pg, "[...document.querySelectorAll('.line.note')].some(l => l.textContent.startsWith('imported 1 conversation, 2 messages'))", 60),
          pg.evaluate("[...document.querySelectorAll('.line.note')].pop().textContent"))
    note = pg.evaluate("[...document.querySelectorAll('.line.note')].pop().textContent")
    check("...into its own memory file, with how to open it and run the mind", "memory-claude.db" in note and "claude_import.py run" in note, note)
    check("...and the file is there", Path(f"{S}/data/memory-claude.db").exists())
    check("the main conversation is untouched", api("/api/import")["state"] == "done" and all(m.get("via") != "claude" for m in api("/api/log?limit=50")["messages"]))
    pg.click("#tray .chip button[title=\"Don't send this one\"]")

    # ---- phone width ----
    pg.set_input_files("#filePick", [{"name": f"a-rather-long-file-name-number-{i}.txt", "mimeType": "text/plain", "buffer": b"x"} for i in range(4)])
    time.sleep(1.5)
    pg.set_viewport_size({"width": 390, "height": 844}); time.sleep(0.6)
    check("phone width: nothing scrolls sideways with files in the tray", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),
          pg.evaluate("document.documentElement.scrollWidth"))
    pg.screenshot(path=f"{S}/shots/f-phone.png", full_page=True)
    pg.set_viewport_size({"width": 1440, "height": 900}); time.sleep(0.4)
    pg.screenshot(path=f"{S}/shots/f-desktop.png")
    check("no page errors", not errs, errs)
    b.close()
print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
