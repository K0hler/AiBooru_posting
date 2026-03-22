# AIBooru Auto-Poster — Design Spec

## Overview

Python-скрипт для автоматической загрузки AI-сгенерированных изображений из локальной папки на aibooru.online. Тегирование выполняется локально через WD Tagger (ONNX), метаданные A1111 используются как source.

## User Flow

1. Пользователь запускает `python main.py`
2. Скрипт проверяет подключение к AIBooru и валидность учётных данных (`GET /posts.json?limit=1`)
3. Сканирует папку с изображениями
4. Отфильтровывает уже загруженные (по SHA256 хешу из `posted.json`)
5. Для каждого нового изображения:
   - Прогоняет через WD Tagger → теги + рейтинг
   - Валидация: минимум 5 тегов, рейтинг определён
   - Извлекает A1111 метаданные из PNG → поле source (для не-PNG — source пустой)
   - Загружает файл на AIBooru (`POST /uploads.json`)
   - Ожидает завершения обработки (polling `GET /uploads/{id}.json`)
   - Создаёт пост (`POST /posts.json`) с тегами, рейтингом и source
   - При успехе записывает хеш в `posted.json`
6. Выводит итог в консоль

## Architecture

### File Structure

```
AiBooru_posting/
├── main.py           # Вся логика (точка входа)
├── .env              # AIBOORU_LOGIN, AIBOORU_API_KEY, IMAGES_DIR
├── posted.json       # Хеши уже загруженных файлов (см. формат ниже)
├── requirements.txt  # Зависимости
└── models/           # WD Tagger ONNX модель + selected_tags.csv (авто-скачивание)
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
- `posted.json` формат: `{"hashes": {"sha256_hex": {"file": "filename.png", "posted_at": "ISO8601"}, ...}}`

### 2. WD Tagger

- Модель: `wd-swinv2-tagger-v3` с HuggingFace
- При первом запуске скачивает `model.onnx` и `selected_tags.csv` в `models/`
- Preprocessing:
  - RGBA → композитинг на белый фон → RGB
  - Padding до квадрата (белый фон)
  - Resize до размера из input shape модели (448x448)
  - RGB → BGR
  - Float32, значения 0-255 (без нормализации)
- Теги из `selected_tags.csv`: маппинг индексов модели на имена тегов и категории
- Пороги confidence:
  - Общие теги (general): > 0.35
  - Теги персонажей (character): > 0.85
- Рейтинг: из категории rating в CSV (category == 9), берётся класс с максимальным confidence
- Маппинг рейтинга: `general` → `g`, `sensitive` → `s`, `questionable` → `q`, `explicit` → `e`

### 3. Validator

- Минимум 5 тегов от WD Tagger, иначе пропуск с предупреждением
- Рейтинг должен быть определён (хотя бы один класс выше порога), иначе пропуск
- В консоль: имя файла + причина пропуска

### 4. Metadata Extractor

- Читает PNG tEXt chunk `parameters` (формат A1111)
- Извлекает: prompt, negative prompt, model, seed, sampler, steps, CFG
- Форматирует как строку для поля `source` на AIBooru
- Для не-PNG файлов (JPG, WEBP): source остаётся пустым, загрузка продолжается без source

### 5. Uploader (двухшаговый процесс)

**Шаг 1: Загрузка файла**
- Эндпоинт: `POST https://aibooru.online/uploads.json`
- Аутентификация: HTTP Basic Auth (`login:api_key`)
- Тело (multipart form):
  - `upload[files][0]` — файл изображения
  - `upload[source]` — A1111 метаданные (опционально)
- Ответ содержит `id` загрузки и `upload_media_assets`

**Шаг 1.5: Ожидание обработки**
- Polling: `GET https://aibooru.online/uploads/{id}.json`
- Ждём пока `status` станет `completed`
- Интервал polling: 2 сек, таймаут: 60 сек
- Из ответа извлекаем `upload_media_asset_id`

**Шаг 2: Создание поста**
- Эндпоинт: `POST https://aibooru.online/posts.json`
- Тело (JSON):
  - `post[upload_media_asset_id]` — ID из шага 1.5
  - `post[tag_string]` — теги через пробел
  - `post[rating]` — `g`/`s`/`q`/`e`
  - `post[source]` — A1111 метаданные
- Пауза 1.5 сек между загрузками (rate limit: 1 req/sec для обычных пользователей)

**Обработка ответов:**
- `200/204` → успех
- `429` → rate limit, ждём (Retry-After header или 3 сек), повторяем тот же файл
- Остальные ошибки → лог в консоль, пропуск файла

### 6. Startup Check

- При запуске: `GET https://aibooru.online/posts.json?limit=1` с авторизацией
- Проверяет одновременно: интернет, доступность AIBooru, валидность credentials
- При неудаче → понятное сообщение и выход

## Console Output

```
Подключение к AIBooru... ОК
Найдено 12 изображений, 3 новых
[1/3] image_001.png — 24 тега, rating: s — загружено ✓
[2/3] image_002.png — 2 тега — пропущено (недостаточно тегов)
[3/3] image_003.png — 18 тегов, rating: q — ошибка 422 (дубликат)
Итог: 1 загружено, 1 пропущено, 1 ошибка
```

## Error Handling

- Ошибки API → лог в консоль, файл пропускается, скрипт продолжает
- 429 (rate limit) → retry того же файла после паузы
- Невалидное изображение (не удалось прочитать) → лог, пропуск
- Нет .env или отсутствуют переменные → ошибка при старте с понятным сообщением
- Нет интернета / AIBooru недоступен / невалидные credentials → ошибка при старте (startup check)

## Security

- API-ключ хранится только в `.env` (в .gitignore)
- Никаких секретов в коде или логах
