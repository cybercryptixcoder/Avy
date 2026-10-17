# Long runs
Starting work that outlives this message (a training run, a long build, a scrape, anything left running) and picking it
up later exactly where it was.

1. Before starting it, put on its thread (open one if there isn't one): what the run is, how it's configured and why
   (the specific reasons, as insights), what result would mean what, and the next step for each outcome. That's what
   gets lost when a run takes hours; the thread is where it survives.
2. Start it with terminal background=true and the thread's id, so its end is noted on the thread by itself.
3. Set the thread's waiting to the job (j3) and what you're waiting to see. Then move on: talk about other things, start
   other work. Don't poll it.
4. When it ends (your desk shows it, and the thread says so), read its output (jobs status), compare it with what you
   predicted, update the thread (what happened, what it means, the next step), and tell him in a line or two.
5. If it failed, read the end of its log first; say what failed and what you'd change, before running it again.
