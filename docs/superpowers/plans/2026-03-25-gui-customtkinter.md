# GUI CustomTkinter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing CLI auto-poster in a CustomTkinter GUI with folder picker, limit input, start/stop buttons, progress bar, and a scrolling log.

**Architecture:** Queue-based producer/consumer. `worker.py` runs the upload pipeline in a daemon thread, emitting events to a `queue.Queue`. `gui.py` polls the queue via `after()` and updates widgets. Existing business modules are unchanged (except a minimal `config.py` refactor).

**Tech Stack:** Python 3.9+, CustomTkinter, threading, queue

**Spec:** `docs/superpowers/specs/2026-03-25-gui-customtkinter-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `config.py` | Modify | Replace `sys.exit(1)` with `raise ValueError`; make `IMAGES_DIR` optional |
| `main.py` | Modify | Wrap `load_config()` in `try/except ValueError` |
| `worker.py` | Create | `UploadWorker(Thread)` — pipeline execution, event queue protocol |
| `gui.py` | Create | `App(CTk)` — GUI layout, queue polling, UI state management |
| `requirements.txt` | Modify | Add `customtkinter>=5.2.0` |
| `tests/test_config.py` | Modify | Update tests for ValueError instead of SystemExit |
| `tests/test_worker.py` | Create | Unit tests for UploadWorker event protocol |

---

### Task 1: Create branch `dev`

- [ ] **Step 1: Create and switch to dev branch**

```bash
git checkout -b dev
```

- [ ] **Step 2: Verify branch**

Run: `git branch --show-current`
Expected: `dev`

---

### Task 2: Refactor `config.py` — replace `sys.exit` with `ValueError`

**Files:**
- Modify: `config.py:10-12`
- Modify: `main.py:18-19`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Update test for ValueError**

In `tests/test_config.py`, change the test that checks for `SystemExit` to check for `ValueError` instead. If no such test exists, add one:

```python
def test_load_config_missing_vars_raises(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AIBOORU_LOGIN=user\n")  # missing API_KEY
    with pytest.raises(ValueError, match="AIBOORU_API_KEY"):
        load_config(str(env_file))


def test_load_config_images_dir_optional(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AIBOORU_LOGIN=user\nAIBOORU_API_KEY=key\n")
    cfg = load_config(str(env_file))
    assert cfg["images_dir"] == ""  # optional, empty if not set
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (currently `sys.exit` raises `SystemExit`, not `ValueError`)

- [ ] **Step 3: Modify `config.py`**

Replace lines 10-12 in `config.py`:

```python
# Before:
    required = ["AIBOORU_LOGIN", "AIBOORU_API_KEY", "IMAGES_DIR"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        print(f"Ошибка: отсутствуют переменные в .env: {', '.join(missing)}")
        sys.exit(1)

# After:
    required = ["AIBOORU_LOGIN", "AIBOORU_API_KEY"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ValueError(f"Отсутствуют переменные в .env: {', '.join(missing)}")
```

`IMAGES_DIR` becomes optional — the GUI provides it via folder picker, the CLI still reads it from `.env`. The return dict includes `"images_dir": values.get("IMAGES_DIR", "")`.

Remove `import sys` from `config.py` (no longer needed).

- [ ] **Step 4: Update `main.py` to preserve CLI behavior**

Wrap `load_config()` call in `main.py:19`:

```python
# Before:
    cfg = load_config()

# After:
    try:
        cfg = load_config()
    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add config.py main.py tests/test_config.py
git commit -m "refactor: config.py raises ValueError instead of sys.exit"
```

---

### Task 3: Create `worker.py` — stdout redirect helper

**Files:**
- Create: `worker.py`
- Create: `tests/test_worker.py`

- [ ] **Step 1: Write test for QueueWriter**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_worker.py::test_queue_writer_puts_log_events -v`
Expected: FAIL (module doesn't exist yet)

- [ ] **Step 3: Implement QueueWriter in `worker.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_worker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add worker.py tests/test_worker.py
git commit -m "feat: add QueueWriter for stdout redirection in worker"
```

---

### Task 4: Create `worker.py` — UploadWorker event protocol

**Files:**
- Modify: `worker.py`
- Modify: `tests/test_worker.py`

- [ ] **Step 1: Write test for UploadWorker event sequence (happy path, mocked modules)**

Test that the worker emits `started`, `progress`, `log`, `finished` in correct order with mocked business modules. Use `unittest.mock.patch` to mock `load_config`, `AIBooruUploader`, `WDTagger`, `scan_for_new_images`, etc.

Add the following imports and helpers to the **top** of `tests/test_worker.py` (merging with existing imports from Task 3):

```python
import queue
import threading
from unittest.mock import patch, MagicMock
from PIL import Image

from worker import QueueWriter, UploadWorker


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worker.py -v`
Expected: FAIL (`UploadWorker` not defined yet)

- [ ] **Step 3: Implement UploadWorker**

Add to `worker.py`:

```python
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
        # Redirect stdout to capture prints from uploader/tagger.
        # NOTE: This is process-wide. It is acceptable here because only the worker
        # thread calls business modules that print (uploader rate-limit, tagger download).
        # The GUI thread does not print to stdout during worker execution.
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
        # Load config (only credentials and artist_tag; images_dir comes from GUI)
        try:
            cfg = load_config()
        except ValueError as e:
            self._log(str(e), "error")
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        # Check connection
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

        # Load tagger
        self._log("Загрузка WD Tagger...")
        tagger = WDTagger()
        self._log("Загрузка WD Tagger... ОК")

        if self.stop_event.is_set():
            self.eq.put({"type": "finished", "uploaded": 0, "skipped": 0, "errors": 0})
            return

        # Scan
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_worker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add worker.py tests/test_worker.py
git commit -m "feat: add UploadWorker with queue-based event protocol"
```

---

### Task 5: Create `gui.py` — application window and layout

**Files:**
- Create: `gui.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add customtkinter to requirements.txt**

Add line to `requirements.txt`:

```
customtkinter>=5.2.0
```

- [ ] **Step 2: Install dependency**

Run: `pip install customtkinter>=5.2.0`

- [ ] **Step 3: Create `gui.py` with layout only (no worker integration yet)**

```python
import customtkinter as ctk
from tkinter import filedialog
from dotenv import dotenv_values


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AIBooru Auto-Poster")
        self.geometry("900x500")
        self.minsize(700, 400)

        ctk.set_appearance_mode("dark")

        self._build_layout()
        self._prefill_from_env()

    def _build_layout(self):
        # Main container: left panel + right panel
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === Left panel ===
        left = ctk.CTkFrame(self, width=250)
        left.grid(row=0, column=0, sticky="ns", padx=(10, 5), pady=10)
        left.grid_propagate(False)

        # Folder
        ctk.CTkLabel(left, text="Папка с изображениями").pack(padx=10, pady=(10, 2), anchor="w")
        folder_frame = ctk.CTkFrame(left, fg_color="transparent")
        folder_frame.pack(padx=10, fill="x")

        self.folder_entry = ctk.CTkEntry(folder_frame, state="readonly")
        self.folder_entry.pack(side="left", fill="x", expand=True)

        self.browse_btn = ctk.CTkButton(folder_frame, text="Обзор", width=70, command=self._browse_folder)
        self.browse_btn.pack(side="right", padx=(5, 0))

        # Limit
        ctk.CTkLabel(left, text="Лимит постов (пусто = все)").pack(padx=10, pady=(15, 2), anchor="w")
        self.limit_entry = ctk.CTkEntry(left, placeholder_text="все")
        self.limit_entry.pack(padx=10, fill="x")

        # Stop on error checkbox
        self.stop_on_error_var = ctk.BooleanVar(value=False)
        self.stop_on_error_cb = ctk.CTkCheckBox(
            left, text="Останавливаться\nпри ошибках", variable=self.stop_on_error_var
        )
        self.stop_on_error_cb.pack(padx=10, pady=(15, 5), anchor="w")

        # Buttons
        self.start_btn = ctk.CTkButton(
            left, text="▶  Запустить", fg_color="#2fa572", hover_color="#1f7a53",
            command=self._on_start,
        )
        self.start_btn.pack(padx=10, pady=(15, 5), fill="x")

        self.stop_btn = ctk.CTkButton(
            left, text="⏹  Стоп", state="disabled",
            command=self._on_stop,
        )
        self.stop_btn.pack(padx=10, fill="x")

        # Progress
        self.progress_label = ctk.CTkLabel(left, text="0 / 0")
        self.progress_label.pack(padx=10, pady=(15, 2))

        self.progress_bar = ctk.CTkProgressBar(left)
        self.progress_bar.pack(padx=10, fill="x")
        self.progress_bar.set(0)

        # === Right panel (log) ===
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 13), state="disabled")
        self.log_box.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        # Configure text tags for colored log output (once)
        self.log_box.tag_config("error", foreground="#ff4444")
        self.log_box.tag_config("warning", foreground="#ffaa00")

    def _prefill_from_env(self):
        try:
            values = dotenv_values(".env")
            images_dir = values.get("IMAGES_DIR", "")
            if images_dir:
                self.folder_entry.configure(state="normal")
                self.folder_entry.insert(0, images_dir)
                self.folder_entry.configure(state="readonly")
        except Exception:
            pass

    def _browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_entry.configure(state="normal")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)
            self.folder_entry.configure(state="readonly")

    def _on_start(self):
        pass  # Task 6

    def _on_stop(self):
        pass  # Task 6

    def _log(self, message: str, level: str = "info"):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        # Trim to 5000 lines
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        if line_count > 5000:
            self.log_box.delete("1.0", f"{line_count - 5000}.0")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")


if __name__ == "__main__":
    app = App()
    app.mainloop()
```

- [ ] **Step 4: Manual smoke test**

Run: `python gui.py`
Expected: window opens, dark theme, all widgets visible, "Обзор" opens folder dialog, pre-filled folder from .env if present. Close window cleanly.

- [ ] **Step 5: Commit**

```bash
git add gui.py requirements.txt
git commit -m "feat: add GUI layout with CustomTkinter (no worker integration)"
```

---

### Task 6: Integrate worker into GUI — start/stop/polling

**Files:**
- Modify: `gui.py`

- [ ] **Step 1: Add worker integration to `gui.py`**

Add imports at the top of `gui.py`:

```python
import queue
import threading
from tkinter import messagebox

from worker import UploadWorker
```

Add instance variables in `__init__` after `self._prefill_from_env()`:

```python
        self.event_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)
```

- [ ] **Step 2: Implement `_on_start`**

```python
    def _on_start(self):
        # Validate folder
        folder = self.folder_entry.get()
        if not folder:
            self._log("Ошибка: выберите папку с изображениями.", "error")
            return

        # Validate limit
        limit_text = self.limit_entry.get().strip()
        limit = None
        if limit_text:
            try:
                limit = int(limit_text)
                if limit < 1:
                    raise ValueError
            except ValueError:
                self._log("Ошибка: лимит должен быть положительным числом.", "error")
                return

        # Lock UI
        self.start_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.limit_entry.configure(state="disabled")
        self.stop_on_error_cb.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Reset state
        self.stop_event.clear()
        self.progress_bar.set(0)
        self.progress_label.configure(text="0 / 0")

        # Start worker
        self.worker = UploadWorker(
            images_dir=folder,
            limit=limit,
            stop_on_error=self.stop_on_error_var.get(),
            event_queue=self.event_queue,
            response_queue=self.response_queue,
            stop_event=self.stop_event,
        )
        self.worker.start()
        self._poll_queue()
```

- [ ] **Step 3: Implement `_on_stop`**

```python
    def _on_stop(self):
        self.stop_event.set()
        self.stop_btn.configure(state="disabled")
```

- [ ] **Step 4: Implement `_poll_queue`**

```python
    def _poll_queue(self):
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            etype = event["type"]

            if etype == "log":
                self._log(event["message"], event.get("level", "info"))

            elif etype == "progress":
                current = event["current"]
                total = event["total"]
                self.progress_bar.set(current / total if total > 0 else 0)
                self.progress_label.configure(text=f"{current} / {total}")

            elif etype == "started":
                total = event["total"]
                self.progress_label.configure(text=f"0 / {total}")

            elif etype == "finished":
                self._unlock_ui()
                return  # stop polling

            elif etype == "error_pause":
                answer = messagebox.askquestion(
                    "Ошибка при загрузке",
                    f"Файл: {event['file']}\n{event['message']}\n\nПропустить и продолжить?",
                    icon="warning",
                )
                self.response_queue.put("skip" if answer == "yes" else "abort")

        self.after(100, self._poll_queue)

    def _unlock_ui(self):
        self.start_btn.configure(state="normal")
        self.browse_btn.configure(state="normal")
        self.limit_entry.configure(state="normal")
        self.stop_on_error_cb.configure(state="normal")
        self.stop_btn.configure(state="disabled")
```

- [ ] **Step 5: Implement `_on_close`**

```python
    def _on_close(self):
        if self.worker and self.worker.is_alive():
            self.stop_event.set()
            self.worker.join(timeout=3)
        self.destroy()
```

- [ ] **Step 6: Add error-level color to `_log`**

Update the `_log` method to colorize errors:

```python
    def _log(self, message: str, level: str = "info"):
        self.log_box.configure(state="normal")

        if level == "error":
            self.log_box.insert("end", message + "\n")
            line_idx = int(self.log_box.index("end-2c").split(".")[0])
            self.log_box.tag_add("error", f"{line_idx}.0", f"{line_idx}.end")
        elif level == "warning":
            self.log_box.insert("end", message + "\n")
            line_idx = int(self.log_box.index("end-2c").split(".")[0])
            self.log_box.tag_add("warning", f"{line_idx}.0", f"{line_idx}.end")
        else:
            self.log_box.insert("end", message + "\n")

        # Trim to 5000 lines
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        if line_count > 5000:
            self.log_box.delete("1.0", f"{line_count - 5000}.0")

        self.log_box.configure(state="disabled")
        self.log_box.see("end")
```

- [ ] **Step 7: Manual integration test**

Run: `python gui.py`
Test:
1. Select a folder with images
2. Set limit to 1
3. Click "Запустить" — observe log updates, progress bar advancing
4. Try "Стоп" during a longer run
5. Close window during operation — should exit cleanly

- [ ] **Step 8: Commit**

```bash
git add gui.py
git commit -m "feat: integrate worker into GUI — start, stop, queue polling, error handling"
```

---

### Task 7: Final polish and verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Verify CLI still works**

Run: `python main.py`
Expected: CLI works exactly as before (enter folder path, see console output)

- [ ] **Step 3: Verify GUI end-to-end**

Run: `python gui.py`
Verify:
- Dark theme
- Folder pre-populated from .env
- Browse button opens dialog
- Limit validation (try "abc", "-1", empty)
- Start → progress → log → finish
- Stop button works
- "Останавливаться при ошибках" works (can test by temporarily disrupting network)
- Window close during operation exits cleanly
- Log doesn't show raw print() in console

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final polish for GUI integration"
```
