# worker.py
import io
import sys
import threading
import queue

from PIL import Image

from config import load_config
from metadata import extract_a1111_metadata
from scanner import scan_for_new_images, count_images, mark_as_posted
from tagger import WDTagger
from uploader import AIBooruUploader

MIN_TAGS = 5
UPLOAD_DELAY = 1.5
POSTED_FILE = "posted.json"


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


class UploadWorker(threading.Thread):
    def __init__(
        self,
        images_dir: str,
        limit: int | None,
        stop_on_error: bool,
        event_queue: queue.Queue,
        response_queue: queue.Queue,
        stop_event: threading.Event,
    ):
        super().__init__(daemon=True)
        self.images_dir = images_dir
        self.limit = limit
        self.stop_on_error = stop_on_error
        self.eq = event_queue
        self.rq = response_queue
        self.stop_event = stop_event

    def _log(self, message: str, level: str = "info"):
        self.eq.put({"type": "log", "message": message, "level": level})

    def _progress(self, current: int, total: int):
        self.eq.put({"type": "progress", "current": current, "total": total})

    def run(self):
        old_stdout = sys.stdout
        sys.stdout = QueueWriter(self.eq)

        try:
            self._run_pipeline()
        except Exception as e:
            self._log(f"Критическая ошибка: {e}", "error")
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 1})
        finally:
            sys.stdout = old_stdout

    def _run_pipeline(self):
        try:
            cfg = load_config()
        except ValueError as e:
            self._log(str(e), "error")
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        self._log("Подключение к AIBooru...")
        uploader = AIBooruUploader(cfg["login"], cfg["api_key"])
        if not uploader.check_connection():
            self._log("Не удалось подключиться к AIBooru. Проверьте интернет и учётные данные.", "error")
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return
        self._log("Подключение к AIBooru... ОК")

        if self.stop_event.is_set():
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        self._log("Загрузка WD Tagger...")
        tagger = WDTagger()
        self._log("Загрузка WD Tagger... ОК")

        if self.stop_event.is_set():
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        new_files = scan_for_new_images(self.images_dir, POSTED_FILE)
        total_images = count_images(self.images_dir)
        self._log(f"Найдено {total_images} изображений, {len(new_files)} новых")

        if not new_files:
            self._log("Нет новых изображений для загрузки.")
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        if self.limit is not None:
            new_files = new_files[:self.limit]

        total = len(new_files)
        self.eq.put({"type": "started", "total": total})

        uploaded = 0
        skipped = 0
        errors = 0

        for idx, file_info in enumerate(new_files, 1):
            if self.stop_event.is_set():
                self._log("Остановлено пользователем.", "warning")
                break

            name = file_info["name"]
            path = file_info["path"]
            file_hash = file_info["hash"]
            prefix = f"[{idx}/{total}] {name}"

            try:
                img = Image.open(path)
                tags, rating, rating_confidence = tagger.predict(img)

                if len(tags) < MIN_TAGS:
                    self._log(f"{prefix} — {len(tags)} тегов — пропущено (недостаточно тегов)", "warning")
                    skipped += 1
                    self._progress(idx, total)
                    continue

                if rating_confidence < 0.3:
                    self._log(
                        f"{prefix} — пропущено (рейтинг не определён, confidence: {rating_confidence:.2f})",
                        "warning",
                    )
                    skipped += 1
                    self._progress(idx, total)
                    continue

                ai_meta = extract_a1111_metadata(path)

                tag_string = " ".join(tags)
                if cfg["artist_tag"]:
                    tag_string += " " + cfg["artist_tag"]
                upload_id = uploader.upload_file(path)

                media_asset_id = uploader.wait_for_processing(upload_id)

                post_id = uploader.create_post(
                    media_asset_id=media_asset_id,
                    tags=tag_string,
                    rating=rating,
                )

                if ai_meta.is_present():
                    uploader.set_ai_metadata(post_id, ai_meta)

                mark_as_posted(POSTED_FILE, file_hash, name)
                self._log(f"{prefix} -- {len(tags)} тегов, rating: {rating} -- загружено OK")
                uploaded += 1

            except Exception as e:
                self._log(f"{prefix} — ошибка: {e}", "error")
                errors += 1

                if self.stop_on_error:
                    self.eq.put({"type": "error_pause", "message": str(e), "file": name})
                    response = self.rq.get()  # blocks until GUI responds
                    if response == "abort":
                        self._log("Остановлено пользователем после ошибки.", "warning")
                        break

            self._progress(idx, total)

            # Interruptible delay
            if self.stop_event.wait(timeout=UPLOAD_DELAY):
                self._log("Остановлено пользователем.", "warning")
                break

        self._log(f"Итог: {uploaded} загружено, {skipped} пропущено, {errors} ошибок")
        self.eq.put({"type": "finished", "uploaded": uploaded, "skipped": skipped, "errors": errors})
