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
