"""Progress events for existing draft callbacks; no model, file or index access."""


def tracked(emit, stage, items, total=None):
    """Count finished items, including handled skips/errors, not started jobs.

    A raised exception never marks the failed operation as completed. Existing
    callbacks keep the (stage, number) signature; totals and completions use
    suffixes, just as the existing extraction events do.
    """
    if total is None:
        total = len(items)
    emit(stage + "_total", total)
    for index, item in enumerate(items, 1):
        yield item
        emit(stage + "_done", index)


class StageProgress:
    """Small per-run wall-clock estimator, independent of Streamlit."""
    def __init__(self, clock):
        self.clock = clock
        self.rows = {}
        self.active = None
        self.cached = 0
        self.failed = 0
        self.last_render = float("-inf")

    def update(self, event, value):
        now = self.clock()
        if event in {"extract_elapsed", "extract"}:
            return False
        if event in {"extract_cached", "extract_failed"}:
            setattr(self, "cached" if event.endswith("cached") else "failed", value)
            return False
        if event.endswith("_total"):
            stage = event[:-6]
            self.rows[stage] = {"total": value, "done": 0, "start": now, "end": now if value == 0 else None}
            self.active = stage
            if stage == "extract":
                self.cached = self.failed = 0
            self.last_render = now
            return True
        if event.endswith("_done"):
            stage = event[:-5]
            if stage not in self.rows:
                return False
            row = self.rows[stage]
            row["done"] = max(row["done"], value)
            finished = row["total"] is not None and row["done"] >= row["total"]
            if finished:
                row["end"] = now
            if finished or now - self.last_render >= 1:
                self.last_render = now
                return True
            return False
        # Historical events announce the start of work, not its completion.
        # They must not overwrite the exact counter.
        if event in self.rows:
            return False
        return False

    def snapshot(self):
        now = self.clock()
        rows = []
        for stage, row in self.rows.items():
            elapsed = max(0, (row["end"] if row["end"] is not None else now) - row["start"])
            done, total = row["done"], row["total"]
            eta = (elapsed * (total - done) / done if total is not None
                   and done >= 3 and total > done and elapsed >= 1 else None)
            # Cache hits do not predict the cost of the remaining cold fragments.
            if stage == "extract" and self.cached:
                eta = None
            rows.append({"stage": stage, "done": done, "total": total,
                         "elapsed": elapsed, "eta": eta})
        return rows
