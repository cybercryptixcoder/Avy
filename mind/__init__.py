"""
Avy's mind: where DeepSeek comes in. It never writes to memory directly; it proposes, and memory's
one door (memory/ops.py) checks every proposal against the rules and journals it.

    llm.py       one strict tool call to DeepSeek, and what it cost
    jobs.py      the engine: prompt, call, check, repair (up to twice), apply, record the run
    writer.py    Write: a stretch of the log becomes knowledge (nodes with evidence, first edges)
    reflect.py   Connect (find partners anywhere in memory and judge them), Think (patterns, unnamed
                 things, shared ideas, conclusions), Check (re-examine what rests on changed ground)
    explore.py   Avy searching her own memory, step by step, when /explore: is on
    worker.py    when all of it happens: after replies, and at quiet times, within a daily budget
"""
