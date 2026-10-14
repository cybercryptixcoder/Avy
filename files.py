"""Files you give Avy: any kind at all. Each one is kept in data/files/<id>/ exactly as it came, then read
into what the model can use: text it can read, and pictures it can look at. A file that can't be read is
still kept, and Avy knows its name, type and size.

    record = save(stream, length, "notes.pdf", "application/pdf", folder)   # kept; read in the background
    record = info(record["id"], [folder])                                    # how the reading went
    blocks, pictures = for_model([record], budget)                           # what goes in the message

What gets read, and how (the packages are optional; without one, that kind is kept but not read):
  any kind of text           as it is: plain, Markdown, code, JSON, CSV, logs, subtitles... (any encoding)
  Jupyter notebooks          cells and their text output
  PDF                        its text (pypdf, or the pdftotext program); a scanned PDF's first pages as
                             pictures (the pdftoppm program)
  Word, Excel, PowerPoint    paragraphs and tables, every sheet as rows, every slide and its notes
                             (.docx .xlsx .pptx, and OpenDocument .odt .ods .odp)
  web pages, RTF, EPUB       their text
  pictures                   the model looks at them, shrunk to at most 1,568 pixels a side (Pillow)
  audio                      what's said, with times, by the speech model (needs voice installed)
  video                      what's said, plus up to 8 frames to look at (needs voice installed: PyAV)
  zip and tar archives       what's inside, and the text of the small text files in it
  a Claude data export       recognized (never read into a message): the page offers to import it
"""

import base64
import html.parser
import io
import json
import mimetypes
import re
import secrets
import shutil
import subprocess
import tarfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES = 8 * 1024 ** 3        # one upload, at most (8 GB)
STORED_CHARS = 2_000_000         # how much of a file's text is kept in text.txt
PER_FILE = 150_000               # the most of one file a message can carry (about 40,000 tokens)
PICTURE_SIDE = 1568              # pictures are shrunk to fit this square
FRAME_SIDE = 768                 # video frames, smaller
MAX_FRAMES = 8
SCAN_PAGES = 6                   # a scanned PDF: how many pages to show as pictures
ID = re.compile(r"^f\d{8}-\d{6}-[0-9a-f]{4}$")

hooks = {"transcribe": None}     # set by app.py: voice.transcribe_file(path) -> (text, seconds), if voice is installed
_heavy = threading.Semaphore(1)  # one transcription at a time: the speech model is big


# --- keeping a file ---------------------------------------------------------------------------------

def save(stream, length, name, mime, folder):
    """Copy an upload (length bytes from stream) into folder/<id>/, then read it in the background.
    Returns its record (status "reading" until the reading is done)."""
    folder = Path(folder)
    fid = datetime.now().strftime("f%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    home = folder / fid
    home.mkdir(parents=True)
    name = safe_name(name)
    left = length
    with open(home / name, "wb") as out:
        while left > 0:
            chunk = stream.read(min(1 << 20, left))
            if not chunk:
                break
            out.write(chunk)
            left -= len(chunk)
    record = {"id": fid, "name": name, "size": length - left, "mime": mime or mimetypes.guess_type(name)[0] or "",
              "at": datetime.now().astimezone().isoformat(timespec="seconds"), "status": "reading", "kind": "file",
              "what": "reading…", "chars": 0, "pictures": 0, "order": time.time_ns()}
    if left > 0:
        record.update(status="problem", what="the upload stopped partway")
    write_info(home, record)
    if record["status"] == "reading":
        threading.Thread(target=read_in_background, args=(home, record), daemon=True).start()
    return record


def safe_name(name):
    name = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    return name[:150] or "file"


def write_info(home, record):
    tmp = home / "info.json.part"
    tmp.write_text(json.dumps(record, indent=1))
    tmp.replace(home / "info.json")


def find(fid, folders):
    """The folder a file lives in (main or incognito), or None."""
    if not fid or not ID.match(str(fid)):
        return None
    for folder in folders:
        if folder and (Path(folder) / fid / "info.json").exists():
            return Path(folder) / fid
    return None


def info(fid, folders):
    home = find(fid, folders)
    return json.loads((home / "info.json").read_text()) if home else None


def original(fid, folders):
    """(path of the file as it came, its record), or (None, None)."""
    home = find(fid, folders)
    if not home:
        return None, None
    record = json.loads((home / "info.json").read_text())
    return home / record["name"], record


def text_of(fid, folders):
    home = find(fid, folders)
    return (home / "text.txt").read_text() if home and (home / "text.txt").exists() else ""


def listing(folders, limit=100):
    found = []
    for folder in folders:
        if folder and Path(folder).exists():
            for p in Path(folder).glob("f*/info.json"):
                try:
                    found.append(json.loads(p.read_text()))
                except (OSError, json.JSONDecodeError):
                    pass
    return sorted(found, key=lambda r: r.get("order") or 0, reverse=True)[:limit]


def brief(record):
    """What a message's meta keeps about a file it carried."""
    return {k: record.get(k) for k in ("id", "name", "kind", "size", "chars", "pictures", "what")}


# --- reading it -------------------------------------------------------------------------------------

def read_in_background(home, record):
    try:
        found = read(home / record["name"], home, record)
        text = found.pop("text", "") or ""
        if text:
            (home / "text.txt").write_text(text[:STORED_CHARS])
        record.update(found, status="problem" if found.get("problem") else "ready",
                      chars=len(text), pictures=len(list((home / "view").glob("*.jpg"))) if (home / "view").exists() else 0)
    except Exception as e:                       # a file that breaks a reader is still kept
        record.update(status="problem", problem=f"couldn't read it ({type(e).__name__}: {e})"[:300])
    if record["status"] == "problem":
        record["what"] = record.get("problem") or "couldn't read it"
    record["read_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_info(home, record)


def read(path, home, record):
    """{"kind", "what" (a few words for the chip), "text", maybe "problem", "details"}; pictures go in home/view/."""
    head = open(path, "rb").read(65536)
    ext = path.suffix.lower().lstrip(".")
    mime = record.get("mime") or ""
    kind = sniff(head, ext, mime, path)
    reader = READERS.get(kind)
    found = reader(path, home, head) if reader else {}
    found.setdefault("kind", kind)
    if not found.get("what"):
        found["what"] = describe(found, record)
    return found


def sniff(head, ext, mime, path):
    """What kind of file this is, from its first bytes, then its name, then its type."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return zip_kind(path, ext)
    if head[:3] == b"\xff\xd8\xff" or head.startswith(b"\x89PNG") or head[:4] in (b"GIF8",) or head[:2] == b"BM" \
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP") or head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"msf1", b"avif"):
            return "image"
        if brand in (b"M4A ", b"M4B "):
            return "audio"
        return "video" if has_video(path, ext) else "audio"
    if head[:4] == b"\x1a\x45\xdf\xa3" or (head[:4] == b"RIFF" and head[8:12] == b"AVI "):
        return "video" if has_video(path, ext) else "audio"
    if head[:4] in (b"OggS", b"fLaC") or head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") \
            or (head[:4] == b"RIFF" and head[8:12] == b"WAVE") or head[:4] == b"FORM":
        return "video" if head[:4] == b"OggS" and has_video(path, ext) else "audio"
    if head[:2] == b"\x1f\x8b" or head[:3] == b"BZh" or head[:6] == b"\xfd7zXZ\x00" or head[257:262] == b"ustar":
        return "archive"
    if head.lstrip()[:5] == b"{\\rtf":
        return "rtf"
    major = mime.split("/")[0]
    if ext in AUDIO_EXT or major == "audio":
        return "audio"
    if ext in VIDEO_EXT or major == "video":
        return "video"
    if looks_like_text(head):
        if ext in ("html", "htm", "xhtml") or head.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
            return "html"
        if ext == "ipynb":
            return "notebook"
        if is_claude_export_head(head):
            return "claude-export"
        return "text"
    if ext in ("heic", "heif", "avif") or major == "image":
        return "image"
    return "binary"


AUDIO_EXT = {"mp3", "m4a", "aac", "wav", "flac", "ogg", "oga", "opus", "wma", "aiff", "aif", "amr", "caf"}
VIDEO_EXT = {"mp4", "mov", "m4v", "mkv", "webm", "avi", "wmv", "flv", "3gp", "mpg", "mpeg", "ts", "mts", "ogv"}


def looks_like_text(head):
    if not head:
        return True
    if b"\x00" in head[:8192] and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    sample = head[:8192]
    for enc in ("utf-8", "utf-16"):
        try:
            sample.decode(enc)
            return True
        except UnicodeDecodeError as e:
            if enc == "utf-8" and e.start > len(sample) - 4:       # a character cut off at the end of the sample
                return True
    printable = sum(32 <= b < 127 or b in (9, 10, 13) or b >= 160 for b in sample)
    return printable / len(sample) > 0.9


def decode(data):
    """Bytes to text: UTF-8 (or UTF-16 with its mark), else Windows-1252, else Latin-1 (which never fails)."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        if e.start > len(data) - 4:                   # only a character cut off at the very end
            return data[:e.start].decode("utf-8-sig")
    try:
        return data.decode("cp1252")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def is_claude_export_head(head):
    text = head[:65536].decode("utf-8", errors="ignore")
    return '"chat_messages"' in text or '"conversations.json"' in text


def zip_kind(path, ext):
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except zipfile.BadZipFile:
        return "binary"
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    if "content.xml" in names and "mimetype" in names:
        return "odf"
    if "META-INF/container.xml" in names and (ext == "epub" or any(n.endswith(".opf") for n in names)):
        return "epub"
    if any(n.rsplit("/", 1)[-1] == "conversations.json" for n in names) or claude_export_inside(path, names):
        return "claude-export"
    return "archive"


def claude_export_inside(path, names):
    jsons = [n for n in names if n.lower().endswith(".json") and not n.startswith("__MACOSX")]
    if len(jsons) != 1:
        return False
    with zipfile.ZipFile(path) as z, z.open(jsons[0]) as f:
        return is_claude_export_head(f.read(65536))


# --- the readers ------------------------------------------------------------------------------------

def read_text(path, home, head):
    size = path.stat().st_size
    with open(path, "rb") as f:
        data = f.read(STORED_CHARS * 2)
    text = decode(data)
    ext = path.suffix.lower()
    if ext in (".json", ".geojson") and size < 5_000_000 and "\n" not in text[:5000] and len(text) > 5000:
        try:                                      # minified JSON: lay it out so it can be read
            text = json.dumps(json.loads(text), indent=1, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    lines = len(text.splitlines())
    partial = size > len(data)
    return {"text": text, "what": plural(lines, "line") + (f" (the first {fmt_size(len(data))} of {fmt_size(size)})" if partial else ""),
            "details": {"lines": lines, "partial": partial}}


def read_notebook(path, home, head):
    try:
        nb = json.loads(path.read_text(errors="replace"))
    except json.JSONDecodeError:
        return read_text(path, home, head)
    parts = []
    for i, cell in enumerate(nb.get("cells") or [], 1):
        source = "".join(cell.get("source") or [])
        parts.append(f"--- cell {i} ({cell.get('cell_type', 'code')}) ---\n{source}")
        for out in cell.get("outputs") or []:
            shown = out.get("text") or (out.get("data") or {}).get("text/plain") or ""
            if shown:
                parts.append("output:\n" + ("".join(shown) if isinstance(shown, list) else str(shown))[:4000])
    return {"kind": "notebook", "text": "\n\n".join(parts), "what": f"notebook, {len(nb.get('cells') or [])} cells"}


def read_pdf(path, home, head):
    text, pages = "", 0
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = len(reader.pages)
        text = "\n\n".join(f"--- page {i} ---\n{(p.extract_text() or '').strip()}" for i, p in enumerate(reader.pages, 1))
    except ImportError:
        if shutil.which("pdftotext"):
            done = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=300)
            text = done.stdout.decode(errors="replace")
            pages = text.count("\f") + 1
            text = "\n\n".join(f"--- page {i} ---\n{t.strip()}" for i, t in enumerate(text.split("\f"), 1) if t.strip())
        else:
            return {"text": "", "problem": "PDFs need pypdf to be read: python3 -m pip install pypdf"}
    except Exception as e:
        return {"text": "", "problem": f"couldn't read this PDF ({type(e).__name__})"}
    words = len(re.sub(r"--- page \d+ ---", "", text).split())
    scanned = pages and words < 20 * pages
    found = {"text": text if words else "", "details": {"pages": pages}}
    if scanned and shutil.which("pdftoppm"):          # pictures of pages without text: the model reads them by eye
        view = home / "view"
        view.mkdir(exist_ok=True)
        subprocess.run(["pdftoppm", "-jpeg", "-r", "110", "-l", str(SCAN_PAGES), "-scale-to", str(PICTURE_SIDE),
                        str(path), str(view / "page")], capture_output=True, timeout=300)
        shown = len(list(view.glob("*.jpg")))
        found["what"] = f"PDF, {plural(pages, 'page')}, scanned: {plural(shown, 'page')} shown as pictures"
    else:
        found["what"] = f"PDF, {plural(pages, 'page')}" + (", no text in it (scanned?)" if scanned else "")
    return found


def xml_root(z, name):
    with z.open(name) as f:
        return ElementTree.parse(f).getroot()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def read_docx(path, home, head):
    with zipfile.ZipFile(path) as z:
        body = xml_root(z, "word/document.xml")
    lines = []

    def paragraph(p):
        out = []
        for el in p.iter():
            t = local(el.tag)
            if t == "t" and el.text:
                out.append(el.text)
            elif t == "tab":
                out.append("\t")
            elif t in ("br", "cr"):
                out.append("\n")
        style = next((s.get(next(iter(s.attrib), "")) for s in p.iter() if local(s.tag) == "pStyle"), "") or ""
        text = "".join(out).strip()
        if text and style.lower().startswith(("heading", "title")):
            level = re.sub(r"\D", "", style) or "1"
            text = "#" * min(6, int(level)) + " " + text
        elif text and any(local(x.tag) == "numPr" for x in p.iter()):
            text = "- " + text
        return text

    for block in next((c for c in body if local(c.tag) == "body"), body):
        t = local(block.tag)
        if t == "p":
            lines.append(paragraph(block))
        elif t == "tbl":
            for row in (r for r in block.iter() if local(r.tag) == "tr"):
                cells = [" ".join(filter(None, (paragraph(p) for p in c.iter() if local(p.tag) == "p")))
                         for c in row if local(c.tag) == "tc"]
                lines.append(" | ".join(cells))
            lines.append("")
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return {"text": text, "what": f"Word document, {len(text.split()):,} words"}


def column_number(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref or "A").group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path, home, head):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in xml_root(z, "xl/sharedStrings.xml"):
                shared.append("".join(t.text or "" for t in si.iter() if local(t.tag) == "t"))
        book = xml_root(z, "xl/workbook.xml")
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in xml_root(z, "xl/_rels/workbook.xml.rels"):
                rels[r.get("Id")] = r.get("Target", "").lstrip("/").removeprefix("xl/")
        sheets = [(s.get("name"), rels.get(next((v for k, v in s.attrib.items() if local(k) == "id"), ""), ""))
                  for s in book.iter() if local(s.tag) == "sheet"]
        parts, total_rows = [], 0
        for i, (name, target) in enumerate(sheets, 1):
            member = "xl/" + target if target else f"xl/worksheets/sheet{i}.xml"
            if member not in names:
                continue
            rows = []
            with z.open(member) as f:
                for _, el in ElementTree.iterparse(f):
                    if local(el.tag) != "row":
                        continue
                    cells = {}
                    for c in el:
                        if local(c.tag) != "c":
                            continue
                        kind, value = c.get("t"), None
                        v = next((x.text for x in c if local(x.tag) == "v"), None)
                        if kind == "s" and v is not None:
                            value = shared[int(v)] if int(v) < len(shared) else ""
                        elif kind == "inlineStr":
                            value = "".join(t.text or "" for t in c.iter() if local(t.tag) == "t")
                        elif kind == "b":
                            value = "TRUE" if v == "1" else "FALSE"
                        else:
                            value = v
                        if value not in (None, ""):
                            cells[column_number(c.get("r"))] = str(value).replace("\t", " ").replace("\n", " ")
                    el.clear()
                    if cells:
                        rows.append("\t".join(cells.get(k, "") for k in range(max(cells) + 1)))
                    if len(rows) >= 20_000:
                        break
            total_rows += len(rows)
            parts.append(f"## sheet: {name} ({plural(len(rows), 'row')}, tab-separated)\n" + "\n".join(rows))
    return {"text": "\n\n".join(parts), "what": f"spreadsheet, {plural(len(parts), 'sheet')}, {total_rows:,} rows"}


def read_pptx(path, home, head):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        number = lambda n: int(re.search(r"(\d+)\.xml$", n).group(1))
        slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=number)
        notes = {number(n): n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)}
        parts = []
        for s in slides:
            root = xml_root(z, s)
            paras = ["".join(t.text or "" for t in p.iter() if local(t.tag) == "t") for p in root.iter() if local(p.tag) == "p"]
            block = f"--- slide {number(s)} ---\n" + "\n".join(x for x in paras if x.strip())
            if number(s) in notes:
                said = [("".join(t.text or "" for t in p.iter() if local(t.tag) == "t")) for p in xml_root(z, notes[number(s)]).iter()
                        if local(p.tag) == "p"]
                said = [x for x in said if x.strip() and not x.strip().isdigit()]
                if said:
                    block += "\nnotes: " + " ".join(said)
            parts.append(block)
    return {"text": "\n\n".join(parts), "what": f"slides, {plural(len(slides), 'slide')}"}


def read_odf(path, home, head):
    with zipfile.ZipFile(path) as z:
        root = xml_root(z, "content.xml")
        mime = z.read("mimetype").decode(errors="ignore") if "mimetype" in z.namelist() else ""
    lines = []
    for el in root.iter():
        t = local(el.tag)
        if t in ("h", "p"):
            text = "".join(el.itertext()).strip()
            if text:
                lines.append(("# " if t == "h" else "") + text)
        elif t == "table-row":
            lines.append(" | ".join("".join(c.itertext()).strip() for c in el if local(c.tag) == "table-cell"))
    seen, out = set(), []
    for line in lines:                                  # rows also contain their paragraphs; keep each once
        if line not in seen or not line:
            out.append(line)
        seen.add(line)
    what = {"spreadsheet": "spreadsheet", "presentation": "slides"}.get(mime.rsplit(".", 1)[-1], "document")
    return {"text": "\n".join(out), "what": f"OpenDocument {what}"}


class TextOfHtml(html.parser.HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header", "footer",
              "blockquote", "pre", "table", "ul", "ol", "dt", "dd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title = [], 0, ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCKS:
            self.out.append("\n")
        if tag == "li":
            self.out.append("- ")
        if tag in ("h1", "h2", "h3"):
            self.out.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCKS:
            self.out.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)

    def text(self):
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.out))
        return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def html_text(markup):
    parser = TextOfHtml()
    parser.feed(markup)
    parser.close()
    return parser.text(), parser.title.strip()


def read_html(path, home, head):
    text, title = html_text(decode(path.read_bytes()[:STORED_CHARS * 2]))
    return {"text": (f"# {title}\n\n" if title else "") + text, "what": "web page" + (f": {title[:60]}" if title else "")}


def read_rtf(path, home, head):
    raw = decode(path.read_bytes()[:STORED_CHARS * 2])
    raw = re.sub(r"\{\\\*[^{}]*\}", "", raw)
    raw = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", errors="replace"), raw)
    raw = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), raw)
    raw = re.sub(r"\\(par|line)\b ?", "\n", raw)
    raw = re.sub(r"\\tab\b ?", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    text = re.sub(r"[{}]", "", raw)
    return {"text": re.sub(r"\n{3,}", "\n\n", text).strip(), "what": "RTF document"}


def read_epub(path, home, head):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        order = []
        try:
            container = xml_root(z, "META-INF/container.xml")
            opf = next(e.get("full-path") for e in container.iter() if local(e.tag) == "rootfile")
            pkg = xml_root(z, opf)
            base = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
            items = {e.get("id"): base + e.get("href", "") for e in pkg.iter() if local(e.tag) == "item"}
            order = [items[e.get("idref")] for e in pkg.iter() if local(e.tag) == "itemref" and e.get("idref") in items]
        except (KeyError, StopIteration, ElementTree.ParseError):
            pass
        order = [n for n in order if n in names] or sorted(n for n in names if n.endswith((".xhtml", ".html", ".htm")))
        parts = [html_text(z.read(n).decode("utf-8", errors="replace"))[0] for n in order]
    text = "\n\n".join(p for p in parts if p)
    return {"text": text, "what": f"book, {len(text.split()):,} words"}


def picture(source, out, side):
    """Save a picture for the model: upright, RGB, fit in side×side, JPEG. Returns (width, height) or None."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    with Image.open(source) as im:
        size = im.size
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            back = Image.new("RGB", im.size, "white")
            back.paste(im, mask=im.split()[-1])
            im = back
        else:
            im = im.convert("RGB")
        im.thumbnail((side, side))
        im.save(out, "JPEG", quality=85)
    return size


def read_image(path, home, head):
    view = home / "view"
    view.mkdir(exist_ok=True)
    try:
        width, height = picture(path, view / "1.jpg", PICTURE_SIDE)
        return {"text": "", "what": f"picture, {width}×{height}", "details": {"width": width, "height": height}}
    except ImportError:
        if head[:3] == b"\xff\xd8\xff" and path.stat().st_size < 4_000_000:     # a JPEG can go as it is
            shutil.copy(path, view / "1.jpg")
            return {"text": "", "what": "picture"}
        return {"text": "", "problem": "pictures need Pillow to be shown to the model: python3 -m pip install Pillow"}
    except Exception as e:
        hint = " (HEIC pictures need: python3 -m pip install pillow-heif)" if path.suffix.lower() in (".heic", ".heif") else ""
        return {"text": "", "problem": f"couldn't open this picture ({type(e).__name__}){hint}"}


def media_facts(path):
    """(seconds, has video, has audio, width, height) via PyAV, or Nones without it."""
    try:
        import av
    except ImportError:
        return None, None, None, None, None
    try:
        with av.open(str(path)) as c:
            seconds = (c.duration or 0) / 1_000_000 or None
            video = next(iter(c.streams.video), None)
            audio = next(iter(c.streams.audio), None)
            return seconds, video is not None, audio is not None, video.width if video else None, video.height if video else None
    except Exception:
        return None, None, None, None, None


def has_video(path, ext):
    _, video, _, _, _ = media_facts(path)
    return video if video is not None else ext in VIDEO_EXT


def transcript(path):
    """(text, problem): what's said in a recording, if the speech model is there."""
    if not hooks["transcribe"]:
        return "", "listening to it needs the voice packages: python3 -m pip install -r requirements-voice.txt"
    with _heavy:
        try:
            text, _ = hooks["transcribe"](path)
            return text, None
        except Exception as e:
            return "", f"couldn't transcribe it ({type(e).__name__}: {str(e)[:120]})"


def read_audio(path, home, head):
    seconds, _, _, _, _ = media_facts(path)
    text, problem = transcript(path)
    length = f", {clock(seconds)}" if seconds else ""
    if problem:
        return {"text": "", "problem": problem, "what": f"audio{length}"}
    return {"text": text, "what": f"audio{length}, " + ("transcribed" if text.strip() else "nothing said in it"),
            "details": {"seconds": seconds}}


def read_video(path, home, head):
    seconds, video, audio, width, height = media_facts(path)
    view = home / "view"
    view.mkdir(exist_ok=True)
    times = frames(path, view, seconds)
    said, problem = transcript(path) if audio is not False else ("", None)
    lines = [f"A video, {clock(seconds) if seconds else 'length unknown'}" + (f", {width}×{height}" if width else "") + "."]
    if times:
        lines.append(f"{plural(len(times), 'frame')} you can see come with it, taken at " + ", ".join(clock(t) for t in times) + ".")
    if said.strip():
        lines.append("What's said in it, with times:\n" + said)
    elif problem:
        lines.append(f"(What's said in it couldn't be heard: {problem}.)")
    elif audio is False:
        lines.append("(It has no sound.)")
    if times or said.strip():
        what = f"video, {clock(seconds) if seconds else '?'}: " + ", ".join(filter(None, [
            plural(len(times), "frame") if times else "", "what's said" if said.strip() else ""]))
    else:
        return {"text": "", "problem": problem or "couldn't read frames or sound from this video (PyAV or ffmpeg needed)",
                "what": f"video, {clock(seconds)}" if seconds else "video"}
    return {"text": "\n".join(lines), "what": what, "details": {"seconds": seconds, "frames": times}}


def frames(path, view, seconds):
    """Up to MAX_FRAMES evenly spread frames saved as view/NN.jpg. Returns their times."""
    count = max(1, min(MAX_FRAMES, int((seconds or 0) // 8) + 1)) if seconds else 1
    wanted = [(i + 0.5) * (seconds or 0) / count for i in range(count)]
    taken = []
    try:
        import av
        with av.open(str(path)) as c:
            stream = c.streams.video[0]
            for i, t in enumerate(wanted, 1):
                c.seek(int(t * 1_000_000), any_frame=False, backward=True)
                frame = next(c.decode(stream), None)
                if frame is None:
                    continue
                img = frame.to_image()
                img.thumbnail((FRAME_SIDE, FRAME_SIDE))
                img.save(view / f"{i:02}.jpg", "JPEG", quality=80)
                taken.append(t)
        return taken
    except Exception:
        pass
    if shutil.which("ffmpeg"):
        for i, t in enumerate(wanted, 1):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                            "-vf", f"scale='min({FRAME_SIDE},iw)':-2", str(view / f"{i:02}.jpg")], capture_output=True, timeout=120)
            if (view / f"{i:02}.jpg").exists():
                taken.append(t)
    return taken


def read_archive(path, home, head):
    entries, texts, budget = [], [], PER_FILE
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for zi in z.infolist():
                    if zi.is_dir() or zi.filename.startswith("__MACOSX"):
                        continue
                    entries.append((zi.filename, zi.file_size))
                    if zi.file_size < 200_000 and budget > 0:
                        data = z.read(zi)
                        if looks_like_text(data[:8192]):
                            body = decode(data)[:budget]
                            budget -= len(body)
                            texts.append(f"--- {zi.filename} ---\n{body}")
        else:
            with tarfile.open(path) as t:
                for ti in t:
                    if not ti.isfile():
                        continue
                    entries.append((ti.name, ti.size))
                    if ti.size < 200_000 and budget > 0:
                        data = t.extractfile(ti).read()
                        if looks_like_text(data[:8192]):
                            body = decode(data)[:budget]
                            budget -= len(body)
                            texts.append(f"--- {ti.name} ---\n{body}")
    except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError):
        if head[:2] == b"\x1f\x8b":                     # a single gzipped file, not a tar
            import gzip
            with gzip.open(path) as g:
                data = g.read(STORED_CHARS)
            if looks_like_text(data[:8192]):
                return {"text": decode(data), "what": "gzipped text"}
        return {"text": "", "problem": "couldn't open this archive"}
    listing = "\n".join(f"{name}  ({fmt_size(size)})" for name, size in entries[:2000])
    more = f"\n…and {len(entries) - 2000:,} more" if len(entries) > 2000 else ""
    text = f"An archive with {plural(len(entries), 'file')}:\n{listing}{more}" + ("\n\n" + "\n\n".join(texts) if texts else "")
    return {"text": text, "what": f"archive, {plural(len(entries), 'file')}"}


def read_claude_export(path, home, head):
    """A Claude data export: counted, never read into a message (it's far too big, and it's a history,
    not a document). The page offers to import it."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "tools"))
    import claude_export
    conversations = messages = 0
    for item in claude_export.read(path):
        if isinstance(item, claude_export.Conversation) and item.messages:
            conversations += 1
            messages += len(item.messages)
    if not conversations:
        return read_text(path, home, head) if not zipfile.is_zipfile(path) else read_archive(path, home, head)
    return {"kind": "claude-export", "text": "", "what": f"Claude export: {conversations:,} conversations, {messages:,} messages",
            "details": {"conversations": conversations, "messages": messages}}


def read_binary(path, home, head):
    return {"text": "", "what": "kept, but Avy can't read this kind of file"}


READERS = {"text": read_text, "notebook": read_notebook, "pdf": read_pdf, "docx": read_docx, "xlsx": read_xlsx,
           "pptx": read_pptx, "odf": read_odf, "html": read_html, "rtf": read_rtf, "epub": read_epub,
           "image": read_image, "audio": read_audio, "video": read_video, "archive": read_archive,
           "claude-export": read_claude_export, "binary": read_binary}


# --- giving it to the model -------------------------------------------------------------------------

def for_model(records, folders, budget=PER_FILE, pictures=True):
    """The files of one message, for the model: (text blocks to add to the message, [picture data URLs]).
    budget: the most characters all these files may take together."""
    blocks, shown = [], []
    for r in records:
        home = find(r.get("id"), folders)
        record = json.loads((home / "info.json").read_text()) if home else r
        attrs = f'name="{record["name"]}" kind="{record.get("kind", "file")}" size="{fmt_size(record.get("size") or 0)}"'
        if not home:
            blocks.append(f"<file {attrs}>(this file is no longer kept)</file>")
            continue
        if record.get("status") == "problem":
            blocks.append(f"<file {attrs}>(it couldn't be read: {record.get('problem') or record.get('what')})</file>")
            continue
        if record.get("kind") == "claude-export":
            blocks.append(f"<file {attrs}>(a Claude data export: {record.get('what')}. It's not shown here; he can import it "
                          "into memory from the page, with the [ import ] button on the file)</file>")
            continue
        text = (home / "text.txt").read_text() if (home / "text.txt").exists() else ""
        room = max(0, min(PER_FILE, budget))
        body = text[:room]
        budget -= len(body)
        cut = f"\n(…the first {len(body):,} of {len(text):,} characters; the rest is too long to show)" if len(body) < len(text) else ""
        pics = sorted((home / "view").glob("*.jpg")) if (home / "view").exists() and pictures else []
        note = f"({plural(len(pics), 'picture')} of it follow{'s' if len(pics) == 1 else ''} this message)" if pics else ""
        if record.get("kind") == "image":
            note = "(the picture follows this message: look at it)" if pics else "(a picture that couldn't be shown)"
        blocks.append(f"<file {attrs}>\n" + "\n".join(filter(None, [note, body + cut])) + "\n</file>")
        shown += [data_url(p) for p in pics]
    return "\n\n".join(blocks), shown


def data_url(path):
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


# --- small helpers -----------------------------------------------------------------------------------

def fmt_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "bytes" else f"{n:,.1f} {unit}"
        n /= 1024


def clock(seconds):
    seconds = int(seconds or 0)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def plural(n, word):
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def describe(found, record):
    return found.get("problem") or f"{found.get('kind', 'file')}, {fmt_size(record.get('size') or 0)}"


def wait(fid, folders, seconds=60):
    """Until the reading is done (for tests and the import): the record."""
    end = time.time() + seconds
    while time.time() < end:
        record = info(fid, folders)
        if record and record["status"] != "reading":
            return record
        time.sleep(0.1)
    return info(fid, folders)
