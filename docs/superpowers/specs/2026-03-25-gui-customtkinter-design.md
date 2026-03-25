# AIBooru Auto-Poster: GUI на CustomTkinter

## Цель

Обернуть существующий CLI-скрипт в графический интерфейс на CustomTkinter. CLI (`main.py`) остаётся рабочим, GUI — альтернативная точка входа.

## Требования

- Выбор папки с изображениями (file dialog)
- Поле ввода лимита постов (пустое = все)
- Кнопки "Запустить" и "Стоп"
- Прогресс-бар с текстовым счётчиком
- Текстовый лог с подсветкой ошибок
- Чекбокс "Останавливаться при ошибках"
- Тёмная тема
- Credentials остаются в `.env`

## Структура файлов

```
gui.py      — CustomTkinter приложение, точка входа GUI
worker.py   — рабочий поток (UploadWorker), пайплайн загрузки
main.py     — без изменений (CLI)
```

Бизнес-модули (`scanner.py`, `tagger.py`, `metadata.py`, `uploader.py`) не изменяются. Worker импортирует и использует их напрямую.

**Минимальный рефакторинг `config.py`:** заменить `sys.exit(1)` на `raise ValueError(...)`. `main.py` оборачивает вызов в `try/except ValueError` с `sys.exit(1)` для сохранения поведения CLI. Worker ловит `ValueError` и отправляет `log` с `level=error` + `finished`.

## Архитектура: Queue-based (producer/consumer)

### Потоки

- **GUI-поток** (main thread) — CustomTkinter event loop, poll'ит `event_queue` через `after()` каждые ~100мс.
- **Worker-поток** (`UploadWorker`, `threading.Thread`) — выполняет пайплайн загрузки, пишет события в `event_queue`.

### Протокол событий

Worker кладёт в `event_queue` словари с полем `type`:

| type | Поля | Назначение |
|------|-------|-----------|
| `log` | `message`, `level` (info/warning/error) | Строка в лог |
| `progress` | `current`, `total` | Обновление прогресс-бара |
| `started` | `total` | Процесс начался, блокируем UI-контролы |
| `finished` | `uploaded`, `skipped`, `errors` | Процесс завершён, разблокируем UI |
| `error_pause` | `message`, `file` | Ошибка + "останавливаться при ошибках" включён |

### Обратный канал

Для `error_pause`: GUI показывает диалог (Пропустить / Остановить), кладёт ответ (`skip` / `abort`) в `response_queue`. Worker блокируется на `response_queue.get()`.

### Остановка

`threading.Event` (`stop_event`). Кнопка "Стоп" вызывает `stop_event.set()`. Worker проверяет `stop_event.is_set()` между изображениями и после каждого шага.

Для interruptible sleep: `stop_event.wait(timeout=UPLOAD_DELAY)` вместо `time.sleep(UPLOAD_DELAY)`. Это обеспечивает мгновенную реакцию на "Стоп".

## GUI-компоновка

Окно: ~900x500, resizable, `customtkinter.set_appearance_mode("dark")`.

### Левая панель (~250px, фиксированная)

1. **Папка**: `CTkEntry` (readonly) + кнопка "Обзор" (`filedialog.askdirectory`)
2. **Лимит постов**: `CTkEntry`, числовой ввод. Пустое = все новые изображения
3. **Чекбокс**: "Останавливаться при ошибках" (`CTkCheckBox`)
4. **Кнопка "Запустить"**: `CTkButton`, зелёный акцент
5. **Кнопка "Стоп"**: `CTkButton`, неактивна до запуска
6. **Прогресс-бар**: `CTkProgressBar` + текст "0 / 0"

### Правая панель (растягивается)

- **Лог**: `CTkTextbox`, readonly, моноширинный шрифт
- Ошибки подсвечиваются красным через текстовые теги

### Блокировка при работе

При запуске: disable "Обзор", лимит, "Запустить", чекбокс. Enable "Стоп".
При завершении/остановке: обратно.

## Worker (UploadWorker)

Класс `UploadWorker(threading.Thread)`:

**Параметры конструктора:**
- `images_dir: str`
- `limit: int | None`
- `stop_on_error: bool`
- `event_queue: queue.Queue`
- `response_queue: queue.Queue`
- `stop_event: threading.Event`

**Метод `run()`** повторяет логику `main.py`:
1. `log` — "Подключение к AIBooru..."
2. Проверка соединения (`uploader.check_connection()`)
3. Загрузка WD Tagger
4. Сканирование папки, применение лимита
5. `started` с `total`
6. Цикл по изображениям: тегирование → upload → create post → metadata
7. Между итерациями: `stop_event.is_set()` — если `True`, выход
8. При ошибке: если `stop_on_error` — `error_pause` + ожидание `response_queue.get()`; иначе — `log` с `level=error`, продолжение
9. `finished` со статистикой

Все `print()` из `main.py` заменяются на `event_queue.put()`.

### Перехват stdout

`uploader.py` и `tagger.py` содержат `print()` вызовы (rate-limit, warnings, model download). Для их перехвата worker использует контекстный менеджер, перенаправляющий `sys.stdout` в обёртку, которая пишет в `event_queue` как `log` события. Существующие модули не модифицируются.

## GUI: дополнительное поведение

### Закрытие окна во время работы

При `WM_DELETE_WINDOW`: вызвать `stop_event.set()`, подождать `worker.join(timeout=3)`, затем `destroy()`. Worker — daemon thread (`daemon=True`), чтобы процесс не зависал.

### Валидация ввода

При нажатии "Запустить": проверить что папка выбрана, лимит — положительное целое или пустое. При ошибке — показать `CTkMessageBox` / лог с ошибкой, не запускать worker.

### Предзаполнение папки из .env

При запуске GUI: попытаться загрузить `IMAGES_DIR` из `.env` и предзаполнить поле папки. Пользователь может изменить через "Обзор".

### Ограничение лога

Максимум 5000 строк в `CTkTextbox`. При превышении — удалять старые строки сверху.

## Зависимости

Новая зависимость: `customtkinter`. Добавить в `requirements.txt`.

## Ветка

Разработка на ветке `dev`.
