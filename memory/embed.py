"""
Meaning search: a small local model turns text into 384 numbers, so that "my exam" lands near
"the probability quiz". It runs on this computer and only ever searches; DeepSeek is still the
only brain. It's optional: without it, keyword search still works. One model, shared by every
open memory.
"""

import threading
from pathlib import Path

EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 384 numbers per text, about 65 MB, runs on the CPU
KINDS = "mvec"                           # what gets vectors: messages, node versions, episodes, connections


class Shelf:
    """Rows of vectors that can grow, for one kind of item."""
    def __init__(self, np, dims=384):
        self.np, self.items, self.where = np, [], {}
        self.data = np.zeros((1024, dims), np.float32)

    def put(self, item, vec):
        if item in self.where:
            self.data[self.where[item]] = vec
            return
        if len(self.items) == len(self.data):
            self.data = self.np.concatenate([self.data, self.np.zeros_like(self.data)])
        self.where[item] = len(self.items)
        self.data[len(self.items)] = vec
        self.items.append(item)

    def closest(self, query, k):
        if not self.items:
            return []
        sims = self.data[:len(self.items)] @ query
        top = self.np.argsort(-sims)[:k]
        return [(self.items[i], float(sims[i])) for i in top]

    def vector(self, item):
        return self.data[self.where[item]] if item in self.where else None


class Embedder:
    def __init__(self):
        self.model, self.np = None, None
        self.status = "starting"
        self.lock = threading.Lock()
        self.memories = []           # every open memory, so each gets its vectors once the model is ready

    @property
    def ready(self):
        return self.model is not None

    def start(self, folder):
        """Load the model in the background (the first run downloads it into `folder`)."""
        threading.Thread(target=self.load, args=(Path(folder),), daemon=True).start()

    def wait(self, seconds=120):
        """For tests and scripts: block until the model is loaded (or failed)."""
        import time
        started = time.time()
        while self.status != "on" and not self.status.startswith("off") and time.time() - started < seconds:
            time.sleep(0.2)
        return self.ready

    def load(self, folder):
        try:
            import numpy as np
            from fastembed import TextEmbedding
        except ImportError:
            self.status = "off: install fastembed for search by meaning (keyword search still works)"
            return
        try:
            self.status = "loading the meaning-search model (first run downloads about 65 MB)"
            self.np = np
            self.model = TextEmbedding(EMBED_MODEL, cache_dir=str(folder))
            self.status = "on"
            for mem in list(self.memories):
                mem.load_vectors()
        except Exception as e:
            self.model, self.status = None, f"off: the meaning-search model failed to load ({e})"

    def attach(self, mem):
        self.memories.append(mem)
        if self.ready:
            mem.load_vectors()

    def detach(self, mem):
        if mem in self.memories:
            self.memories.remove(mem)

    def passages(self, texts):
        with self.lock:
            return [self.np.asarray(v, self.np.float32) for v in self.model.passage_embed([t[:2000] for t in texts])]

    def query(self, text):
        if not self.ready or not text.strip():
            return None
        with self.lock:
            return self.np.asarray(next(iter(self.model.query_embed([text[:2000]]))), self.np.float32)


embedder = Embedder()
