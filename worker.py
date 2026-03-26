# worker.py
import io
import queue


class QueueWriter(io.TextIOBase):
    """Redirects write() calls to event_queue as log events."""

    def __init__(self, event_queue: queue.Queue):
        self._queue = event_queue

    def write(self, text: str) -> int:
        stripped = text.strip()
        if stripped:
            self._queue.put({"type": "log", "message": stripped, "level": "info"})
        return len(text)

    def flush(self):
        pass
