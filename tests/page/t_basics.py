import os, sys, time
from playwright.sync_api import sync_playwright
S = sys.argv[1]
os.makedirs(f"{S}/shots", exist_ok=True); fails = []
def check(name, cond, detail=""):
    print(("ok    " if cond else "FAIL  ") + name + (f"   ({detail})" if detail and not cond else "")); fails.append(name) if not cond else None
# Behind a proxy (a cloud workspace), the browser has to use it for everything but Avy.
PROXY = [f"--proxy-server={os.environ['HTTPS_PROXY']}", "--proxy-bypass-list=localhost;127.0.0.1"] if os.environ.get("HTTPS_PROXY") else []
with sync_playwright() as p:
    b = p.chromium.launch(args=[*PROXY])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8000"); time.sleep(2)
    pg.click("#input"); pg.keyboard.type("show me some markdown please"); pg.keyboard.press("Enter")
    time.sleep(1); t0 = time.time()
    while pg.evaluate("document.getElementById('chat').classList.contains('busy')") and time.time() - t0 < 60: time.sleep(0.2)
    html = pg.evaluate("[...document.querySelectorAll('.line.avy')].pop().innerHTML")
    check("markdown renders: code box, bold, list, link", ".codebox" not in html and "codebox" in html and "<b>" in html and "•" in html and "<a href" in html, html[:300])
    check("html inside a reply is escaped", "&lt;b&gt;not html&lt;/b&gt;" in html)
    pg.click("#openKeys"); time.sleep(0.5)
    check("the keys panel opens", pg.is_visible("#keys"))
    pg.click("#closeKeys"); time.sleep(0.3)
    check("...and closes", not pg.is_visible("#keys"))
    pg.click(".sys-row[data-name=window]"); time.sleep(0.4)
    check("a system card row opens its options", pg.is_visible("#menu"))
    pg.keyboard.press("Escape"); time.sleep(0.2)
    pg.set_viewport_size({"width": 390, "height": 844}); time.sleep(0.6)
    check("phone width: nothing scrolls sideways", pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"),
          pg.evaluate("document.documentElement.scrollWidth"))
    pg.screenshot(path=f"{S}/shots/v2-phone.png", full_page=True)
    check("no page errors", not errs, errs)
    b.close()
print(f"\n{len(fails)} failed")
