# Files: attaching anything, and getting things out

## Attaching

Any kind of file, any size (up to 8 GB), three ways:
- **`[ attach ]`** at the bottom right (or `/attach`)
- **drop** files anywhere on the page
- **paste** a picture or a file into the box (pasting text still pastes text)

Each file shows as a chip above the status line while it uploads (with a percentage) and while it's
read, then says what Avy made of it ("PDF, 12 pages", "picture, 4032×3024", "audio, 3:12, transcribed",
"Claude export: 503 conversations"). `×` takes it out. Enter sends your message with the files, or the
files alone. If something's still being read when you press Enter, Avy waits for it (Esc stops waiting).

Your message keeps its files: chips under it, in the history too. Click a name to open the file as it
came; **read** shows exactly what Avy read from it.

## What Avy can read

| Kind | What she gets | Needs |
|---|---|---|
| Any text: plain, Markdown, code, JSON, CSV, logs, subtitles, config... | the text as it is (any encoding; minified JSON laid out) | nothing |
| Jupyter notebooks | each cell, and its text output | nothing |
| Word (.docx), OpenDocument (.odt) | paragraphs, headings, lists, tables | nothing |
| Excel (.xlsx), OpenDocument (.ods) | every sheet, as tab-separated rows | nothing |
| PowerPoint (.pptx), OpenDocument (.odp) | every slide in order, with its notes | nothing |
| Web pages, RTF, EPUB | their text (an EPUB in reading order) | nothing |
| PDF | its text, page by page | pypdf (or the pdftotext program) |
| A scanned PDF (no text in it) | its first 6 pages as pictures she looks at | the pdftoppm program |
| Pictures (JPEG, PNG, GIF, WebP, BMP, TIFF; HEIC with pillow-heif) | the picture itself: she sees it (shrunk to 1,568 pixels a side) | Pillow |
| Audio (MP3, M4A, WAV, FLAC, OGG, Opus...) | what's said, with times, by the speech model | the voice packages |
| Video (MP4, MOV, MKV, WebM...) | up to 8 frames she sees, spread over it, plus what's said | the voice packages (PyAV); else ffmpeg for frames |
| Zip and tar archives | what's inside (names and sizes), and the text of small text files in it | nothing |
| A Claude data export | recognized and counted, never read into a message: `[ import ]` on its chip | ijson |
| Anything else | kept, and she knows its name, type and size | |

`requirements.txt` has pypdf, Pillow and ijson; the voice packages are in `requirements-voice.txt`.
Without one of them, that kind of file is still kept, and the chip says what to install.

Speech in attached recordings is heard in English with the default speech models; for other languages,
`/whisper: large-v3-turbo`.

## How files reach the model

- A file goes **with the message it came with**, inside `<file name=... kind=... size=...>` tags after
  your words; pictures and frames follow as images.
- **One file carries at most 150,000 characters** (about 40,000 tokens); the rest is cut, and the model is
  told how much it's seeing ("the first 150,000 of 2,000,000 characters").
- **Earlier files stay in view** while their message is within `/window:`, newest first, until
  240,000 characters and 16 pictures in all; past that they're named, not shown.
- Avy's instructions say how files arrive, to say so when a file couldn't be read or is only partly
  shown, and never to guess at the rest.

## Memory and files

The log keeps which files went with each message (name, kind, size, what was read). The writer sees the
names, so memory knows a file was shared and what was said about it. What the file itself says isn't
written into knowledge yet (LATER.md).

## Getting things out

- **A file you attached**: click its name (opens it), or `/files` to list them all, newest first.
- **What Avy read from it**: **read** on its chip.
- **Code and files Avy makes**: ask for a file ("make me a CSV of..."); she puts it in a code block, and
  `[ save ]` on the block downloads it (`avy.csv`, `avy.py`...; a block labelled with a file name, like
  ```` ```notes.md ````, saves under that name). `[ copy ]` copies it.
- **`/export`**: the whole conversation as Markdown, a heading where each sitting begins, who said what
  and when, and what was attached.
- **`/export: json`**: the same as data (every message with its metadata).
- **`/export: memory`**: everything memory knows, as JSON: every node (with where it was said), every
  connection, what inferences rest on, every conversation.

In an incognito conversation, exports are of the incognito memory, and attached files are kept with it
and deleted when it ends.

## Where files live

`data/files/<id>/`: the file exactly as it came, `info.json` (what it is and how reading went),
`text.txt` (what Avy read), and `view/` (the pictures she's shown). Incognito files go in
`data/incognito/files/`. Nothing in `data/` is ever committed.

## Safety

- File names can't reach outside their folder; ids are checked before any file is opened.
- A web page you attached opens sandboxed, so it can't run as Avy's page.
- Uploads are only accepted from Avy's own page.

## Code

- `files.py`: keeping and reading files (one reader per kind), and what goes to the model.
- `app.py`: `/api/files` (upload, list, a file, its download, its text), `/api/export`, `/api/import`,
  and the briefing (`with_files`).
- `voice.py`: `transcribe_file()` for attached recordings.
- `index.html`: the attach button, dropping, pasting, the tray, chips, `[ save ]`, `/files`, `/export`.
- `tests/test_files.py`: every kind of file, made and read offline, and what the model is given.
