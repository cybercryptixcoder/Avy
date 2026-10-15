"""The library and the looking glass: a file attached in the chat joins memory's library; a whole folder dropped in
the looking glass is read (code, docs, data) with live progress; the library's views in the inspector; a later
question brings library passages into the memory note; [p41] footnotes; dreaming started and woken from the glass;
the glass readable in light and dark."""
import json, os, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True); fails = []
def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({str(detail)[:300]})" if not cond else "")); fails.append(name) if not cond else None
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []
get = lambda path: json.loads(urllib.request.urlopen("http://localhost:8000" + path).read())

def requests():
    return [json.loads(l) for l in open(f"{S}/requests.jsonl") if l.strip()]

def wait_for(fn, seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

# a small project folder to drop in
proj = Path(tempfile.mkdtemp(prefix="avy-proj-")) / "ingester"
(proj / "src").mkdir(parents=True)
(proj / "README.md").write_text("# Ingester\n\nPulls partner feeds and writes them to the warehouse.\n\n## Retries\n\n"
                                "A failed fetch is retried 3 times, backing off 0.5 s, then 1 s, then 2 s.\n")
(proj / "src" / "client.py").write_text("RETRIES = 3\nBACKOFF = [0.5, 1, 2]\n\n\ndef fetch(session, url):\n    return session.get(url)\n")
(proj / "partners.csv").write_text("partner,feed\nacme,https://acme.example/feed\nglobex,https://globex.example/feed\n")
(proj / "node_modules" / "x").mkdir(parents=True)
(proj / "node_modules" / "x" / "index.js").write_text("module.exports = 1")
note = Path(tempfile.mkdtemp()) / "oncall.txt"
note.write_text("On-call rota for the ingester: Priya Raman this quarter, then Dev Patel.\n")

with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8000"); time.sleep(2)

    # --- a file attached in the chat joins the library ---------------------------------------------------
    pg.set_input_files("#filePick", str(note)); time.sleep(1.5)
    pg.click("#input"); pg.keyboard.type("here's the on-call rota"); pg.keyboard.press("Enter")
    check("an attached file joins memory's library by itself", wait_for(lambda: any(s["name"] == "oncall.txt" and s["status"] == "stored"
                                                                                   for s in get("/api/library")["sources"])), get("/api/library"))

    # --- the looking glass: drop a folder, watch it load -----------------------------------------------------
    pg.click("#openGlass"); time.sleep(1)
    check("the looking glass opens", pg.is_visible("#glass") and "loading into memory" in pg.inner_text("#glassBody"))
    pg.set_input_files("#libFolder", str(proj)); time.sleep(0.5)
    check("a folder dropped in: it uploads and goes in as one source", wait_for(lambda: any(s["name"] == "ingester" and s["status"] == "stored"
                                                                                           for s in get("/api/library")["sources"]), 120),
          get("/api/library")["intake"])
    src = next(s for s in get("/api/library")["sources"] if s["name"] == "ingester")
    check("...read by kind: code, docs and data, with node_modules left out", src["meta"].get("files") == 3
          and src["meta"]["skipped"]["folders"] >= 1, src["meta"])
    time.sleep(2)
    body = pg.inner_text("#glassBody")
    check("the glass shows it: in memory, its passages and how long it took", "ingester" in body and "in memory: searchable" in body, body[:600])
    check("...and the state of memory, the mind, the Claude history and dreaming", all(w in body for w in ("memory now", "the mind", "your claude history", "dreaming")), body[:300])
    pg.screenshot(path=f"{S}/shots/glass-light.png")

    # --- dreaming from the glass ---------------------------------------------------------------------------
    urllib.request.urlopen(urllib.request.Request("http://localhost:8000/api/index", data=b"{}", method="POST")).read()   # some knowledge first
    dream_btn = pg.locator("#glassBody button.act", has_text="[ dream ]")
    dream_btn.first.click(); time.sleep(1.5)
    st = get("/api/glass")["dream"]
    check("dreaming starts from the glass, at max thinking", st["state"] in ("dreaming", "awake") and st.get("effort", "max") == "max", st)
    time.sleep(1)
    if get("/api/glass")["dream"]["state"] == "dreaming":       # a tiny memory may run out of things to dream about first
        pg.locator("#glassBody button.act", has_text="[ wake ]").first.click()
    check("...and wakes (when asked, or when there's nothing left to find), leaving a record", wait_for(lambda: get("/api/glass")["dream"]["state"] == "awake", 60)
          and any(r["job"] == "dream" for r in get("/api/glass")["mind"]["runs"]), get("/api/glass")["dream"])
    reqs = [r for r in requests() if r["body"].get("tools") and r["body"]["reasoning_effort"] == "max"]
    check("...its calls went to Luminal thinking at max", len(reqs) >= 1, len(reqs))

    # --- the library in the inspector ---------------------------------------------------------------------------
    pg.keyboard.press("Escape"); time.sleep(0.4)
    pg.click("#input"); pg.keyboard.type("/library"); pg.keyboard.press("Enter"); time.sleep(1.2)
    check("/library lists what was added", "ingester" in pg.inner_text("#inspBody") and "oncall.txt" in pg.inner_text("#inspBody"))
    pg.locator("#inspBody .row", has_text="ingester").first.click(); time.sleep(1)
    check("a source shows its passages, labeled by file and place", "src/client.py:1-" in pg.inner_text("#inspBody") and "README.md" in pg.inner_text("#inspBody"))
    pg.locator("#inspBody .row", has_text="src/client.py").first.click(); time.sleep(1)
    check("a passage, word for word", "BACKOFF = [0.5, 1, 2]" in pg.inner_text("#inspBody"))
    pg.click("#inspClose"); time.sleep(0.3)

    # --- a question brings library passages into the memory note ----------------------------------------------------
    open(f"{S}/requests.jsonl", "w").close()
    pg.click("#input"); pg.keyboard.type("what's the backoff when an ingester fetch fails, and who is on call?"); pg.keyboard.press("Enter")
    time.sleep(1); wait_for(lambda: not pg.evaluate("document.getElementById('chat').classList.contains('busy')"), 60)
    reply_req = [r for r in requests() if not r["body"].get("tools")]
    note_text = reply_req[-1]["body"]["messages"][-2]["content"] if reply_req else ""
    check("the memory note brings passages from the library, with their source", "From his library" in note_text and "[p" in note_text
          and ("Priya" in note_text or "0.5 s" in note_text or "BACKOFF" in note_text), note_text[-900:])
    trace = pg.locator(".line.trace").last.inner_text()
    check("the line under the reply counts them", "passage" in trace, trace)

    # --- the glass in the dark ---------------------------------------------------------------------------------------
    urllib.request.urlopen(urllib.request.Request("http://localhost:8000/api/settings", data=json.dumps({"name": "theme", "value": "dark"}).encode(),
                                                  headers={"Content-Type": "application/json"})).read()
    pg.reload(); time.sleep(1.5)
    pg.click("#openGlass"); time.sleep(2)
    pg.screenshot(path=f"{S}/shots/glass-dark.png")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from audit import CONTRAST  # noqa: E402  (the same audit the look test uses)
    low = pg.evaluate(CONTRAST, 2.5)
    check("the glass in the dark: everything readable", not [x for x in low if "glass" in x["what"] or "pane" in x["what"] or "job" in x["what"]], low[:4])
    pg.keyboard.press("Escape"); time.sleep(0.3)
    check("Esc closes the glass", not pg.is_visible("#glass"))
    urllib.request.urlopen(urllib.request.Request("http://localhost:8000/api/settings", data=json.dumps({"name": "theme", "value": "auto"}).encode(),
                                                  headers={"Content-Type": "application/json"})).read()
    check("no page errors", not errs, errs)
    b.close()
print(f"\n{len(fails)} failed")
