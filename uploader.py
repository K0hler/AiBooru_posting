import os
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from metadata import AIMetadata

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
        self, file_path: str, max_retries: int = 3
    ) -> int:
        filename = os.path.basename(file_path)
        for attempt in range(max_retries):
            with open(file_path, "rb") as f:
                r = requests.post(
                    f"{BASE_URL}/uploads.json",
                    auth=self.auth,
                    files={"upload[files][0]": (filename, f, "image/png")},
                    timeout=60,
                )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 3))
                print(f"  Rate limit, ожидание {wait} сек...")
                time.sleep(wait)
                continue
            if not r.ok:
                raise RuntimeError(f"Upload failed ({r.status_code}): {r.text}")
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
        max_retries: int = 3,
    ) -> int:
        payload = {
            "upload_media_asset_id": media_asset_id,
            "post[tag_string]": tags,
            "post[rating]": rating,
        }

        for attempt in range(max_retries):
            r = requests.post(
                f"{BASE_URL}/posts.json",
                auth=self.auth,
                data=payload,
                headers={"Accept": "application/json"},
                timeout=30,
            )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 3))
                print(f"  Rate limit, ожидание {wait} сек...")
                time.sleep(wait)
                continue
            if not r.ok:
                raise RuntimeError(f"Create post failed ({r.status_code}): {r.text}")
            return r.json().get("id", 0)

        raise RuntimeError(f"Не удалось создать пост после {max_retries} попыток")

    def set_ai_metadata(self, post_id: int, ai_metadata: "AIMetadata") -> None:
        payload = {
            "post[ai_metadata][prompt]": ai_metadata.prompt,
            "post[ai_metadata][negative_prompt]": ai_metadata.negative_prompt,
        }
        if ai_metadata.sampler:
            payload["post[ai_metadata][sampler]"] = ai_metadata.sampler
        if ai_metadata.seed:
            payload["post[ai_metadata][seed]"] = ai_metadata.seed
        if ai_metadata.steps:
            payload["post[ai_metadata][steps]"] = ai_metadata.steps
        if ai_metadata.cfg_scale:
            payload["post[ai_metadata][cfg_scale]"] = ai_metadata.cfg_scale
        if ai_metadata.model_hash:
            payload["post[ai_metadata][model_hash]"] = ai_metadata.model_hash

        r = requests.put(
            f"{BASE_URL}/posts/{post_id}/ai_metadata/create_or_update.json",
            auth=self.auth,
            data=payload,
            timeout=30,
        )
        if r.status_code not in (200, 204):
            print(f"  Предупреждение: не удалось установить AI metadata ({r.status_code})")
