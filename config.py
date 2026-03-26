# config.py
from dotenv import dotenv_values


def load_config(env_path: str = ".env") -> dict:
    values = dotenv_values(env_path)
    required = ["AIBOORU_LOGIN", "AIBOORU_API_KEY"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ValueError(f"Отсутствуют переменные в .env: {', '.join(missing)}")
    return {
        "login": values["AIBOORU_LOGIN"],
        "api_key": values["AIBOORU_API_KEY"],
        "images_dir": values.get("IMAGES_DIR", ""),
        "artist_tag": values.get("ARTIST_TAG", ""),
    }
