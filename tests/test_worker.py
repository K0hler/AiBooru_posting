# tests/test_worker.py
import queue

from worker import QueueWriter


def test_queue_writer_puts_log_events():
    q = queue.Queue()
    writer = QueueWriter(q)
    writer.write("hello world\n")
    writer.flush()  # should be a no-op, no error

    event = q.get_nowait()
    assert event["type"] == "log"
    assert event["message"] == "hello world"
    assert event["level"] == "info"


def test_queue_writer_ignores_empty_strings():
    q = queue.Queue()
    writer = QueueWriter(q)
    writer.write("")
    writer.write("\n")
    assert q.empty()
