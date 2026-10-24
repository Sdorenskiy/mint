"""Минимальная заглушка faiss на numpy: подключается тестами, только если faiss-cpu не установлен."""
import pickle
import numpy as np

class IndexFlatL2:
    def __init__(self, d):
        self.d = int(d)
        self._x = np.zeros((0, self.d), dtype="float32")
    @property
    def ntotal(self):
        return int(self._x.shape[0])
    def add(self, x):
        x = np.asarray(x, dtype="float32")
        assert x.ndim == 2 and x.shape[1] == self.d, f"dim mismatch {x.shape} vs {self.d}"
        self._x = np.vstack([self._x, x])
    def search(self, q, k):
        q = np.asarray(q, dtype="float32")
        assert q.shape[1] == self.d, "query dim mismatch"
        d2 = ((self._x[None, :, :] - q[:, None, :]) ** 2).sum(-1)
        idx = np.argsort(d2, axis=1)[:, :k]
        dist = np.take_along_axis(d2, idx, axis=1)
        if idx.shape[1] < k:
            pad = k - idx.shape[1]
            idx = np.hstack([idx, -np.ones((idx.shape[0], pad), dtype=int)])
            dist = np.hstack([dist, np.full((dist.shape[0], pad), np.inf)])
        return dist, idx
    def reconstruct(self, i):
        return self._x[i].copy()
    def reconstruct_n(self, i0, ni):
        return self._x[i0:i0 + ni].copy()

def write_index(index, path):
    with open(path, "wb") as f:
        pickle.dump({"d": index.d, "x": index._x}, f)

def read_index(path):
    with open(path, "rb") as f:
        data = pickle.load(f)
    idx = IndexFlatL2(data["d"])
    idx._x = data["x"]
    return idx

def serialize_index(index):
    return np.frombuffer(pickle.dumps({"d": index.d, "x": index._x}), dtype="uint8")

def deserialize_index(arr):
    data = pickle.loads(np.asarray(arr, dtype="uint8").tobytes())
    idx = IndexFlatL2(data["d"])
    idx._x = data["x"]
    return idx
