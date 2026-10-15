"""Grade a finished benchmark run again (after the judge changes), using the log it produced.

    python3 tests/bench/regrade.py tests/bench/results/<stamp>.json [--key .env]
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

run_file = Path(sys.argv[1])
key_file = Path(sys.argv[sys.argv.index("--key") + 1]) if "--key" in sys.argv else HERE.parent.parent / ".env"

import judge          # noqa: E402
judge.load_keys(key_file)
import luminal        # noqa: E402
import report         # noqa: E402
from mind import llm  # noqa: E402

llm.app.update(ask=luminal.complete, prices=luminal.PRICES)
r = json.loads(run_file.read_text())
log = sqlite3.connect(f"file:{run_file.with_suffix('.memory') / 'memory-v2.db'}?mode=ro", uri=True).execute(
    "SELECT at, role, text FROM messages ORDER BY id").fetchall()
probes = {p["id"]: p for p in json.loads(json.dumps(__import__("world").PROBES))}
for p in r["probes"]:
    for a in p["answers"]:
        a["grade"] = judge.grade(probes[p["id"]], a["answer"], log=log)
        print(f"{p['id']:<14} {a['config']:<8} {a['grade']['score']}" + ("  INVENTED: " + a["grade"]["invented_what"][:150] if a["grade"]["invented"] else ""), flush=True)
    for a in [r.get("v1", {}).get(p["id"])]:
        if a:
            a["grade"] = judge.grade(probes[p["id"]], a["answer"], log=log)
            print(f"{p['id']:<14} {'v1':<8} {a['grade']['score']}", flush=True)
run_file.write_text(json.dumps(r, indent=1, default=str))
run_file.with_suffix(".md").write_text(report.markdown(r))
print("regraded:", run_file.with_suffix(".md"))
