# AIBooru Auto-Poster — Design Spec

## Overview

Python-скрипт для автоматической загрузки AI-сгенерированных изображений из локальной папки на aibooru.online. Тегирование выполняется локально через WD Tagger (ONNX), метаданные A1111 используются как source.

## User Flow

1. Пользователь запускает `python main.py`
2. Скрипт сканирует папку с изображениями
3. Отфильтровывает уже загруженные (по SHA256 хешу из `posted.json`)
4. Для каждого нового изображения:
   - Прогоняет через WD Tagger → теги + рейтинг
   - Валидация: минимум 5 тегов, рейтинг определён
   - Извлекает A1111 метаданные из PNG → поле source
   - Загружает на AIBooru через API
   - При успехе записывает хеш в `posted.json`
5. Выводит итог в консоль

## Architecture

### File Structure

```
AiBooru_posting/
├── main.py           # Вся логика (точка входа)
├── .env              # AIBOORU_LOGIN, AIBOORU_API_KEY, IMAGES_DIR
├── posted.json       # {"hashes": ["sha256_1", "sha256_2", ...]}
├── requirements.txt  # Зависимости
└── models/           # WD Tagger ONNX модель (авто-скачивание)
```

### Configuration (.env)

| Переменная | Описание |
|---|---|
| `AIBOORU_LOGIN` | Имя пользователя на AIBooru |
| `AIBOORU_API_KEY` | API-ключ (генерируется в профиле) |
| `IMAGES_DIR` | Абсолютный путь к папке с изображениями |

### Dependencies

| Пакет | Назначение |
|---|---|
| `requests` | HTTP-запросы к AIBooru API |
| `onnxruntime` | Инференс WD Tagger модели |
| `Pillow` | Чтение изображений + A1111 метаданных из PNG |
| `python-dotenv` | Загрузка конфигурации из .env |
| `numpy` | Обработка тензоров для WD Tagger |
| `huggingface_hub` | Скачивание модели WD Tagger при первом запуске |

## Components

### 1. Scanner

- Читает все файлы из `IMAGES_DIR` (PNG, JPG, WEBP)
- Вычисляет SHA256 хеш каждого файла
- Сравнивает с `posted.json`, возвращает только новые
- `posted.json` формат: `{"hashes": ["sha256_1", "sha256_2", ...]}`

### 2. WD Tagger

- Модель: `wd-swinv2-tagger-v3` с HuggingFace
- При первом запуске скачивает модель в `models/`
- Вход: изображение (resize до 448x448, нормализация)
- Выход: список тегов с confidence > 0.35, рейтинг
- Маппинг рейтинга: `general` → `g`, `sensitive` → `s`, `questionable` → `q`, `explicit` → `e`

### 3. Validator

- Минимум 5 тегов от WD Tagger, иначе пропуск с предупреждением
- Рейтинг должен быть определён (хотя бы один класс выше порога), иначе пропуск
- В консоль: имя файла + причина пропуска

### 4. Metadata Extractor

- Читает PNG tEXt chunk `parameters` (формат A1111)
- Извлекает: prompt, negative prompt, model, seed, sampler, steps, CFG
- Форматирует как строку для поля `source` на AIBooru

### 5. Uploader

- Эндпоинт: `POST https://aibooru.online/uploads.json`
- Аутентификация: HTTP Basic Auth (`login:api_key`)
- Тело (multipart form):
  - `upload[files][0]` — файл
  - `upload[tag_string]` — теги через пробел
  - `upload[rating]` — `g`/`s`/`q`/`e`
  - `upload[source]` — A1111 метаданные
- Пауза 1.5 сек между загрузками (rate limit: 1 req/sec для обычных пользователей)
- Обработка ответов:
  - `200/204` → успех
  - `429` → rate limit, ждём 2 сек, переходим к следующему
  - Остальные ошибки → лог в консоль, пропуск

## Console Output

```
Найдено 12 изображений, 3 новых
[1/3] image_001.png — 24 тега, rating: s — загружено ✓
[2/3] image_002.png — 2 тега — пропущено (недостаточно тегов)
[3/3] image_003.png — 18 тегов, rating: q — ошибка 422 (дубликат)
Итог: 1 загружено, 1 пропущено, 1 ошибка
```

## Error Handling

- Ошибки API → лог в консоль, файл пропускается, скрипт продолжает
- Невалидное изображение (не удалось прочитать) → лог, пропуск
- Нет .env или отсутствуют переменные → ошибка при старте с понятным сообщением
- Нет интернета / AIBooru недоступен → ошибка при старте

## Security

- API-ключ хранится только в `.env` (в .gitignore)
- Никаких секретов в коде или логах
