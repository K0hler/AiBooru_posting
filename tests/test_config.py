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
