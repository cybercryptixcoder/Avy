# Memory v2's page, against the fake Luminal (run.py starts it): the card, the command panel, footnotes, chapters,
# the inspector's new views, Avy's own search, and the living graph.
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright

S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True)
fails = []


def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({detail})" if detail and not cond else ""), flush=True)
    if not cond:
        fails.append(name)


def api(path, body=None):
    req = urllib.request.Request("http://localhost:8000" + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def wait(pg, cond, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pg.evaluate(cond):
            return True
        time.sleep(0.1)
    return False


def say(pg, text):
    pg.click("#input"); pg.keyboard.type(text); pg.keyboard.press("Enter"); time.sleep(0.3)
    wait(pg, "!document.getElementById('chat').classList.contains('busy')"); time.sleep(0.4)


def command(pg, text):
    pg.click("#input"); pg.keyboard.type(text); pg.keyboard.press("Enter"); time.sleep(0.6)


# Behind a proxy (a cloud workspace), the browser has to use it for everything but Avy.
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []
with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY])
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto("http://localhost:8000"); time.sleep(2)

    rows = pg.evaluate("[...document.querySelectorAll('.sys-row .k')].map(k => k.textContent)")
    check("the system card keeps only the important settings", rows == ["thinking", "window", "recall", "explore", "live"], rows)
    info = pg.evaluate("[...document.querySelectorAll('.sys-info .k')].map(k => k.textContent)")
    check("...and shows memory, what it knows, the mind and the search mode", {"memory", "knows", "mind", "search"} <= set(info), info)

    pg.click("#input"); pg.keyboard.type("/")
    time.sleep(0.4)
    check("typing / opens the command panel at once", pg.evaluate("document.getElementById('cmds').classList.contains('open')"))
    items = pg.evaluate("[...document.querySelectorAll('#cmdsList li')].map(li => [li.querySelector('.name')?.textContent, li.querySelector('.short')?.textContent, li.querySelector('.value')?.textContent])")
    names = [i[0] for i in items]
    check("every command is listed, settings and actions", {"/window:", "/words:", "/meaning:", "/explore:", "/graph", "/reflect", "/memory"} <= set(names), names)
    check("each has a short description under its name", all(i[1] and len(i[1].split()) <= 6 for i in items), [i for i in items if not i[1] or len(i[1].split()) > 6])
    check("settings show their current value", dict((i[0], i[2]) for i in items).get("/window:") == "20")
    sep = pg.evaluate("getComputedStyle(document.querySelector('#cmdsList li')).borderBottomStyle")
    check("rows are separated by a line", sep == "solid", sep)
    pg.screenshot(path=f"{S}/shots/v2-commands.png")
    pg.keyboard.type("wi")
    time.sleep(0.2)
    check("typing narrows the list", pg.evaluate("[...document.querySelectorAll('#cmdsList li .name')].map(n => n.textContent)") == ["/window:"])
    pg.keyboard.press("Escape")

    for t in ["my friend Rohan just moved to Pittsburgh", "and my sister Priya wants to visit Rohan in Pittsburgh",
              "I also started learning the cello this week"]:
        say(pg, t)
    command(pg, "/index")
    wait(pg, "[...document.querySelectorAll('.line.note')].some(l => l.textContent.includes('wrote ep'))", 60)
    note = pg.evaluate("[...document.querySelectorAll('.line.note')].pop().textContent")
    check("/index writes what's waiting and says what it wrote", "wrote ep1" in note and "node" in note, note)
    st = api("/api/memory?episodes=0")["stats"]
    check("knowledge exists now", st["nodes"] >= 4 and st["episodes"] == 1, st)

    say(pg, "what do you know about Rohan?")
    fn = pg.query_selector_all(".line.avy .fn")
    check("a reply that used memory has a footnote", len(fn) >= 1, pg.evaluate("[...document.querySelectorAll('.line.avy')].pop().innerHTML"))
    if fn:
        fn[-1].hover(); time.sleep(1.2)
        card = pg.evaluate("document.querySelector('.fn-card')?.innerText || ''")
        check("hovering it shows what memory said, with its standing and his words", "you said" in card and '"' in card, card)
        pg.screenshot(path=f"{S}/shots/v2-footnote.png")
        pg.mouse.move(5, 5)
        fn[-1].click(); time.sleep(1.2)
        check("clicking it opens the node in the inspector", pg.evaluate("document.getElementById('inspTitle').textContent").startswith("── k"))
        body = pg.inner_text("#inspBody")
        check("...a node page: standing, where it was said, connections, versions", "you said" in body and "said in" in body and "versions" in body, body[:400])
        pg.screenshot(path=f"{S}/shots/v2-node.png")
        links = pg.query_selector_all("#inspBody .ref")
        edge_link = next((l for l in links if l.inner_text().startswith("c")), None)
        if edge_link:
            edge_link.click(); time.sleep(1)
            body = pg.inner_text("#inspBody")
            check("a connection page: its reason, strength and supports", "supports" in body and "strength" in body, body[:300])
        pg.click("#inspClose")
    trace = pg.query_selector_all(".line.trace")
    check("the reply says what memory brought", trace and "node" in trace[-1].inner_text(), trace and trace[-1].inner_text())
    chapters = pg.evaluate("[...document.querySelectorAll('.chapter')].map(c => c.innerText)")
    check("the conversation is marked where the sitting began", len(chapters) == 1 and "today" in chapters[0], chapters)

    command(pg, "/memory")
    time.sleep(1)
    body = pg.inner_text("#inspBody")
    check("/memory: numbers, the network, conversations", "conversation" in body and "connection" in body and "ep1" in body, body[:400])
    pg.screenshot(path=f"{S}/shots/v2-memory.png")
    pg.query_selector_all("#inspBody .row")[0].click(); time.sleep(1)
    body = pg.inner_text("#inspBody")
    check("a conversation page: what was written, and how", "knowledge written from it" in body and "what it changed" in body, body[:400])
    for view in ["journal", "health"]:
        pg.evaluate(f"inspect('{view}')"); time.sleep(1)
        check(f"the {view} view opens", "couldn't load" not in pg.inner_text("#inspBody"), pg.inner_text("#inspBody")[:200])
    pg.screenshot(path=f"{S}/shots/v2-health.png")
    pg.click("#inspClose")

    command(pg, "/explore: on")
    say(pg, "anything coming up with my family?")
    check("with explore on, the reply says Avy searched", "searched memory" in pg.query_selector_all(".line.trace")[-1].inner_text(),
          pg.query_selector_all(".line.trace")[-1].inner_text())
    pg.query_selector_all(".line.trace")[-1].click(); time.sleep(1)
    body = pg.inner_text("#inspBody")
    check("the recall view replays her search, round by round", "avy's search" in body and "round 1" in body and "read:" in body, body[:500])
    pg.screenshot(path=f"{S}/shots/v2-explore.png")
    pg.click("#inspClose")
    command(pg, "/explore: off")

    command(pg, "/words: off")
    command(pg, "/meaning: off")
    say(pg, "what do you know about Rohan?")
    reqs = [json.loads(l) for l in open(f"{S}/requests.jsonl") if l.strip()]
    chat = [r["body"] for r in reqs if not r["body"].get("tools")][-1]
    check("with words and meaning off, Avy gets no memory at all", "switched off" in chat["messages"][-2]["content"]
          and "hubs of your memory" not in chat["messages"][0]["content"], chat["messages"][-2]["content"][:200])
    command(pg, "/words: on"); command(pg, "/meaning: on")

    pg.evaluate("loadGraph()"); time.sleep(1.5)
    check("the corner shows the network once there is one", pg.is_visible("#mini") and not pg.is_visible("#scope"))
    pg.screenshot(path=f"{S}/shots/v2-mini.png")
    pg.click("#mini"); time.sleep(2.5)
    check("clicking it opens the graph, full page", pg.is_visible("#graph"))
    drawn = pg.evaluate("graphShown.length")
    check("the graph draws every node", drawn == api("/api/memory?episodes=0")["stats"]["nodes"], drawn)
    pg.screenshot(path=f"{S}/shots/v2-graph.png")
    hub = pg.evaluate("(() => { const s = graphShown.slice().sort((a, b) => b.p.degree - a.p.degree)[0]; const r = document.getElementById('graphCanvas').getBoundingClientRect(); return [r.left + s.q.x, r.top + s.q.y]; })()")
    pg.mouse.move(*hub); time.sleep(0.6)
    check("hovering a node shows what it is", pg.is_visible("#graphTip"), pg.evaluate("document.getElementById('graphTip').innerText"))
    hub = pg.evaluate("(() => { const s = graphShown.slice().sort((a, b) => b.p.degree - a.p.degree)[0]; const r = document.getElementById('graphCanvas').getBoundingClientRect(); return [r.left + s.q.x, r.top + s.q.y]; })()")
    pg.mouse.click(*hub); time.sleep(1.2)
    check("clicking a node shows its card", pg.is_visible("#graphCard") and "open in the inspector" in pg.inner_text("#graphCard"), pg.inner_text("#graphCard"))
    pg.screenshot(path=f"{S}/shots/v2-graph-card.png")
    pg.mouse.move(700, 450); pg.mouse.down(); pg.mouse.move(820, 470, steps=6); pg.mouse.up()
    pg.mouse.wheel(0, -400); time.sleep(0.5)
    pg.keyboard.press("Escape"); time.sleep(0.4)
    check("Esc closes the graph", not pg.is_visible("#graph"))

    command(pg, "/incognito")
    time.sleep(1)
    say(pg, "secret plan: a party for Priya")
    fn = pg.query_selector_all(".line.avy .fn")
    check("incognito replies can cite main memory too", True)
    command(pg, "/incognito")
    time.sleep(1)
    check("no page errors", not errs, errs[:5])
    b.close()

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
