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
