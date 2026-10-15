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

## Memory and files: the library

**Every file you attach also joins memory's library** (intake.py), in the memory it was attached in (an
incognito conversation's own library is deleted with it). The library keeps what a file *says*, word for
word, as passages in order (the way the log keeps what was said), and memory can search them from then on:
days later, "what's the retry policy in that design doc?" brings back the doc's own words, cited `[p41]`.
(Before Oct 15 only a file's name reached memory, and the live tests caught Avy confidently saying a doc
didn't contain what it did.)

- **Any format, no schema**: documents (by section, labeled with the page/slide and heading path), code (by
  file and lines), data (30 rows at a time, header repeated), recordings (the transcript), pictures (the
  model describes each once, so it can be found by what's in it), and conversations in any common shape:
  Claude and ChatGPT exports, any JSON with speaker and text, WhatsApp exports, labeled transcripts.
- **Whole folders and codebases**: drop a folder on the page (or use [ add a folder ] in the looking glass).
  It's uploaded file by file into `data/library/<batch>/`, then read as one source: every file by its own
  kind; node_modules, .git, build folders, lockfiles, minified bundles and binaries are left out and counted.
  A zip or tar of a project works the same way.
- **Watch it load** in the looking glass (`/glass`): each source's progress, how fast, how long it'll take,
  and any problem. Meaning vectors are the slow part; words are searchable at once.
- **See what's in it**: `/library`, then a source, then any passage, word for word.
- **Not yet**: knowledge (nodes and connections) written *from* the library. Passages are searchable and
  cited as they are; writing knowledge from them waits on decisions (VISION.md §16.1).

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
- `intake.py`: the library: anything (a file, a folder, an archive, a chat export) read into passages; the queue.
- `memory/library.py`: sources and passages in the memory file; searching them; what recall shows of them.
- `app.py`: `/api/files` (upload, list, a file, its download, its text), `/api/export`, `/api/import`,
  and the briefing (`with_files`).
- `voice.py`: `transcribe_file()` for attached recordings.
- `index.html`: the attach button, dropping, pasting, the tray, chips, `[ save ]`, `/files`, `/export`.
- `tests/test_files.py`: every kind of file, made and read offline, and what the model is given.
- `tests/test_intake.py`: every format into passages, the queue, duplicates, recall and explore bringing passages back.
