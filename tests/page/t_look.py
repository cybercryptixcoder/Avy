"""The look: light and dark themes (every surface readable, hovers included), her thinking folded under a reply
(live and after a reload), the theme toggle and /theme:, and the sounds (each interaction makes one, nothing errors).
Screenshots of both themes land in <work>/shots so they can be looked at by eye too."""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True); fails = []
def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({detail})" if detail and not cond else "")); fails.append(name) if not cond else None
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []

def setting(name, value):
    req = urllib.request.Request("http://localhost:8000/api/settings", data=json.dumps({"name": name, "value": value}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

from audit import CONTRAST  # every visible text's contrast over what it sits on (audit.py)

with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # spy on the sounds the page asks for (the synth still runs; headless has no speakers), on every load
    pg.add_init_script("window.__sounds = []; addEventListener('DOMContentLoaded', () => { const s = window.sound; "
                       "window.sound = (n, o) => { window.__sounds.push(n); return s(n, o); }; })")
    pg.goto("http://localhost:8000"); time.sleep(2)

    def send(text, wait=60):
        pg.click("#input"); pg.keyboard.type(text); pg.keyboard.press("Enter"); time.sleep(0.8); t0 = time.time()
        while pg.evaluate("document.getElementById('chat').classList.contains('busy')") and time.time() - t0 < wait: time.sleep(0.2)

    # --- thinking, folded under the reply -------------------------------------------------------------------
    send("hello, just checking in")
    check("thinking off: no thinking block", pg.locator(".line.thought").count() == 0)
    setting("thinking", "high"); pg.reload(); time.sleep(2)
    send("think about this one please")
    heads = pg.locator(".line.thought .thought-head")
    check("thinking on: a folded thinking block above the reply", heads.count() == 1 and "thought for" in heads.first.inner_text(), heads.count())
    check("...folded by default", pg.locator(".line.thought .thought-body").first.is_hidden())
    heads.first.click(); time.sleep(0.3)
    body = pg.locator(".line.thought .thought-body").first
    check("...opens on click and shows what she thought", body.is_visible() and "think about this" in body.inner_text(), body.inner_text()[:80])
    check("...and says so to screen readers", heads.first.get_attribute("aria-expanded") == "true")
    pg.screenshot(path=f"{S}/shots/look-light-thinking.png")
    pg.reload(); time.sleep(2)
    check("after a reload, the thinking is still there (saved with the reply)", pg.locator(".line.thought .thought-head").count() == 1
          and "thought for" in pg.locator(".line.thought .thought-head").first.inner_text())
    log = json.loads(urllib.request.urlopen("http://localhost:8000/api/log?limit=10").read())
    replies = [m for m in log["messages"] if m["role"] == "assistant"]
    check("the log keeps it next to the reply (meta.thought, and the reasoning itself)", replies[-1]["meta"].get("thought") and
          "think about" in replies[-1].get("thinking", {}).get("text", ""), replies[-1].get("thinking"))
    check("the reply without thinking has none", not replies[0].get("thinking"))
    exported = urllib.request.urlopen("http://localhost:8000/api/export?what=conversation&format=md").read().decode()
    check("the Markdown export folds it in a <details>", "<details><summary>thought" in exported)
    setting("thinking", "none")
    check("thinking levels offered: none, low, high, max", setting("thinking", "none")["schema"]["thinking"]["options"] == ["none", "low", "high", "max"])
    check("an old level still works and means DeepSeek's: medium -> high", setting("thinking", "medium")["values"]["thinking"] == "high")
    setting("thinking", "none")

    # --- light and dark ----------------------------------------------------------------------------------------
    def tour(theme):
        """Open each surface, measure contrast, take screenshots. Returns the low-contrast items found."""
        found = {}
        def measure(where):
            for x in pg.evaluate(CONTRAST, 3.0):
                found.setdefault((x["what"], x["text"]), (x["r"], where))
        pg.reload(); time.sleep(2)
        measure("page")
        pg.screenshot(path=f"{S}/shots/look-{theme}.png")
        pg.click(".sys-row[data-name=window]"); time.sleep(0.3); pg.hover("#menu li:nth-child(3)"); measure("menu")
        pg.screenshot(path=f"{S}/shots/look-{theme}-menu.png"); pg.keyboard.press("Escape"); time.sleep(0.2)
        for sel in ["#openMemory", "#openGlass", "#themeBtn", "#attach", "#send", ".sys-row[data-name=recall]", ".line.thought .thought-head"]:
            if pg.locator(sel).count():
                pg.hover(sel); time.sleep(0.15); measure("hover " + sel)
        pg.click("#input"); pg.keyboard.type("/th"); time.sleep(0.4); measure("commands")
        pg.screenshot(path=f"{S}/shots/look-{theme}-commands.png")
        pg.keyboard.press("Escape"); time.sleep(0.2)
        pg.click("#openMemory"); time.sleep(1.2); measure("inspector")
        rows = pg.locator(".insp .row")
        if rows.count():
            rows.first.hover(); time.sleep(0.15); measure("inspector hover")
        pg.screenshot(path=f"{S}/shots/look-{theme}-inspector.png")
        pg.click("#inspClose"); time.sleep(0.3)
        pg.click("#openKeys"); time.sleep(0.4); measure("keys"); pg.screenshot(path=f"{S}/shots/look-{theme}-keys.png")
        pg.click("#closeKeys"); time.sleep(0.3)
        return found

    light = tour("light")
    setting("theme", "dark")
    dark = tour("dark")
    check("dark: the page really is dark", pg.evaluate("getComputedStyle(document.body).backgroundColor") not in ("rgb(238, 220, 194)",),
          pg.evaluate("getComputedStyle(document.body).backgroundColor"))
    worst = sorted(((r, w, k) for k, (r, w) in dark.items()), key=lambda x: x[0])
    floor_light = min([r for r, _ in light.values()] or [9])
    print(f"      (light: {len(light)} quiet texts under 3:1, lowest {floor_light}; dark: {len(dark)}, lowest {worst[0][0] if worst else '-'})")
    for r, w, k in worst[:12]:
        print(f"      dark {r:>5}  {w:<22} {k[0][:60]}  \"{k[1]}\"")
    check("dark: nothing is harder to read than the quietest text in light", not worst or worst[0][0] >= min(2.0, floor_light) - 0.05,
          worst[:3])
    check("dark: nothing anywhere is nearly invisible (every text at least 2:1, hovers and menus included)",
          all(r >= 2.0 for r, _, _ in worst), worst[:3])
    pg.click("#themeBtn"); time.sleep(0.7)
    check("the toggle switches to light", pg.evaluate("document.documentElement.dataset.theme") == "light")
    pg.click("#themeBtn"); time.sleep(0.7)
    check("...and back to dark, remembered by the server", json.loads(urllib.request.urlopen("http://localhost:8000/api/settings").read())["values"]["theme"] == "dark")
    pg.reload(); time.sleep(0.3)
    check("dark from the first frame after a reload (no light flash)", pg.evaluate("document.documentElement.dataset.theme") == "dark")
    time.sleep(1.5)
    # incognito in dark turns the conversation light (inside out, like light mode's dark incognito)
    pg.click("#input"); pg.keyboard.type("/incognito"); pg.keyboard.press("Enter"); time.sleep(1.5)
    check("dark incognito: the conversation turns inside out (light)", pg.evaluate("getComputedStyle(document.getElementById('chat')).backgroundColor") in ("rgb(233, 220, 199)",),
          pg.evaluate("getComputedStyle(document.getElementById('chat')).backgroundColor"))
    inc = [x for x in pg.evaluate(CONTRAST, 2.0) if "chat" in x["what"] or "line" in x["what"]]
    check("dark incognito: readable", not inc, inc[:3])
    pg.screenshot(path=f"{S}/shots/look-dark-incognito.png")
    pg.click("#endIncognito"); time.sleep(1)
    pg.set_viewport_size({"width": 390, "height": 844}); time.sleep(0.6)
    pg.screenshot(path=f"{S}/shots/look-dark-phone.png", full_page=True)
    pg.set_viewport_size({"width": 1440, "height": 900}); time.sleep(0.4)

    # --- sounds ------------------------------------------------------------------------------------------------
    pg.evaluate("window.__sounds = []")
    send("one more")
    heard = pg.evaluate("window.__sounds")
    check("sending makes a sound, and so does the reply landing", "send" in heard and "receive" in heard, heard)
    pg.evaluate("window.__sounds = []")
    pg.click("#attach"); time.sleep(0.2); pg.keyboard.press("Escape")
    pg.click(".sys-row[data-name=recall]"); time.sleep(0.2); pg.keyboard.press("Escape")
    check("buttons and the system card click", pg.evaluate("window.__sounds").count("click") >= 2, pg.evaluate("window.__sounds"))
    check("the synthesizer started without errors", pg.evaluate("!!(sfx.ctx)") and not errs, errs)
    setting("sounds", "off"); pg.reload(); time.sleep(1.5)
    pg.evaluate("() => { window.__made = 0; const s = SOUNDS.click; SOUNDS.click = (...a) => { window.__made++; return s(...a); }; }")
    pg.click(".sys-row[data-name=recall]"); time.sleep(0.2); pg.keyboard.press("Escape")
    check("/sounds: off is silent", pg.evaluate("window.__made") == 0)
    setting("sounds", "on"); setting("theme", "auto")
    check("no page errors", not errs, errs)
    b.close()
print(f"\n{len(fails)} failed")
