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
        "artist_tag": values.get("ARTIST_TAG", ""),
    }
