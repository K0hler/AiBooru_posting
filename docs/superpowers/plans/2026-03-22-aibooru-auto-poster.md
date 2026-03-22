# AIBooru Auto-Poster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python script that scans a local folder for new AI-generated images, auto-tags them via WD Tagger, and uploads to aibooru.online.

**Architecture:** Single `main.py` with helper modules for separation of concerns. Config via `.env`, state tracking via `posted.json`. Two-step upload: file → AIBooru uploads API → create post with tags/rating.

**Tech Stack:** Python 3.10+, requests, onnxruntime, Pillow, numpy, huggingface_hub, python-dotenv

**Spec:** `docs/superpowers/specs/2026-03-22-aibooru-auto-poster-design.md`

---

## File Structure

```
AiBooru_posting/
├── main.py              # Entry point, orchestration loop
├── config.py            # Load .env, validate config
├── scanner.py           # Scan folder, hash files, track posted
├── tagger.py            # WD Tagger: download model, preprocess, inference
├── metadata.py          # Extract A1111 PNG metadata
├── uploader.py          # AIBooru API: upload file, create post
├── .env                 # AIBOORU_LOGIN, AIBOORU_API_KEY, IMAGES_DIR
├── .gitignore           # .env, models/, __pycache__/, posted.json
├── posted.json          # Auto-generated state file
├── requirements.txt     # Dependencies
├── tests/
│   ├── test_config.py
│   ├── test_scanner.py
│   ├── test_tagger.py
│   ├── test_metadata.py
│   └── test_uploader.py
└── models/              # Auto-downloaded WD Tagger files
```

> **Note:** The spec says "single main.py" but the plan splits into focused modules for testability. Each module is small (50-150 lines). `main.py` remains the only entry point and orchestrates the flow.

---

### Task 1: Project Setup & Configuration

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `tests/test_config.py`
- Modify: `.env` (update format)
- Modify: `.gitignore` (add posted.json)

- [ ] **Step 1: Create requirements.txt**

```
requests>=2.31.0
onnxruntime>=1.17.0
Pillow>=10.0.0
python-dotenv>=1.0.0
numpy>=1.24.0
huggingface_hub>=0.20.0
pytest>=7.0.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Update .env format**

Current `.env` has `Auth = ?api_key=XwuvoJgG2MfeaeKVFPdYpLzK&login=K0hler`. Update to:

```
AIBOORU_LOGIN=K0hler
AIBOORU_API_KEY=XwuvoJgG2MfeaeKVFPdYpLzK
IMAGES_DIR=<user must fill in the path to their images folder>
```

- [ ] **Step 3: Update .gitignore**

Add `posted.json` to `.gitignore`:

```
.env
models/
__pycache__/
posted.json
```

- [ ] **Step 4: Write test for config loading**

```python
# tests/test_config.py
import os
import pytest
from config import load_config


def test_load_config_returns_all_keys(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIBOORU_LOGIN=testuser\n"
        "AIBOORU_API_KEY=testkey123\n"
        "IMAGES_DIR=C:/images\n"
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config(str(env_file))
    assert cfg["login"] == "testuser"
    assert cfg["api_key"] == "testkey123"
    assert cfg["images_dir"] == "C:/images"


def test_load_config_missing_key_raises(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("AIBOORU_LOGIN=testuser\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        load_config(str(env_file))
```

Run: `pytest tests/test_config.py -v`
Expected: FAIL (config module doesn't exist)

- [ ] **Step 5: Implement config.py**

```python
# config.py
import sys
from dotenv import dotenv_values


def load_config(env_path: str = ".env") -> dict:
    values = dotenv_values(env_path)
    required = ["AIBOORU_LOGIN", "AIBOORU_API_KEY", "IMAGES_DIR"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        print(f"Ошибка: отсутствуют переменные в .env: {', '.join(missing)}")
        sys.exit(1)
    return {
        "login": values["AIBOORU_LOGIN"],
        "api_key": values["AIBOORU_API_KEY"],
        "images_dir": values["IMAGES_DIR"],
    }
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.py tests/test_config.py .env .gitignore
git commit -m "feat: add project setup and config loading"
```

---

### Task 2: Scanner — Find New Images

**Files:**
- Create: `scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write tests for scanner**

```python
# tests/test_scanner.py
import json
import hashlib
from pathlib import Path
from PIL import Image
from scanner import scan_for_new_images, count_images, compute_hash, load_posted, save_posted


def _create_test_image(path: Path, color: str = "red"):
    img = Image.new("RGB", (100, 100), color)
    img.save(str(path))


def test_compute_hash_deterministic(tmp_path):
    img_path = tmp_path / "test.png"
    _create_test_image(img_path)
    h1 = compute_hash(str(img_path))
    h2 = compute_hash(str(img_path))
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_scan_finds_new_images(tmp_path):
    _create_test_image(tmp_path / "a.png")
    _create_test_image(tmp_path / "b.jpg")
    posted_path = tmp_path / "posted.json"
    new_files = scan_for_new_images(str(tmp_path), str(posted_path))
    assert len(new_files) == 2


def test_scan_skips_already_posted(tmp_path):
    img_path = tmp_path / "a.png"
    _create_test_image(img_path)
    file_hash = compute_hash(str(img_path))
    posted_path = tmp_path / "posted.json"
    posted_path.write_text(json.dumps({
        "hashes": {file_hash: {"file": "a.png", "posted_at": "2026-01-01T00:00:00"}}
    }))
    new_files = scan_for_new_images(str(tmp_path), str(posted_path))
    assert len(new_files) == 0


def test_scan_ignores_non_image_files(tmp_path):
    (tmp_path / "readme.txt").write_text("hello")
    _create_test_image(tmp_path / "img.png")
    posted_path = tmp_path / "posted.json"
    new_files = scan_for_new_images(str(tmp_path), str(posted_path))
    assert len(new_files) == 1
    assert new_files[0]["path"].endswith(".png")


def test_load_posted_empty(tmp_path):
    posted_path = tmp_path / "posted.json"
    data = load_posted(str(posted_path))
    assert data == {"hashes": {}}


def test_save_and_load_posted(tmp_path):
    posted_path = tmp_path / "posted.json"
    data = {"hashes": {"abc123": {"file": "test.png", "posted_at": "2026-01-01T00:00:00"}}}
    save_posted(str(posted_path), data)
    loaded = load_posted(str(posted_path))
    assert loaded == data
```

Run: `pytest tests/test_scanner.py -v`
Expected: FAIL

- [ ] **Step 2: Implement scanner.py**

```python
# scanner.py
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def compute_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_posted(posted_path: str) -> dict:
    path = Path(posted_path)
    if not path.exists():
        return {"hashes": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(posted_path: str, data: dict) -> None:
    with open(posted_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mark_as_posted(posted_path: str, file_hash: str, filename: str) -> None:
    data = load_posted(posted_path)
    data["hashes"][file_hash] = {
        "file": filename,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    save_posted(posted_path, data)


def count_images(images_dir: str) -> int:
    return sum(
        1 for p in Path(images_dir).iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def scan_for_new_images(images_dir: str, posted_path: str) -> list[dict]:
    posted = load_posted(posted_path)
    posted_hashes = set(posted["hashes"].keys())
    new_files = []
    for p in sorted(Path(images_dir).iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        file_hash = compute_hash(str(p))
        if file_hash not in posted_hashes:
            new_files.append({"path": str(p), "hash": file_hash, "name": p.name})
    return new_files
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_scanner.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scanner.py tests/test_scanner.py
git commit -m "feat: add image scanner with hash-based dedup"
```

---

### Task 3: Metadata Extractor — A1111 PNG Info

**Files:**
- Create: `metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_metadata.py
from PIL import Image, PngImagePlugin
from metadata import extract_a1111_metadata


def _create_png_with_metadata(path, params_text: str):
    img = Image.new("RGB", (100, 100), "red")
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", params_text)
    img.save(str(path), pnginfo=info)


def test_extract_full_metadata(tmp_path):
    params = (
        "1girl, blue hair, school uniform\n"
        "Negative prompt: bad anatomy, worst quality\n"
        "Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 12345, "
        "Size: 512x768, Model: animagineXL"
    )
    path = tmp_path / "test.png"
    _create_png_with_metadata(path, params)
    result = extract_a1111_metadata(str(path))
    assert "1girl, blue hair, school uniform" in result
    assert "animagineXL" in result
    assert "12345" in result


def test_extract_no_metadata_returns_empty(tmp_path):
    path = tmp_path / "test.png"
    Image.new("RGB", (100, 100)).save(str(path))
    result = extract_a1111_metadata(str(path))
    assert result == ""


def test_extract_from_jpg_returns_empty(tmp_path):
    path = tmp_path / "test.jpg"
    Image.new("RGB", (100, 100)).save(str(path))
    result = extract_a1111_metadata(str(path))
    assert result == ""
```

Run: `pytest tests/test_metadata.py -v`
Expected: FAIL

- [ ] **Step 2: Implement metadata.py**

```python
# metadata.py
from PIL import Image


def extract_a1111_metadata(file_path: str) -> str:
    if not file_path.lower().endswith(".png"):
        return ""
    try:
        img = Image.open(file_path)
        return img.info.get("parameters", "")
    except Exception:
        return ""
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_metadata.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add metadata.py tests/test_metadata.py
git commit -m "feat: add A1111 PNG metadata extractor"
```

---

### Task 4: WD Tagger — Model Download & Inference

**Files:**
- Create: `tagger.py`
- Create: `tests/test_tagger.py`

> **Note:** This is the most complex component. Tests use a real model download (cached after first run). Keep the model download test separate so it can be skipped in CI.

- [ ] **Step 1: Write tests**

```python
# tests/test_tagger.py
import pytest
import numpy as np
from PIL import Image
from tagger import WDTagger, preprocess_image


def test_preprocess_image_output_shape():
    img = Image.new("RGB", (200, 300), "red")
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)
    assert result.dtype == np.float32


def test_preprocess_image_rgba():
    img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)


def test_preprocess_image_square_padding():
    # Wide image: 400x100 -> padded to 400x400 -> resized to 448x448
    img = Image.new("RGB", (400, 100), "blue")
    result = preprocess_image(img, target_size=448)
    assert result.shape == (1, 448, 448, 3)


def test_preprocess_bgr_conversion():
    # Create image with known R=255, G=0, B=0
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    result = preprocess_image(img, target_size=10)
    # After BGR conversion: channel 0 should be B=0, channel 2 should be R=255
    assert result[0, 0, 0, 0] == 0.0    # B
    assert result[0, 0, 0, 2] == 255.0  # R


@pytest.fixture(scope="session")
def tagger():
    return WDTagger(models_dir="models")


def test_tagger_loads_model(tagger):
    assert tagger.session is not None
    assert len(tagger.tag_names) > 0
    assert len(tagger.rating_names) == 4


def test_tagger_predict_returns_tags_and_rating(tagger):
    img = Image.new("RGB", (512, 512), "red")
    tags, rating, rating_confidence = tagger.predict(img)
    assert isinstance(tags, list)
    assert isinstance(rating, str)
    assert rating in ("g", "s", "q", "e")
    assert 0.0 <= rating_confidence <= 1.0
```

Run: `pytest tests/test_tagger.py -v`
Expected: FAIL

- [ ] **Step 2: Implement tagger.py — model download and CSV parsing**

```python
# tagger.py
import csv
from pathlib import Path

import numpy as np
import onnxruntime as rt
from huggingface_hub import hf_hub_download
from PIL import Image

MODEL_REPO = "SmilingWolf/wd-swinv2-tagger-v3"
GENERAL_THRESHOLD = 0.35
CHARACTER_THRESHOLD = 0.85
RATING_MAP = {"general": "g", "sensitive": "s", "questionable": "q", "explicit": "e"}


def preprocess_image(image: Image.Image, target_size: int = 448) -> np.ndarray:
    # RGBA -> composite on white -> RGB
    if image.mode == "RGBA":
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        image = canvas.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Pad to square with white background
    w, h = image.size
    max_dim = max(w, h)
    padded = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
    padded.paste(image, ((max_dim - w) // 2, (max_dim - h) // 2))

    # Resize to target
    padded = padded.resize((target_size, target_size), Image.LANCZOS)

    # To numpy, RGB -> BGR, float32 (no normalization)
    arr = np.array(padded, dtype=np.float32)
    arr = arr[:, :, ::-1]  # RGB -> BGR
    return np.expand_dims(arr, axis=0)


class WDTagger:
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        self._download_model()
        self._load_labels()
        self.session = rt.InferenceSession(
            str(self.models_dir / "model.onnx"),
            providers=["CPUExecutionProvider"],
        )
        input_shape = self.session.get_inputs()[0].shape
        self.target_size = input_shape[1]  # typically 448

    def _download_model(self):
        for filename in ("model.onnx", "selected_tags.csv"):
            target = self.models_dir / filename
            if not target.exists():
                print(f"Скачивание {filename}...")
                hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename=filename,
                    local_dir=str(self.models_dir),
                )

    def _load_labels(self):
        self.tag_names = []
        self.tag_categories = []
        self.rating_names = []
        self.rating_indices = []
        self.general_indices = []
        self.character_indices = []

        csv_path = self.models_dir / "selected_tags.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                name = row["name"]
                category = int(row["category"])
                self.tag_names.append(name)
                self.tag_categories.append(category)
                if category == 9:
                    self.rating_names.append(name)
                    self.rating_indices.append(i)
                elif category == 0:
                    self.general_indices.append(i)
                elif category == 4:
                    self.character_indices.append(i)

    def predict(self, image: Image.Image) -> tuple[list[str], str, float]:
        input_data = preprocess_image(image, self.target_size)
        input_name = self.session.get_inputs()[0].name
        output = self.session.run(None, {input_name: input_data})[0][0]

        # Rating: pick highest confidence
        rating_scores = {self.tag_names[i]: float(output[i]) for i in self.rating_indices}
        best_rating_name = max(rating_scores, key=rating_scores.get)
        rating = RATING_MAP.get(best_rating_name, "g")
        rating_confidence = rating_scores[best_rating_name]

        # General tags
        tags = []
        for i in self.general_indices:
            if output[i] > GENERAL_THRESHOLD:
                tag = self.tag_names[i].replace(" ", "_")
                tags.append(tag)

        # Character tags (higher threshold)
        for i in self.character_indices:
            if output[i] > CHARACTER_THRESHOLD:
                tag = self.tag_names[i].replace(" ", "_")
                tags.append(tag)

        return tags, rating, rating_confidence
```

- [ ] **Step 3: Run tests** (first run downloads model ~467MB)

Run: `pytest tests/test_tagger.py -v`
Expected: PASS (preprocessing tests pass immediately, model tests pass after download)

- [ ] **Step 4: Commit**

```bash
git add tagger.py tests/test_tagger.py
git commit -m "feat: add WD Tagger with model download and inference"
```

---

### Task 5: Uploader — AIBooru API

**Files:**
- Create: `uploader.py`
- Create: `tests/test_uploader.py`

> **Note:** Tests mock the HTTP calls. Real API integration is verified manually.

- [ ] **Step 1: Write tests**

```python
# tests/test_uploader.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
from uploader import AIBooruUploader


@pytest.fixture
def uploader():
    return AIBooruUploader(login="testuser", api_key="testkey")


def test_startup_check_success(uploader):
    with patch("uploader.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert uploader.check_connection() is True


def test_startup_check_auth_failure(uploader):
    with patch("uploader.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        assert uploader.check_connection() is False


def test_upload_file_returns_id(uploader):
    with patch("uploader.requests.post") as mock_post, \
         patch("builtins.open", mock_open(read_data=b"fake image data")):
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 42},
        )
        upload_id = uploader.upload_file("test.png", source="test prompt")
        assert upload_id == 42


def test_create_post_success(uploader):
    with patch("uploader.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": 100})
        post_id = uploader.create_post(
            media_asset_id=99,
            tags="1girl blue_hair",
            rating="s",
            source="test prompt",
        )
        assert post_id == 100


def test_wait_for_processing_success(uploader):
    with patch("uploader.requests.get") as mock_get, \
         patch("uploader.time.sleep"):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {
                "status": "processing",
                "upload_media_assets": [{"id": 99}],
            }),
            MagicMock(status_code=200, json=lambda: {
                "status": "completed",
                "upload_media_assets": [{"id": 99}],
            }),
        ]
        media_id = uploader.wait_for_processing(42)
        assert media_id == 99


def test_upload_file_rate_limited_retries(uploader):
    with patch("uploader.requests.post") as mock_post, \
         patch("builtins.open", mock_open(read_data=b"fake image data")), \
         patch("uploader.time.sleep"):
        mock_post.side_effect = [
            MagicMock(status_code=429, headers={}),
            MagicMock(
                status_code=201,
                json=lambda: {"id": 42},
            ),
        ]
        upload_id = uploader.upload_file("test.png")
        assert upload_id == 42
```

Run: `pytest tests/test_uploader.py -v`
Expected: FAIL

- [ ] **Step 2: Implement uploader.py**

```python
# uploader.py
import time
import requests

BASE_URL = "https://aibooru.online"


class AIBooruUploader:
    def __init__(self, login: str, api_key: str):
        self.auth = (login, api_key)

    def check_connection(self) -> bool:
        try:
            r = requests.get(
                f"{BASE_URL}/posts.json",
                params={"limit": 1},
                auth=self.auth,
                timeout=10,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def upload_file(
        self, file_path: str, source: str = "", max_retries: int = 3
    ) -> int:
        data = {}
        if source:
            data["upload[source]"] = source

        for attempt in range(max_retries):
            with open(file_path, "rb") as f:
                r = requests.post(
                    f"{BASE_URL}/uploads.json",
                    auth=self.auth,
                    files={"upload[files][0]": f},
                    data=data,
                    timeout=60,
                )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 3))
                print(f"  Rate limit, ожидание {wait} сек...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["id"]

        raise RuntimeError(f"Не удалось загрузить файл после {max_retries} попыток")

    def wait_for_processing(self, upload_id: int, timeout: int = 60) -> int:
        start = time.time()
        while time.time() - start < timeout:
            r = requests.get(
                f"{BASE_URL}/uploads/{upload_id}.json",
                auth=self.auth,
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "")
            if status == "completed":
                return data["upload_media_assets"][0]["id"]
            if status in ("error", "failed"):
                raise RuntimeError(f"Upload {upload_id} failed: {data}")
            time.sleep(2)
        raise TimeoutError(f"Upload {upload_id} не завершился за {timeout} сек")

    def create_post(
        self,
        media_asset_id: int,
        tags: str,
        rating: str,
        source: str = "",
        max_retries: int = 3,
    ) -> int:
        payload = {
            "post[upload_media_asset_id]": media_asset_id,
            "post[tag_string]": tags,
            "post[rating]": rating,
        }
        if source:
            payload["post[source]"] = source

        for attempt in range(max_retries):
            r = requests.post(
                f"{BASE_URL}/posts.json",
                auth=self.auth,
                data=payload,
                timeout=30,
            )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 3))
                print(f"  Rate limit, ожидание {wait} сек...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("id", 0)

        raise RuntimeError(f"Не удалось создать пост после {max_retries} попыток")
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_uploader.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add uploader.py tests/test_uploader.py
git commit -m "feat: add AIBooru uploader with two-step upload flow"
```

---

### Task 6: Main Orchestrator

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
# main.py
import sys
import time

from PIL import Image

from config import load_config
from scanner import scan_for_new_images, count_images, mark_as_posted
from tagger import WDTagger
from metadata import extract_a1111_metadata
from uploader import AIBooruUploader

MIN_TAGS = 5
UPLOAD_DELAY = 1.5
POSTED_FILE = "posted.json"


def main():
    cfg = load_config()

    # Startup check
    print("Подключение к AIBooru...", end=" ")
    uploader = AIBooruUploader(cfg["login"], cfg["api_key"])
    if not uploader.check_connection():
        print("ОШИБКА")
        print("Не удалось подключиться к AIBooru. Проверьте интернет и учётные данные.")
        sys.exit(1)
    print("ОК")

    # Load tagger
    print("Загрузка WD Tagger...", end=" ")
    tagger = WDTagger()
    print("ОК")

    # Scan for new images
    new_files = scan_for_new_images(cfg["images_dir"], POSTED_FILE)
    total_images = count_images(cfg["images_dir"])
    print(f"Найдено {total_images} изображений, {len(new_files)} новых")

    if not new_files:
        print("Нет новых изображений для загрузки.")
        return

    uploaded = 0
    skipped = 0
    errors = 0

    for idx, file_info in enumerate(new_files, 1):
        name = file_info["name"]
        path = file_info["path"]
        file_hash = file_info["hash"]
        prefix = f"[{idx}/{len(new_files)}] {name}"

        try:
            # Tag
            img = Image.open(path)
            tags, rating, rating_confidence = tagger.predict(img)

            # Validate tags
            if len(tags) < MIN_TAGS:
                print(f"{prefix} — {len(tags)} тегов — пропущено (недостаточно тегов)")
                skipped += 1
                continue

            # Validate rating
            if rating_confidence < 0.3:
                print(f"{prefix} — пропущено (рейтинг не определён, confidence: {rating_confidence:.2f})")
                skipped += 1
                continue

            # Metadata
            source = extract_a1111_metadata(path)

            # Upload file (step 1)
            tag_string = " ".join(tags)
            upload_id = uploader.upload_file(path, source=source)

            # Wait for processing (step 1.5)
            media_asset_id = uploader.wait_for_processing(upload_id)

            # Create post (step 2)
            post_id = uploader.create_post(
                media_asset_id=media_asset_id,
                tags=tag_string,
                rating=rating,
                source=source,
            )

            mark_as_posted(POSTED_FILE, file_hash, name)
            print(f"{prefix} — {len(tags)} тегов, rating: {rating} — загружено ✓")
            uploaded += 1

        except Exception as e:
            print(f"{prefix} — ошибка: {e}")
            errors += 1

        time.sleep(UPLOAD_DELAY)

    print(f"Итог: {uploaded} загружено, {skipped} пропущено, {errors} ошибок")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test** (manual, requires valid .env with IMAGES_DIR)

Run: `python main.py`
Expected: connects to AIBooru, scans folder, processes images

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main orchestrator script"
```

---

### Task 7: End-to-End Manual Test

- [ ] **Step 1: Prepare test image**

Place one AI-generated PNG (with A1111 metadata) into `IMAGES_DIR`.

- [ ] **Step 2: Run the script**

Run: `python main.py`
Expected output:
```
Подключение к AIBooru... ОК
Загрузка WD Tagger... ОК
Найдено 1 изображений, 1 новых
[1/1] test_image.png — XX тегов, rating: s — загружено ✓
Итог: 1 загружено, 0 пропущено, 0 ошибок
```

- [ ] **Step 3: Verify on aibooru.online**

Open the user's profile on aibooru.online and confirm the post appears with correct tags, rating, and source.

- [ ] **Step 4: Run again to confirm dedup**

Run: `python main.py`
Expected: `Нет новых изображений для загрузки.`

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: complete end-to-end verification"
```
