# tests/test_config.py
import pytest
from config import load_config


def test_load_config_returns_all_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIBOORU_LOGIN=testuser\n"
        "AIBOORU_API_KEY=testkey123\n"
        "IMAGES_DIR=C:/images\n"
    )
    cfg = load_config(str(env_file))
    assert cfg["login"] == "testuser"
    assert cfg["api_key"] == "testkey123"
    assert cfg["images_dir"] == "C:/images"


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
