# Jobs: Avy's tests, packaged for someone else to run

Everything needed to test Avy, ready to run without judgment: press go, wait, push the records. Reading the results
and answering the questions is a separate step (`QUESTIONS.md`), for an agent with its own credits.

## Run

```
python3 -m pip install -r requirements.txt            # once (the page job also: playwright + its Chromium)
echo "LUMINAL_API_KEY=lum_live_..." > .env            # once; never committed
python3 jobs/run.py --list                            # what each job is
python3 jobs/run.py all --stamp 2026-10-18_run1       # everything (about 3 hours), or name jobs: offline hands persona
```

Interrupted? Run the same command with the same `--stamp`: finished jobs are skipped and the long ones resume.

Or press the button: GitHub → Actions → **Avy jobs** → Run workflow (needs the repository secret `LUMINAL_API_KEY`);
it runs the jobs you pick and commits `jobs/results/<stamp>/` back to the branch.

## Then

```
python3 jobs/facts.py 2026-10-18_run1                 # numbers computed by code: jobs/results/<stamp>/FACTS.md
```

Answer `jobs/QUESTIONS.md` into `jobs/results/<stamp>/ANSWERS.md` (from FACTS.md first; open result files only where
a question says to), then commit and push `jobs/results/<stamp>/` and the result files RUN.md lists.

## What's where

| job | writes |
|---|---|
| offline | `jobs/results/<stamp>/offline.log` |
| page | `jobs/results/<stamp>/page.log`, screenshots in the page tests' work folder |
| hands | `tests/hands/results/<stamp>.md` / `.json` |
| persona | `tests/persona/results/<stamp>_a.md` … `_c.md` / `.json` |
| longrun | `tests/persona/results/<stamp>_longrun_longrun.md` / `.json`, the conversation in `<stamp>_longrun.memory/transcript.jsonl` |
| live | `tests/live/results/<stamp>_*.md` / `.json` |
| bench | `tests/bench/results/*.md` / `.json` |
