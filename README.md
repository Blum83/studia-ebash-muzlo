# songgen

Свой Suno на своей видеокарте: идея → Claude пишет название, стиль и текст → [ACE-Step 1.5](https://github.com/ACE-Step/ACE-Step-1.5) генерирует песню с вокалом → библиотека с плеером.

- Бэкенд: Python, FastAPI, uv. Модель грузится один раз и держится в памяти, задачи идут по очереди (одна на GPU).
- Фронт: React + Vite, отдаётся тем же сервером.
- История — SQLite (`data/songgen.db`), треки — `data/outputs/` (WAV + MP3).
- ACE-Step подключён git-сабмодулем, зафиксирован на коммите `ca1e85f`.

## Требования

- Windows 10/11 или Linux, NVIDIA GPU от 8 ГБ (проверено на RTX 5070 12 ГБ), свежий драйвер.
- [uv](https://docs.astral.sh/uv/), Node.js 20+, ffmpeg в `PATH`, git.
- ~12 ГБ на диске под модели.
- Для текстов: залогиненный [Claude Code](https://code.claude.com) (`claude`) **или** `ANTHROPIC_API_KEY`. Без этого всё работает, но тексты пишешь сам (режим Advanced).

## Запуск

```bat
git clone --recursive https://github.com/Blum83/studia-ebash-muzlo.git
cd studia-ebash-muzlo
start.bat
```

`start.bat` сам: создаёт `.env` из `.env.example`, ставит зависимости, собирает фронт, при первом запуске качает модели (~11 ГБ, проверяет VRAM), запускает сервер и открывает http://127.0.0.1:8000.

Первая загрузка модели после старта — ~3–4 минуты (в сайдбаре «Модель загружается…»). Задачи, отправленные в это время, просто ждут в очереди.

### Вручную

```bash
cd backend
uv sync
uv run songgen download            # модели в ../models
PYTHONUTF8=1 uv run songgen serve  # http://127.0.0.1:8000
```

Разработка фронта с hot reload (бэкенд должен быть запущен, `/api` проксируется на :8000):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Одна песня без сервера:

```bash
uv run songgen generate --caption "synthwave, female vocal, 110 bpm" --lyrics-file song.txt --duration 60 --language ru
```

## Как пользоваться

- **Simple** — описываешь идею, выбираешь голос, жмёшь Create. Claude пишет название, стиль и текст, генерация стартует сама.
- **Advanced** — свой текст, стиль, длительность, seed, язык, инструментал. «✨ Написать с Claude» заполняет поля, их можно поправить.
- Текст размечается тегами секций на английском: `[Intro] [Verse 1] [Pre-Chorus] [Chorus] [Bridge] [Outro]`, подача — через дефис: `[Chorus - shouted, group vocals]`, `[Outro - whispered]`. Без вокала — `[Instrumental]`.
- Голос задаётся в стиле (`male vocal, raspy`, `female rap` …) — готовых пресетов голоса у модели нет. Один и тот же seed даёт похожее звучание.
- Темп — пиши в стиле `95 bpm`, он передаётся модели явно.
- В библиотеке: ⟳ **Remix** — те же настройки, новый seed; ⋯ → «Повторить точно» (тот же seed), «Открыть в редакторе», WAV, удалить.
- Название, если не задано, берётся из первой строки припева.

Скорость на RTX 5070: трек 30 с — ~30 с, 2 мин — ~1,5 мин. Большая часть времени — LM-планировщик ACE-Step (на Windows он медленный).

## Настройки (`.env`)

| Переменная | По умолчанию | Что это |
|---|---|---|
| `ACESTEP_DIT_MODEL` | `acestep-v15-turbo` | Генератор. `acestep-v15-xl-turbo` — лучше, но нужно ≥ 16–20 ГБ |
| `ACESTEP_LM_MODEL` | `acestep-5Hz-lm-0.6B` | Планировщик структуры/темпа. Пусто = выключить (быстрее, ~10 с на трек, качество ниже) |
| `ACESTEP_LM_BACKEND` | `pt` | `vllm` — быстрее, только Linux |
| `ACESTEP_QUANTIZATION` | `int8_weight_only` | `none`, если VRAM хватает |
| `OFFLOAD_TO_CPU` | `true` | Выгружать VAE/текст-энкодер в RAM между шагами |
| `LYRICS_PROVIDER` | `auto` | `auto` — API-ключ, если задан, иначе CLI `claude`; `api`, `cli`, `off` |
| `ANTHROPIC_API_KEY` | — | Ключ Anthropic API (необязательно) |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Модель для API-режима |
| `CLAUDE_CLI_MODEL` | — | Модель для CLI-режима, пусто = дефолт Claude Code |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Авторизации нет — не открывай наружу |
| `MODELS_DIR`, `OUTPUT_DIR`, `DB_PATH` | `models/`, `data/outputs/`, `data/songgen.db` | Абсолютные пути |

## Если что-то не так

- **`UnicodeEncodeError: 'charmap' codec`** — консоль Windows не умеет эмодзи из логов ACE-Step. Запускай с `PYTHONUTF8=1` (в `start.bat` уже есть).
- **`CUDA not visible` / генерация на CPU** — обнови драйвер NVIDIA. Проверка: `uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"`. RTX 50xx нужен torch с cu128 — он ставится автоматически.
- **`CUDA out of memory`** — уменьши длительность, выключи LM (`ACESTEP_LM_MODEL=`), включи `OFFLOAD_DIT_TO_CPU=true`. Ошибка видна прямо в карточке задачи.
- **`ffmpeg not found`** — `winget install Gyan.FFmpeg`, перезапусти терминал.
- **«Claude не подключён»** — проверь `claude -p "hi"` в терминале (должен ответить без логина) или задай `ANTHROPIC_API_KEY`.
- **`uv sync` падает с «file is being used by another process»** — сервер ещё запущен, останови его.
- **Темп/тональность странные** — маленькая LM иногда уходит в крайности (30/300 BPM). Укажи `NN bpm` в стиле.
- **Сообщение `Skipping import of cpp extensions … torchao`** — безвредно, INT8 работает.

## Структура

```
backend/app/
  engines/      MusicEngine (интерфейс) + ACE-Step 1.5; новый движок = новый класс + строка в get_engine
  lyrics/       Claude: API или CLI
  api.py jobs.py db.py audio.py cli.py config.py
backend/tests/  pytest, движок замокан
frontend/src/   CreatePanel, TrackList, Player
third_party/    ACE-Step-1.5 (сабмодуль)
```

Тесты: `cd backend && uv run pytest && uv run ruff check .`

Задел на потом: режимы cover/repaint (`GenerateRequest.task`), LoRA и другие параметры движка (`GenerateRequest.extra`), второй движок (YuE, MiniMax) через `MusicEngine`.
