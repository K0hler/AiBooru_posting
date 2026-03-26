# tests/test_worker.py
import queue
import threading
from unittest.mock import patch, MagicMock

from PIL import Image

from worker import QueueWriter, UploadWorker


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


def _drain_queue(q):
    """Drain all events from queue into a list."""
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_worker_happy_path_emits_correct_events():
    eq = queue.Queue()
    rq = queue.Queue()
    stop = threading.Event()

    fake_config = {
        "login": "user",
        "api_key": "key",
        "images_dir": "/imgs",
        "artist_tag": "",
    }

    fake_files = [
        {"path": "/imgs/a.png", "hash": "aaa", "name": "a.png"},
    ]

    fake_image = MagicMock(spec=Image.Image)

    with patch("worker.load_config", return_value=fake_config), \
         patch("worker.AIBooruUploader") as MockUploader, \
         patch("worker.WDTagger") as MockTagger, \
         patch("worker.scan_for_new_images", return_value=fake_files), \
         patch("worker.count_images", return_value=1), \
         patch("worker.Image.open", return_value=fake_image), \
         patch("worker.extract_a1111_metadata") as MockMeta, \
         patch("worker.mark_as_posted"):

        mock_uploader = MockUploader.return_value
        mock_uploader.check_connection.return_value = True
        mock_uploader.upload_file.return_value = 42
        mock_uploader.wait_for_processing.return_value = 100
        mock_uploader.create_post.return_value = 1

        mock_tagger = MockTagger.return_value
        mock_tagger.predict.return_value = (["tag1", "tag2", "tag3", "tag4", "tag5"], "g", 0.9)

        mock_meta = MagicMock()
        mock_meta.is_present.return_value = False
        MockMeta.return_value = mock_meta

        w = UploadWorker(
            images_dir="/imgs",
            limit=None,
            stop_on_error=False,
            event_queue=eq,
            response_queue=rq,
            stop_event=stop,
        )
        w.start()
        w.join(timeout=10)

    events = _drain_queue(eq)
    types = [e["type"] for e in events]

    assert "started" in types
    assert "progress" in types
    assert "finished" in types
    # finished should be last
    assert types[-1] == "finished"
    finished = events[-1]
    assert finished["uploaded"] == 1
    assert finished["errors"] == 0


def test_worker_stop_event_stops_processing():
    eq = queue.Queue()
    rq = queue.Queue()
    stop = threading.Event()
    stop.set()  # pre-set stop

    fake_config = {
        "login": "user",
        "api_key": "key",
        "images_dir": "/imgs",
        "artist_tag": "",
    }

    fake_files = [
        {"path": "/imgs/a.png", "hash": "aaa", "name": "a.png"},
        {"path": "/imgs/b.png", "hash": "bbb", "name": "b.png"},
    ]

    with patch("worker.load_config", return_value=fake_config), \
         patch("worker.AIBooruUploader") as MockUploader, \
         patch("worker.WDTagger"), \
         patch("worker.scan_for_new_images", return_value=fake_files), \
         patch("worker.count_images", return_value=2):

        mock_uploader = MockUploader.return_value
        mock_uploader.check_connection.return_value = True

        w = UploadWorker(
            images_dir="/imgs",
            limit=None,
            stop_on_error=False,
            event_queue=eq,
            response_queue=rq,
            stop_event=stop,
        )
        w.start()
        w.join(timeout=10)

    events = _drain_queue(eq)
    finished = [e for e in events if e["type"] == "finished"]
    assert len(finished) == 1
    assert finished[0]["uploaded"] == 0
