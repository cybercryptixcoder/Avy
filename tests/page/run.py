"""Browser tests of the page, against a fake Luminal. Each test gets a fresh copy of Avy (the repo's code,
an empty memory, a fake key) in a work folder, with the real speech and meaning models borrowed from
data/models so nothing is downloaded twice. Your own data is never touched.

    python3 tests/page/run.py                     all of them
    python3 tests/page/run.py files errands       some of them
    python3 tests/page/run.py --keep              leave the last Avy running (http://localhost:8000) to look at

Needs: playwright with Chromium (python3 -m pip install playwright && python3 -m playwright install chromium),
and Avy's own packages (requirements-voice.txt) in the Python that runs app.py (--python, default this one).
Screenshots land in <work>/shots; the fake Luminal's log of every request in <work>/requests.jsonl.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TESTS = {
    "basics": "t_basics.py",     # markdown, keys panel, the card's menu, phone width
    "ui": "t_ui.py",             # the command panel, /index, footnotes, the inspector, explore, the graph, incognito citing
    "errands": "t_errands.py",   # the two dials, incognito end to end, dictation vs live voice (needs the voice models)
    "files": "t_files.py",       # attaching, dropping, pasting, what reaches the model, chips, save, /export, /files, import
}


def wait_for_avy(seconds=240):
    """Until the server answers and voice has finished loading (or given up)."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            status = json.loads(urllib.request.urlopen("http://localhost:8000/api/status", timeout=2).read())
            voice = status.get("voice") or {}
            if voice.get("available") or "loading" not in (voice.get("problem") or "loading"):
                return status
        except OSError:
            pass
        time.sleep(1)
    return None


class Avy:
    def __init__(self, work, python, models):
        self.work, self.python, self.models, self.procs = Path(work), python, Path(models), []

    def start(self):
        self.stop()
        code, data = self.work / "code", self.work / "data"
        shutil.rmtree(code, ignore_errors=True)
        shutil.copytree(ROOT, code, ignore=shutil.ignore_patterns("data", ".git", "__pycache__", ".env", "results", "*.memory"))
        shutil.rmtree(data, ignore_errors=True)                     # a fresh memory every time
        (data / "models").mkdir(parents=True)
        for model in ("whisper", "kokoro", "meaning"):              # borrow the models instead of downloading them
            if (self.models / model).exists():
                (data / "models" / model).symlink_to((self.models / model).resolve())
        (code / "data").symlink_to(data)
        (code / ".env").write_text("LUMINAL_API_KEY=lum_live_fake1234\n")
        (self.work / "requests.jsonl").write_text("")
        log = open(self.work / "avy.log", "w")
        self.procs.append(subprocess.Popen([sys.executable, str(HERE / "mock_luminal.py"), str(self.work / "requests.jsonl")],
                                           stdout=log, stderr=subprocess.STDOUT))
        env = dict(os.environ, LUMINAL_BASE_URL="http://127.0.0.1:9999/v1", AVY_NO_BROWSER="1")
        self.procs.append(subprocess.Popen([self.python, "-u", "app.py"], cwd=code, env=env, stdout=log, stderr=subprocess.STDOUT))
        if not wait_for_avy():
            raise SystemExit(f"Avy didn't start; see {self.work / 'avy.log'}")

    def stop(self):
        for p in self.procs:
            p.send_signal(signal.SIGINT if p.args[-1] == "app.py" else signal.SIGTERM)
        for p in self.procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procs = []
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tests", nargs="*", help="any of: " + ", ".join(TESTS) + " (default: all)")
    parser.add_argument("--work", default="", help="the work folder (default: a new temporary one)")
    parser.add_argument("--python", default=sys.executable, help="the Python that runs app.py (with Avy's packages)")
    parser.add_argument("--models", default=str(ROOT / "data" / "models"), help="where the speech and meaning models are")
    parser.add_argument("--keep", action="store_true", help="leave the last Avy running")
    args = parser.parse_args()
    args.tests = args.tests or list(TESTS)
    unknown = [t for t in args.tests if t not in TESTS]
    if unknown:
        parser.error(f"no such test: {', '.join(unknown)} (there are: {', '.join(TESTS)})")
    work = Path(args.work or tempfile.mkdtemp(prefix="avy-page-"))
    work.mkdir(parents=True, exist_ok=True)
    avy, failed = Avy(work, args.python, args.models), []
    print(f"work folder: {work}")
    try:
        for name in args.tests:
            print(f"\n== {name}")
            avy.start()
            done = subprocess.run([sys.executable, str(HERE / TESTS[name]), str(work)], text=True, capture_output=True)
            print(done.stdout.rstrip() + ("\n" + done.stderr[-2000:] if done.returncode and done.stderr else ""))
            last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
            if done.returncode or not last.startswith("0 failed"):
                failed.append(name)
    finally:
        if not args.keep:
            avy.stop()
    print(f"\n{len(failed)} of {len(args.tests)} failed" + (": " + ", ".join(failed) if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
