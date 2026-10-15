"""Shared by the page tests: a contrast audit run inside the page."""

# Every visible piece of text: its color (with its own and its ancestors' opacity) over the background it sits on.
CONTRAST = r"""
(limit) => {
  const parse = (c) => {
    let m = c.match(/^rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    m = c.match(/^color\(srgb ([^)]+)\)/);
    if (m) { const p = m[1].split(/[\s\/]+/).filter(Boolean).map(Number); return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1]; }
    return [0, 0, 0, 0];
  };
  const over = (top, bottom) => { const a = top[3]; return [top[0] * a + bottom[0] * (1 - a), top[1] * a + bottom[1] * (1 - a), top[2] * a + bottom[2] * (1 - a), 1]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    if (!el.getClientRects().length || ["SCRIPT", "STYLE", "svg", "use", "CANVAS"].includes(el.tagName)) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const field = el.tagName === "INPUT" || el.tagName === "TEXTAREA";
    if (!own && !field) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || el.closest("[hidden], [aria-hidden=true], .typed textarea")) continue;
    const chain = []; for (let x = el; x; x = x.parentElement) chain.unshift(x);
    let bg = [255, 255, 255, 1], alpha = 1;
    for (const x of chain) { const s = getComputedStyle(x); bg = over(parse(s.backgroundColor), bg); alpha *= Number(s.opacity); }
    const fg = parse(cs.color); fg[3] *= alpha;
    const seen = over(fg, bg);
    const r = ratio(seen, bg);
    if (r < limit) out.push({ r: Math.round(r * 100) / 100, text: (el.innerText || el.value || el.placeholder || "").trim().slice(0, 50),
                              what: el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).join(".") : "") });
  }
  return out.sort((a, b) => a.r - b.r);
}
"""
