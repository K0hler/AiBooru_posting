# main.py
import sys
import time

from PIL import Image

from config import load_config
from metadata import extract_a1111_metadata
from scanner import scan_for_new_images, count_images, mark_as_posted
from tagger import WDTagger
from uploader import AIBooruUploader

MIN_TAGS = 5
UPLOAD_DELAY = 1.5
POSTED_FILE = "posted.json"


def main():
    try:
        cfg = load_config()
    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    # Startup check
    print("Подключение к AIBooru...", end=" ")
    uploader = AIBooruUploader(cfg["login"], cfg["api_key"])
    if not uploader.check_connection():
        print("ОШИБКА")
        print("Не удалось подключиться к AIBoору. Проверьте интернет и учётные данные.")
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

    # Ask user how many images to upload
    limit_input = input(f"Сколько изображений загрузить? (1-{len(new_files)}, Enter — все): ").strip()
    if limit_input:
        try:
            limit = int(limit_input)
            if limit < 1:
                print("Число должно быть >= 1.")
                return
            new_files = new_files[:limit]
        except ValueError:
            print("Некорректный ввод.")
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

            # Extract AI metadata
            ai_meta = extract_a1111_metadata(path)

            # Upload file (step 1)
            tag_string = " ".join(tags)
            if cfg["artist_tag"]:
                tag_string += " " + cfg["artist_tag"]
            upload_id = uploader.upload_file(path)

            # Wait for processing (step 1.5)
            media_asset_id = uploader.wait_for_processing(upload_id)

            # Create post (step 2)
            post_id = uploader.create_post(
                media_asset_id=media_asset_id,
                tags=tag_string,
                rating=rating,
            )

            # Set AI metadata (step 3)
            if ai_meta.is_present():
                uploader.set_ai_metadata(post_id, ai_meta)

            mark_as_posted(POSTED_FILE, file_hash, name)
            print(f"{prefix} -- {len(tags)} тегов, rating: {rating} -- загружено OK")
            uploaded += 1

        except Exception as e:
            print(f"{prefix} — ошибка: {e}")
            errors += 1

        time.sleep(UPLOAD_DELAY)

    print(f"Итог: {uploaded} загружено, {skipped} пропущено, {errors} ошибок")


if __name__ == "__main__":
    main()
