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
