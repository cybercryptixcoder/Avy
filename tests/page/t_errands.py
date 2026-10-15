# The errands: the two dials, incognito, and dictation vs live. Against the fake Luminal (run.py starts it).
import glob, json, os, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True)
DATA = f"{S}/data"
ASSETS = Path(__file__).resolve().parent / "assets"
fails = []


def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def api(path, body=None):
    req = urllib.request.Request("http://localhost:8000" + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    raw = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(raw) if raw[:1] in b"{[" else raw


def last_request():
    lines = [json.loads(l) for l in open(f"{S}/requests.jsonl") if l.strip()]
    chats = [l["body"] for l in lines if not l["body"].get("tools")]
    return chats[-1]


def wait(pg, cond, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pg.evaluate(cond):
            return True
        time.sleep(0.1)
    return False


def say(pg, text):
    pg.click("#input"); pg.keyboard.type(text); pg.keyboard.press("Enter"); time.sleep(0.3)
    wait(pg, "!document.getElementById('chat').classList.contains('busy')"); time.sleep(0.3)


def command(pg, text):
    pg.click("#input"); pg.keyboard.type(text); pg.keyboard.press("Enter"); time.sleep(0.5)


# Behind a proxy (a cloud workspace), the browser has to use it for everything but Avy.
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []
with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY,
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={ASSETS}/fakemic.wav",
        "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, permissions=["microphone", "clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto("http://localhost:8000"); time.sleep(2)

    # ---------------- the dials ----------------
    rows = pg.evaluate("[...document.querySelectorAll('.sys-row .k')].map(k => k.textContent)")
    check("system card has window, recall and live (and no speak)", {"window", "recall", "live"} <= set(rows) and "speak" not in rows, rows)
    for i in range(14):
        api("/api/chat", {"text": f"message number {i} about my cat Miso"})
    def history_sent():
        return [m for m in last_request()["messages"] if m["role"] in ("user", "assistant")]
    say(pg, "hello there")
    n20 = len(history_sent()) - 1
    check("window 20: 20 to 29 earlier messages sent word for word", 20 <= n20 <= 29, n20)
    command(pg, "/window: 0")
    say(pg, "what's my cat called?")
    req = last_request()
    check("window 0: only your new message is sent word for word", len(history_sent()) == 1, len(history_sent()))
    check("...and memory still found the cat in the log", "Miso" in req["messages"][-2]["content"], req["messages"][-2]["content"][:300])
    command(pg, "/window: all")
    say(pg, "and again")
    total = api("/api/memory?episodes=0")["stats"]["messages"]
    check("window all: the whole conversation is sent", len(history_sent()) - 1 == total - 2, (len(history_sent()), total))
    command(pg, "/recall: off")
    say(pg, "what's my cat called?")
    check("recall off: the memory note says so", "recall is off" in last_request()["messages"][-2]["content"])
    check("...and no recall line under the reply", not pg.evaluate("[...document.querySelectorAll('.line.avy')].pop().nextElementSibling?.classList.contains('trace')"))
    command(pg, "/recall: deep")
    command(pg, "/window: 0")
    say(pg, "tell me about my cat")
    check("recall deep at window 0 brings the cat back", "Miso" in last_request()["messages"][-2]["content"])
    before = api("/api/memory?episodes=0")["stats"]
    for i in range(3):
        api("/api/chat", {"text": f"tiny chat {i}"})
    time.sleep(2.5)       # the background indexer wakes after each reply
    after = api("/api/memory?episodes=0")["stats"]
    check("window 0: index pages are written every few messages", after["waiting"] < 6 and after["episodes"] > before["episodes"], (before["episodes"], after))
    command(pg, "/window: 20"); command(pg, "/recall: normal")

    # ---------------- incognito ----------------
    main_before = api("/api/memory?episodes=0")["stats"]["messages"]
    command(pg, "/incognito")
    time.sleep(0.8)
    check("incognito: the conversation turns dark", pg.evaluate("document.getElementById('chat').classList.contains('incognito')"))
    check("...the main conversation is off the screen", pg.evaluate("document.querySelectorAll('.line.you').length") == 0)
    check("...and [ end incognito ] shows", pg.is_visible("#endIncognito"))
    pg.screenshot(path=f"{S}/shots/e-incognito.png")
    say(pg, "secret: I'm planning a surprise party for Priya")
    say(pg, "what's my cat called?")
    req = last_request()
    check("Avy is told it's incognito", "incognito conversation" in req["messages"][0]["content"])
    check("...and can still read the main memory (the cat)", "Miso" in req["messages"][-2]["content"], req["messages"][-2]["content"][:400])
    check("the main log didn't grow", api("/api/memory?episodes=0&memory=main")["stats"]["messages"] == main_before)
    inc_stats = api("/api/memory?episodes=0")["stats"]
    check("the incognito memory has its own messages", inc_stats["memory"] == "incognito" and inc_stats["messages"] == 4, inc_stats)
    files = glob.glob(f"{DATA}/incognito/*.db")
    check("it lives in its own file under data/incognito", len(files) == 1, files)
    pg.reload(); time.sleep(2)
    check("a reload stays in incognito, with its conversation (once)", pg.evaluate("document.getElementById('chat').classList.contains('incognito')")
          and pg.evaluate("document.querySelectorAll('.line.you').length") == 2, pg.evaluate("document.querySelectorAll('.line.you').length"))
    traces = pg.query_selector_all(".line.trace")
    if traces:
        traces[-1].click(); time.sleep(0.8)
        body = pg.inner_text("#inspBody")
        check("its recall view marks entries or lines from the main memory", "main" in body, body[:300])
        rows = pg.query_selector_all("#inspBody .row")
        if rows:
            rows[-1].click(); time.sleep(0.8)
            check("clicking a main-memory item opens it from the main memory", "couldn't load" not in pg.inner_text("#inspBody"), pg.inner_text("#inspBody")[:200])
        pg.click("#inspClose")
    else:
        check("incognito replies get recall lines", False)
    pg.click("#endIncognito"); time.sleep(1.2)
    check("ending it: back to the main conversation", not pg.evaluate("document.getElementById('chat').classList.contains('incognito')")
          and pg.evaluate("document.querySelectorAll('.line.you').length") > 0)
    check("...its files are deleted", not os.path.exists(f"{DATA}/incognito"), glob.glob(f"{DATA}/incognito/**", recursive=True))
    check("...and the secret is nowhere in the main memory", "surprise" not in json.dumps(api("/api/log?limit=200")))
    try:
        api("/api/memory?memory=incognito")
        check("asking for an ended incognito memory is refused", False)
    except urllib.error.HTTPError as e:
        check("asking for an ended incognito memory is refused", e.code == 404)

    # ---------------- dictation (the default) ----------------
    n_you = pg.evaluate("document.querySelectorAll('.line.you').length")
    pg.click("#input"); pg.keyboard.down("Space"); time.sleep(8.6); pg.keyboard.up("Space")
    wait(pg, "document.getElementById('input').value.length > 0", 60)
    typed = pg.input_value("#input")
    check("dictation: what you said lands in the box", "remind" in typed.lower(), typed)
    check("...and nothing was sent", pg.evaluate("document.querySelectorAll('.line.you').length") == n_you)
    pg.keyboard.press("End")
    pg.keyboard.down("Space"); time.sleep(0.08); pg.keyboard.up("Space")
    pg.keyboard.type("ok")
    check("a quick tap in a box with text types a space", pg.input_value("#input").endswith(" ok"), pg.input_value("#input")[-20:])
    pg.keyboard.down("Space"); time.sleep(4.5); pg.keyboard.up("Space")
    wait(pg, "document.getElementById('input').value.length > %d" % (len(typed) + 10), 60); time.sleep(0.3)
    second = pg.input_value("#input")
    check("holding space in a box with text dictates more onto the end", len(second) > len(typed) + 10 and second.startswith(typed), second)
    pg.screenshot(path=f"{S}/shots/e-dictation.png")
    pg.keyboard.press("Enter"); time.sleep(0.5)
    wait(pg, "!document.getElementById('chat').classList.contains('busy')")
    check("Enter sends the dictated text as a normal message", pg.evaluate("document.querySelectorAll('.line.you').length") == n_you + 1)

    # ---------------- live mode ----------------
    command(pg, "/live: on")
    check("live mode: the button says [ talk ]", pg.inner_text("#talk") == "[ talk ]")
    pg.click("#input"); pg.keyboard.down("Space"); time.sleep(8.6); pg.keyboard.up("Space")
    check("live: Avy answers out loud", wait(pg, "voiceState === 'speaking'", 60))
    wait(pg, "voiceState === 'idle'", 120); time.sleep(1)
    for _ in range(30):                     # the save can trail the audio a little while the mind is busy
        log = api("/api/log?limit=2")["messages"]
        if [m["via"] for m in log] == ["voice", "voice"]:
            break
        time.sleep(0.5)
    check("live: both sides saved as spoken", [m["via"] for m in log] == ["voice", "voice"] and not log[-1]["meta"].get("cut"), log)
    command(pg, "/live: off")
    check("dictation mode again: the button says [ dictate ]", pg.inner_text("#talk") == "[ dictate ]")
    check("no page errors", not errs, errs)
    b.close()

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
