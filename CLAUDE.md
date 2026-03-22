# AIBooru Auto-Poster

## Project Overview

Python-скрипт для автоматической загрузки AI-сгенерированных изображений на aibooru.online.
Тегирование через WD Tagger (ONNX, локально), метаданные A1111 используются как source.

## Architecture

- `main.py` — точка входа, оркестрация
- `config.py` — загрузка .env
- `scanner.py` — сканирование папки, SHA256 дедупликация
- `tagger.py` — WD Tagger v3: preprocessing, инференс
- `metadata.py` — извлечение A1111 метаданных из PNG
- `uploader.py` — AIBooru API (двухшаговый: upload → poll → create post)

## Key Details

- AIBooru API — Danbooru-совместимый, но с нюансами:
  - Нельзя отправлять file и source одновременно в `/uploads.json`
  - `upload_media_asset_id` для создания поста берётся из `upload_media_assets[0]["id"]`
  - Source ограничен 1200 символами
- WD Tagger модель: `SmilingWolf/wd-swinv2-tagger-v3` (~467MB, скачивается при первом запуске)
- Preprocessing: RGBA→белый фон→RGB, padding до квадрата, resize 448x448, RGB→BGR, float32 без нормализации
- Пороги: general tags > 0.35, character tags > 0.85

## Commands

```bash
# Запуск
python main.py

# Тесты
pytest tests/ -v
```

## Configuration

`.env` файл:
```
AIBOORU_LOGIN=<username>
AIBOORU_API_KEY=<api_key>
IMAGES_DIR=<path_to_images>
```

## Specs & Plans

- `docs/superpowers/specs/2026-03-22-aibooru-auto-poster-design.md`
- `docs/superpowers/plans/2026-03-22-aibooru-auto-poster.md`
