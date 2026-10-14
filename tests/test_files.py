"""Offline checks of attaching files (files.py) and what the model is given (app.briefing): every kind
of file is made here, uploaded the way the page does it, read, and put in a message. No network.
Pictures need Pillow; PDFs pypdf (or pdftotext); video PyAV. Whatever is missing is skipped and said.

    python3 tests/test_files.py
"""

import base64
import io
import json
import os
import struct
import sys
import tarfile
import tempfile
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AVY_NO_BROWSER", "1")

import files  # noqa: E402

fails, skipped = [], []


def ok(name, condition, detail=""):
    print(("ok    " if condition else "FAIL  ") + name + ("" if condition else f"   ({detail})"))
    if not condition:
        fails.append(name)


def skip(name, why):
    print(f"skip  {name}   ({why})")
    skipped.append(name)


tmp = Path(tempfile.mkdtemp())
FOLDER = tmp / "files"
made = tmp / "made"
made.mkdir()


def attach(name, data, mime=""):
    """Upload bytes the way the page does (a stream of the body), and wait for the reading."""
    record = files.save(io.BytesIO(data), len(data), name, mime, FOLDER)
    return files.wait(record["id"], [FOLDER], seconds=120)


def text(record):
    return files.text_of(record["id"], [FOLDER])


# --- 1. text of every kind ------------------------------------------------------------------------
r = attach("notes.md", "# Basil pot\n\nThe pump is **quiet**.\n".encode())
ok("Markdown is read as it is", r["status"] == "ready" and r["kind"] == "text" and "The pump is **quiet**." in text(r), r)
r = attach("plan.py", b"def water(ml):\n    return ml * 2\n")
ok("code is read as it is", r["kind"] == "text" and "return ml * 2" in text(r) and r["what"] == "2 lines", r)
blob = json.dumps({"plants": [{"name": f"basil {i}", "ml": i * 10} for i in range(400)]}, separators=(",", ":"))
r = attach("plants.json", blob.encode())
ok("minified JSON is laid out so it can be read", r["kind"] == "text" and '\n "plants": [' in text(r) and text(r).count("\n") > 400)
r = attach("old.txt", "caf\xe9 cr\xe8me".encode("cp1252"))
ok("text in an old Windows encoding is read", "café crème" in text(r), text(r))
r = attach("utf16.txt", "hello in UTF-16".encode("utf-16"))
ok("...and UTF-16", "hello in UTF-16" in text(r), text(r))
r = attach("prices.csv", b"item,price\npump,12\nsensor,4\n", "text/csv")
ok("CSV is read as rows", "pump,12" in text(r))
nb = {"cells": [{"cell_type": "markdown", "source": ["# Watering\n"]},
                {"cell_type": "code", "source": ["print(2 + 2)"], "outputs": [{"output_type": "stream", "text": ["4\n"]}]}]}
r = attach("analysis.ipynb", json.dumps(nb).encode())
ok("a notebook: its cells and their output", r["kind"] == "notebook" and "print(2 + 2)" in text(r) and "output:\n4" in text(r), text(r))
page = b"<!doctype html><html><head><title>Basil care</title><style>p{color:red}</style><script>alert(1)</script></head>" \
       b"<body><h1>Watering</h1><p>Water every <b>two</b> days.</p><ul><li>morning</li></ul></body></html>"
r = attach("care.html", page)
ok("a web page: its text, not its code", r["kind"] == "html" and "Water every two days." in text(r) and "alert" not in text(r)
   and "color:red" not in text(r) and "# Basil care" in text(r), text(r))
r = attach("letter.rtf", rb"{\rtf1\ansi{\fonttbl{\f0 Arial;}}\f0 Dear Maya,\par the caf\'e9 opens at nine.\par}")
ok("RTF: its text", r["kind"] == "rtf" and "Dear Maya," in text(r) and "café opens at nine." in text(r), text(r))
big = ("line of a big log file\n" * 200_000).encode()
r = attach("big.log", big)
ok("a big text file is kept whole, and its text is read up to a limit", r["size"] == len(big) and len(text(r)) <= files.STORED_CHARS
   and (FOLDER / r["id"] / "big.log").stat().st_size == len(big))


# --- 2. office documents ------------------------------------------------------------------------------
def office(members):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, body in members.items():
            z.writestr(name, body)
    return out.getvalue()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
docx = office({"[Content_Types].xml": "<Types/>", "word/document.xml":
    f'<w:document {W}><w:body>'
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Pump plan</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>Use a peristaltic pump.</w:t></w:r><w:r><w:tab/><w:t>Quiet.</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr><w:r><w:t>buy tubing</w:t></w:r></w:p>'
    '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>part</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>cost</w:t></w:r></w:p></w:tc></w:tr>'
    '<w:tr><w:tc><w:p><w:r><w:t>pump</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>$12</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    '</w:body></w:document>'})
r = attach("plan.docx", docx)
ok("Word: headings, paragraphs, lists and tables", r["kind"] == "docx" and "# Pump plan" in text(r) and "Use a peristaltic pump.\tQuiet." in text(r)
   and "- buy tubing" in text(r) and "pump | $12" in text(r), text(r))
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
xlsx = office({"[Content_Types].xml": "<Types/>",
               "xl/workbook.xml": f'<workbook {S}><sheets><sheet name="Budget" sheetId="1" r:id="rId1"/></sheets></workbook>',
               "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                             '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
               "xl/sharedStrings.xml": f'<sst {S}><si><t>item</t></si><si><t>pump</t></si><si><r><t>sen</t></r><r><t>sor</t></r></si></sst>',
               "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData>'
                   '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>note</t></is></c></row>'
                   '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>12</v></c></row>'
                   '<row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3"><v>4.5</v></c><c r="C3" t="b"><v>1</v></c></row>'
                   '</sheetData></worksheet>'})
r = attach("budget.xlsx", xlsx)
ok("Excel: every sheet, as rows, with gaps kept", r["kind"] == "xlsx" and "## sheet: Budget" in text(r) and "item\t\tnote" in text(r)
   and "pump\t12" in text(r) and "sensor\t4.5\tTRUE" in text(r), text(r))
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
slide = lambda words: f'<p:sld {A}><p:cSld><p:spTree>' + "".join(f"<p:sp><p:txBody><a:p><a:r><a:t>{w}</a:t></a:r></a:p></p:txBody></p:sp>" for w in words) + "</p:spTree></p:cSld></p:sld>"
pptx = office({"[Content_Types].xml": "<Types/>", "ppt/presentation.xml": f"<p:presentation {A}/>",
               "ppt/slides/slide1.xml": slide(["Self-watering pot", "for basil"]), "ppt/slides/slide2.xml": slide(["Parts"]),
               "ppt/slides/slide10.xml": slide(["Thanks"]),
               "ppt/notesSlides/notesSlide2.xml": f'<p:notes {A}><a:p><a:r><a:t>mention the pump</a:t></a:r></a:p></p:notes>'})
r = attach("pitch.pptx", pptx)
t = text(r)
ok("PowerPoint: slides in order, with their notes", r["kind"] == "pptx" and t.index("slide 1 ---") < t.index("slide 2 ---") < t.index("slide 10 ---")
   and "Self-watering pot\nfor basil" in t and "notes: mention the pump" in t, t)
odt = office({"mimetype": "application/vnd.oasis.opendocument.text", "content.xml":
    '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text>'
    '<text:h>Diary</text:h><text:p>The basil sprouted.</text:p></office:text></office:body></office:document-content>'})
r = attach("diary.odt", odt)
ok("OpenDocument: its text", r["kind"] == "odf" and "# Diary" in text(r) and "The basil sprouted." in text(r), text(r))
epub = office({"mimetype": "application/epub+zip",
               "META-INF/container.xml": '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>',
               "OEBPS/book.opf": '<package><manifest><item id="c2" href="two.xhtml"/><item id="c1" href="one.xhtml"/></manifest>'
                                 '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>',
               "OEBPS/one.xhtml": "<html><body><p>Chapter one: seeds.</p></body></html>",
               "OEBPS/two.xhtml": "<html><body><p>Chapter two: water.</p></body></html>"})
r = attach("garden.epub", epub)
ok("EPUB: its chapters, in reading order", r["kind"] == "epub" and text(r).index("seeds") < text(r).index("water"), text(r))


# --- 3. PDF ---------------------------------------------------------------------------------------------
def pdf(lines):
    """A small real PDF with a line of text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for line in lines:
        stream = f"BT /F1 18 Tf 72 720 Td ({line}) Tj ET".encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{body}\nendobj\n".encode())
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for o in offsets:
        out.write(f"{o:010} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


try:
    import pypdf  # noqa: F401
    have_pdf = True
except ImportError:
    import shutil
    have_pdf = bool(shutil.which("pdftotext"))
if have_pdf:
    r = attach("manual.pdf", pdf(["The pump needs five volts and a relay to switch it on and off safely every time."] * 2 +
                                 ["Page three says to water the basil in the morning before the sun is strong."]))
    ok("PDF: its text, page by page", r["kind"] == "pdf" and "--- page 3 ---" in text(r) and "water the basil in the morning" in text(r)
       and r["what"].startswith("PDF, 3 pages"), (r, text(r)[:300]))
else:
    skip("PDF text", "neither pypdf nor pdftotext is installed")

# --- 4. pictures, audio, video ---------------------------------------------------------------------------
try:
    from PIL import Image
    have_pil = True
except ImportError:
    have_pil = False
if have_pil:
    im = Image.new("RGB", (4000, 3000), "red")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    r = attach("plant.png", buf.getvalue(), "image/png")
    view = sorted((FOLDER / r["id"] / "view").glob("*.jpg"))
    ok("a picture is kept as it came, and a smaller copy is made for the model to look at",
       r["kind"] == "image" and r["pictures"] == 1 and r["what"] == "picture, 4000×3000"
       and max(Image.open(view[0]).size) == files.PICTURE_SIDE and (FOLDER / r["id"] / "plant.png").read_bytes() == buf.getvalue(), r)
    rgba = Image.new("RGBA", (50, 50), (0, 0, 255, 0))
    buf = io.BytesIO()
    rgba.save(buf, "PNG")
    r = attach("clear.png", buf.getvalue())
    ok("...a see-through picture gets a white background", r["status"] == "ready"
       and Image.open(sorted((FOLDER / r["id"] / "view").glob("*.jpg"))[0]).getpixel((5, 5))[0] > 240, r)
    buf = io.BytesIO()
    Image.new("RGB", (30, 20), "green").save(buf, "JPEG")
    r = attach("IMG_0001", buf.getvalue())
    ok("...even with no name to go by (from its first bytes)", r["kind"] == "image" and r["pictures"] == 1, r)
else:
    skip("pictures", "Pillow isn't installed")
r = attach("broken.png", b"\x89PNG\r\n\x1a\nnot really a png")
ok("a picture that can't be opened is kept, and says why", r["status"] == "problem" and "couldn't" in r["what"] or "Pillow" in r["what"], r)

sound = io.BytesIO()
with wave.open(sound, "wb") as w:
    w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
    w.writeframes(b"".join(struct.pack("<h", 0) for _ in range(16000)))
files.hooks["transcribe"] = None
r = attach("memo.wav", sound.getvalue())
ok("audio without the speech model: kept, and says what's needed", r["kind"] == "audio" and r["status"] == "problem"
   and "requirements-voice" in r["what"], r)
heard = []
files.hooks["transcribe"] = lambda path: heard.append(path) or ("[0:00] water the basil at seven", 1.0)
r = attach("memo.wav", sound.getvalue())
ok("audio: what's said, with times", r["kind"] == "audio" and r["status"] == "ready" and "[0:00] water the basil at seven" in text(r)
   and "transcribed" in r["what"], r)

try:
    import av
    import numpy as np
    clip = made / "clip.mp4"
    with av.open(str(clip), "w") as out:
        stream = out.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 320, 240, "yuv420p"
        for i in range(200):                                       # 20 seconds, getting brighter
            frame = av.VideoFrame.from_ndarray(np.full((240, 320, 3), min(255, i), np.uint8), format="rgb24")
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    r = attach("clip.mp4", clip.read_bytes(), "video/mp4")
    ok("video: frames to look at, spread over it (and no sound: said so)", r["kind"] == "video" and r["status"] == "ready"
       and r["pictures"] == 3 and "(It has no sound.)" in text(r) and "taken at 0:03, 0:10, 0:16" in text(r), (r, text(r)))
except ImportError:
    skip("video", "PyAV isn't installed (it comes with the voice packages)")
except Exception as e:
    skip("video", f"couldn't make a test video here ({e})")

# --- 5. archives, exports, anything else ---------------------------------------------------------------
r = attach("project.zip", office({"src/main.py": "print('hi')\n", "README.md": "# Pot\n", "logo.bin": bytes(range(256)) * 4}))
ok("a zip: what's inside, and the text of its small text files", r["kind"] == "archive" and "3 files" in r["what"]
   and "src/main.py" in text(r) and "--- README.md ---\n# Pot" in text(r) and "logo.bin  (1.0 KB)" in text(r), text(r))
tgz = io.BytesIO()
with tarfile.open(fileobj=tgz, mode="w:gz") as t:
    data = b"notes inside a tarball\n"
    info = tarfile.TarInfo("notes.txt")
    info.size = len(data)
    t.addfile(info, io.BytesIO(data))
r = attach("backup.tar.gz", tgz.getvalue())
ok("a .tar.gz: the same", r["kind"] == "archive" and "notes inside a tarball" in text(r), (r, text(r)))
export = {"conversations.json": [{"uuid": "c1", "name": "x", "chat_messages": [
    {"uuid": "m1", "sender": "human", "created_at": "2025-01-01T00:00:00Z", "text": "hi", "content": [{"type": "text", "text": "hi"}]},
    {"uuid": "m2", "sender": "assistant", "created_at": "2025-01-01T00:00:05Z", "text": "hello", "content": [{"type": "text", "text": "hello"}]}]}]}
r = attach("combined_export.json", json.dumps(export).encode())
ok("a Claude export is recognized and counted, never read in", r["kind"] == "claude-export" and r["what"] == "Claude export: 1 conversations, 2 messages"
   and r["chars"] == 0, r)
r = attach("data-2026.zip", office({"conversations.json": json.dumps(export["conversations.json"]), "users.json": "[]"}))
ok("...the zip claude.ai emails too", r["kind"] == "claude-export", r)
r = attach("firmware.bin", os.urandom(5000))
ok("anything else is kept, and known by name and size", r["kind"] == "binary" and r["status"] == "ready" and "can't read" in r["what"], r)
r = attach("../../etc/passwd", b"x")
ok("a file's name can't reach outside its folder", r["name"] == "passwd" and (FOLDER / r["id"] / "passwd").exists())
ok("ids can't be used to reach other folders", files.info("../files", [FOLDER]) is None and files.find("f1/../../x", [FOLDER]) is None)
ok("every file is listed, newest first", len(files.listing([FOLDER])) >= 25 and files.listing([FOLDER])[0]["name"] == "passwd")

# --- 6. what the model is given --------------------------------------------------------------------------
notes = attach("notes.md", b"# Basil pot\n\nThe pump is quiet.\n")
blocks, pictures = files.for_model([notes], [FOLDER])
ok("a file goes in the message inside <file> tags", blocks.startswith('<file name="notes.md" kind="text"') and "The pump is quiet." in blocks
   and blocks.endswith("</file>") and not pictures, blocks)
huge = attach("huge.txt", ("x" * 99 + "\n").encode() * 5000)
blocks, _ = files.for_model([huge], [FOLDER], budget=1000)
ok("...only as much as there's room for, saying how much was left out", "(…the first 1,000 of 500,000 characters" in blocks, blocks[-200:])
if have_pil:
    pic = next(f for f in files.listing([FOLDER]) if f["name"] == "plant.png")
    blocks, pictures = files.for_model([pic], [FOLDER])
    ok("a picture goes as an image the model can see", len(pictures) == 1 and pictures[0].startswith("data:image/jpeg;base64,")
       and "the picture follows this message" in blocks)
    ok("...unless pictures are turned off for it", files.for_model([pic], [FOLDER], pictures=False)[1] == [])
ok("a file that's gone says so", "no longer kept" in files.for_model([{"id": "f20990101-000000-abcd", "name": "gone.txt"}], [FOLDER])[0])

import app  # noqa: E402
import memory  # noqa: E402

app.FILES_DIR = FOLDER
app.MEMORIES["main"] = memory.Memory(tmp / "memory.db")
app.current_settings = lambda: {name: s["default"] for name, s in app.SETTINGS.items()}
msgs = app.briefing([], "(memory note)", "what's in these?", attached=[notes] + ([pic] if have_pil else []))
last = msgs[-1]["content"]
if have_pil:
    ok("the briefing: your message and its files, then the pictures", isinstance(last, list) and last[0]["type"] == "text"
       and last[0]["text"].startswith("what's in these?\n\n[attached]\n<file name=\"notes.md\"") and last[1]["type"] == "image_url", last[:1])
else:
    ok("the briefing: your message and its files", isinstance(last, str) and "<file name=\"notes.md\"" in last)
mem = app.MEMORIES["main"]
mem.add("user", "here's my plan", "text", {"files": [files.brief(notes)]})
mem.add("assistant", "Nice plan.", "text")
msgs = app.briefing(mem.window(20), "(memory note)", "and the pump?")
ok("a file sent earlier is still in front of the model while that message is in the window",
   "The pump is quiet." in json.dumps(msgs[1]["content"]) and msgs[-1]["content"] == "and the pump?", msgs[1])
room = {"chars": 10, "pictures": 0}
ok("...within the room left", "the first 10 of" in app.with_files("x", [notes], room) and room["chars"] < 10)
mem.add("user", "an old one", "claude", {"files": ["photo.jpg"], "attachments": [{"name": "a.txt", "chars": 5}]})
ok("imported messages, whose files are only names, don't trip the briefing",
   app.briefing(mem.window(20), "(memory note)", "hi")[-1]["content"] == "hi")
ok("the system prompt says how files arrive, and how to make one", "<file> tags" in app.SYSTEM_PROMPT and "save" in app.SYSTEM_PROMPT)

print(f"\n{len(fails)} failed" + (": " + ", ".join(fails) if fails else "") + (f"; skipped: {', '.join(skipped)}" if skipped else ""))
sys.exit(1 if fails else 0)
