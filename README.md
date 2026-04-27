# ДТП-ассистент

AI-агент для консультаций по дорожно-транспортным происшествиям. Помогает пользователю пошагово оформить ДТП, определить возможность Европротокола, разрешить разногласия между участниками и ответить на вопросы по ОСАГО.

Поддерживает текстовый ввод, а также **голосовые сообщения** (распознавание речи через SaluteSpeech, синтез ответа). Модуль голосового ввода-вывода находится в разработке и требует дополнительной настройки API-ключей SaluteSpeech.

---

## Содержание

- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Интеграция с бэкендом](#интеграция-с-бэкендом)
- [Локальное тестирование](#локальное-тестирование)
- [Архитектура](#архитектура)
- [Известные ограничения](#известные-ограничения)

---

## Структура проекта

```
├── agent/
│   ├── core.py              # Публичный API: run_agent(), rate_answer(), process_voice_message()
│   ├── algorithm.py         # Загрузка и нарезка алгоритма по блокам
│   ├── generator.py         # Генерация ответа через GigaChat
│   ├── history.py           # Адаптивное формирование истории диалога
│   ├── meta_classifier.py   # LLM-классификатор намерений
│   └── retriever.py         # Категориально-зависимый RAG
│
├── services/
│   ├── dialog_flow.py       # Детерминированная машина состояний диалога
│   ├── gigachat_client.py   # Function Calling для извлечения фактов о ДТП
│   ├── salutespeech_client.py # Клиент SaluteSpeech API (TTS/STT) [в разработке]
│   └── scheme_flow.py       # Пошаговый мастер создания схемы ДТП
│
├── utils/
│   ├── audio_utils.py       # Нормализация аудио (PCM 16bit, 16kHz, моно)
│   ├── catalog.py           # Каталог поддерживаемых моделей GigaChat
│   ├── knowledge_loader.py  # Загрузка файлов (.md, .txt, .json, .pdf)
│   └── prompts.py           # Структурированные промпты с ограничителями
│
├── evaluation/
│   ├── critic.py            # AI-критик: оценка качества ответа
│   └── self_check.py        # Самопроверка и улучшение ответа
│
├── rag/
│   ├── retrieval.py         # Поиск контекста в векторных базах
│   ├── feedback_db.py       # Сохранение хороших Q&A для дообучения
│   └── init_db.py           # Инициализация ChromaDB
│
├── templates/
│   ├── matcher.py           # Regex-матчер шаблонных ответов
│   ├── responses.py         # Шаблоны частых вопросов (без LLM)
│   └── llm_classifier.py    # LLM-классификатор шаблонов
│
├── Docs_md/                 # Документы для RAG-базы
├── chroma_db/               # Основная векторная база (генерируется через build_db.py)
├── chroma_feedback/         # База дообучения на хороших Q&A (генерируется)
│
├── build_db.py              # Умная сборка RAG-индекса с манифестами
├── config.py                # Конфигурация через переменные окружения (.env)
├── main_AI.py               # CLI для локального тестирования
└── requirements.txt         # Зависимости проекта
```

---

## Требования

- Python 3.10+
- Токен GigaChat ([получить здесь](https://developers.sber.ru/gigachat))
- API-ключи SaluteSpeech (для голосового ввода-вывода, опционально)

```bash
gigachat
langchain-community
langchain-huggingface
chromadb
sentence-transformers
python-dotenv
pypdf>=4.0.0
requests>=2.31.0
```

---

## Установка

```bash
git clone <repo-url>
cd dtp-agent
pip install -r requirements.txt
```

---

## Конфигурация

Токен GigaChat и API-ключи SaluteSpeech передаются через переменные окружения. **Никогда не вписывай токены в код и не коммить `.env` в git.**

```bash
# Linux / Mac
export GIGACHAT_AUTH="ваш_токен"
export SALUTESPEECH_CLIENT_ID="ваш_client_id"
export SALUTESPEECH_CLIENT_SECRET="ваш_client_secret"

# Windows
set GIGACHAT_AUTH=ваш_токен
set SALUTESPEECH_CLIENT_ID=ваш_client_id
set SALUTESPEECH_CLIENT_SECRET=ваш_client_secret
```

Или через `.env` файл (убедись что он добавлен в `.gitignore`):

```env
GIGACHAT_AUTH=ваш_токен
SALUTESPEECH_CLIENT_ID=ваш_client_id
SALUTESPEECH_CLIENT_SECRET=ваш_client_secret
```

```bash
# .gitignore
.env
chroma_db/
chroma_feedback/
*.pyc
__pycache__/
```

---

## Интеграция с бэкендом

Агент предоставляет методы для текстового и голосового взаимодействия. **История диалога хранится на стороне бэкенда** и передаётся в каждый запрос.

### Импорт

```python
from agent.core import run_agent, rate_answer, process_voice_message
```

---

### `run_agent` — получить ответ агента (текст)

```python
run_agent(
    query: str,
    history: list = None,
    db=None,
    feedback_db=None,
    state: dict = None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `query` | `str` | Сообщение пользователя |
| `history` | `list` | История диалога — список `{"query": ..., "answer": ...}`. Бэкенд хранит и передаёт сам. |
| `db` | ChromaDB | Основная RAG-база. Передать `None` если не используется. |
| `feedback_db` | ChromaDB | База дообучения. Передать `None` если не используется. |
| `state` | `dict` | Состояние машины состояний диалога (опционально, возвращается в ответе). |

**Возвращает:**

```python
{
    "answer": str,           # ответ агента
    "source": str,           # откуда пришёл ответ: "template" | "llm" | "filter" | "error"
    "category": str | None,  # категория намерения (например, "dtp_registration")
    "state": dict,           # обновлённое состояние диалога (для передачи в следующий запрос)
}
```

**Пример:**

```python
# Первое сообщение — история пустая
response = run_agent(query="попал в ДТП, что делать?")
# {"answer": "Сохраняйте спокойствие...", "source": "llm"}

# Бэкенд сохраняет пару в своей БД
history = [{"query": "попал в ДТП, что делать?", "answer": response["answer"]}]

# Следующее сообщение — передаём историю
response = run_agent(query="пострадавших нет", history=history)
```

**Значения `source`:**

| Значение | Описание |
|----------|----------|
| `template` | Ответ из шаблона (regex, без вызова LLM) |
| `llm` | Ответ сгенерирован моделью |
| `filter` | Запрос не по теме ДТП |
| `error` | Произошла ошибка |

---

### `process_voice_message` — обработать голосовое сообщение [в разработке]

**Модуль голосового ввода-вывода находится в стадии разработки.** Требуется настройка API-ключей SaluteSpeech и тестирование в реальных условиях.

```python
process_voice_message(
    audio_bytes: bytes,
    content_type: str = "audio/ogg;codecs=opus",
    history: list = None,
    db=None,
    feedback_db=None,
    state: dict = None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `audio_bytes` | `bytes` | Аудиосообщение пользователя (OGG/Opus, WAV) |
| `content_type` | `str` | MIME-тип аудио (по умолчанию `"audio/ogg;codecs=opus"`) |
| `history` | `list` | История диалога (как в `run_agent`) |
| `db` | ChromaDB | Основная RAG-база |
| `feedback_db` | ChromaDB | База дообучения |
| `state` | `dict` | Состояние машины состояний диалога |

**Возвращает:**

```python
{
    "answer": str,              # текстовый ответ агента
    "source": str,              # источник ответа
    "category": str | None,     # категория намерения
    "state": dict,              # обновлённое состояние
    "transcribed_text": str,    # распознанный текст
    "audio_response": bytes,    # аудиответ (синтезированный голос)
    "audio_media_type": str,    # MIME-тип аудиответа (например, "audio/opus")
}
```

**Пример:**

```python
# Бэкенд получает аудиосообщение от пользователя
with open("user_message.ogg", "rb") as f:
    audio_bytes = f.read()

response = process_voice_message(
    audio_bytes=audio_bytes,
    content_type="audio/ogg;codecs=opus",
)

# Отправить текстовый ответ в UI
print(response["transcribed_text"])  # "попал в ДТП, что делать?"
print(response["answer"])            # "Сохраняйте спокойствие..."

# Отправить аудиответ пользователю
send_audio_to_user(
    audio=response["audio_response"],
    media_type=response["audio_media_type"],
)
```

---

### `rate_answer` — оценить ответ

Вызывается после того как пользователь поставил оценку. Бэкенд передаёт сюда `query` и `answer`, которые сам достаёт из своей БД.

```python
rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `query` | `str` | Вопрос пользователя (из БД бэкенда) |
| `answer` | `str` | Ответ агента (из БД бэкенда) |
| `rating` | `int` | Оценка пользователя от 0 до 5 |
| `feedback_db` | ChromaDB | База дообучения. При оценке ≥4 хороший ответ сохраняется для улучшения RAG. |

**Возвращает:**

```python
{
    "critic_score": int,    # оценка AI-критика от 1 до 5
    "critic_comment": str,  # комментарий критика
}
```

**Пример:**

```python
# Пользователь поставил оценку 5
# Бэкенд достаёт из своей БД нужный query и answer
result = rate_answer(
    query="попал в ДТП, что делать?",
    answer="Включите аварийку...",
    rating=5,
)
# {"critic_score": 4, "critic_comment": "Хороший ответ, но..."}
```

---

### Пример Django view

```python
import json
from django.http import JsonResponse
from django.views import View
from agent.core import run_agent, rate_answer, process_voice_message


class ChatView(View):
    def post(self, request):
        data = json.loads(request.body)

        # История берётся из БД бэкенда
        history = list(
            Message.objects.filter(session_id=data["session_id"])
            .values("query", "answer")
            .order_by("created_at")
        )

        # Состояние диалога хранится в сессии или БД
        state = data.get("state")

        response = run_agent(
            query=data["query"],
            history=history,
            state=state,
        )

        # Бэкенд сохраняет пару сам
        Message.objects.create(
            session_id=data["session_id"],
            query=data["query"],
            answer=response["answer"],
            source=response["source"],
            category=response.get("category"),
        )

        return JsonResponse({
            "answer": response["answer"],
            "source": response["source"],
            "category": response.get("category"),
            "state": response.get("state"),
        })


class VoiceMessageView(View):
    """Обработка голосовых сообщений [в разработке]"""
    def post(self, request):
        # Аудиофайл передаётся как multipart/form-data
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return JsonResponse({"error": "No audio file"}, status=400)

        audio_bytes = audio_file.read()
        content_type = audio_file.content_type or "audio/ogg;codecs=opus"

        # История и состояние (как в ChatView)
        history = [...]  # из БД
        state = {...}    # из сессии

        response = process_voice_message(
            audio_bytes=audio_bytes,
            content_type=content_type,
            history=history,
            state=state,
        )

        # Сохраняем в БД
        Message.objects.create(
            session_id=request.POST.get("session_id"),
            query=response["transcribed_text"],
            answer=response["answer"],
            source="voice",
        )

        # Возвращаем текст + аудио
        return JsonResponse({
            "answer": response["answer"],
            "transcribed_text": response["transcribed_text"],
            "audio_response": base64.b64encode(response["audio_response"]).decode(),
            "audio_media_type": response["audio_media_type"],
        })


class RateView(View):
    def post(self, request):
        data = json.loads(request.body)

        # Бэкенд достаёт сообщение из своей БД
        msg = Message.objects.get(id=data["message_id"])

        result = rate_answer(
            query=msg.query,
            answer=msg.answer,
            rating=data["rating"],
        )

        return JsonResponse(result)
```

---

## Локальное тестирование

```bash
python main_AI.py
```

История хранится в памяти на время сессии — имитирует поведение бэкенда. После каждого ответа можно поставить оценку и увидеть мнение AI-критика.

```
ДТП-ассистент запущен. Введите 'выход' для завершения.

Ты: попал в ДТП, пострадавших нет

Бот [llm]: Сохраняйте спокойствие. Первым делом...

Оцени ответ (0-5 или Enter): 5
Критик: 4/5 — Ответ полный, но можно добавить...
```

---

## Архитектура

```
Запрос пользователя (текст / голос)
        │
        ▼
┌───────────────┐
│ Template      │ ──── совпадение regex ──▶ ответ из шаблона (0 токенов)
│ Matcher       │
└──────┬────────┘
       │ нет совпадения
       ▼
┌───────────────┐
│ Dialog Flow   │  детерминированная машина состояний диалога
│ (State Machine)│
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Meta          │  классификация намерения + извлечение фактов (Function Calling)
│ Classifier    │
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ RAG Retrieval │ ◀── chroma_db + chroma_feedback
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Generator     │  генерирует ответ (GigaChat) с учётом STATE-карточки
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Self-Check    │  оценивает и при необходимости переписывает
└──────┬────────┘
       │
       ▼
    ответ (текст / аудио)
```

**Детерминированная машина состояний** (`services/dialog_flow.py`) управляет пошаговым сбором фактов о ДТП: наличие пострадавших, количество участников, повреждения, ОСАГО, разногласия, фотофиксация. Переходы между шагами явные, без зависимости от LLM.

**Function Calling** (`services/gigachat_client.py`) надёжно извлекает факты из сообщения пользователя через нативный API GigaChat — больше никаких парсингов JSON через regex.

**STATE-карточка** (`utils/prompts.py`) передаёт в генератор текущий шаг диалога, известные факты, фокус шага и ограничения — что можно/нельзя упоминать.

**Шаблонные ответы** (`source: template`) — самый быстрый путь. Regex-матчер покрывает частые вопросы: приветствие, лимиты выплат, сроки, экстренные номера, приложения и др. Нулевой расход токенов.

**RAG** использует две базы: `chroma_db` с документами по ДТП и ОСАГО, `chroma_feedback` с хорошими Q&A из реальных диалогов. Вторая база пополняется автоматически при высоких оценках. Поддерживаются форматы `.md`, `.txt`, `.json`, `.pdf`.

---

## Известные ограничения

| # | Проблема |
|---|----------|
| 1 | **Голосовой модуль в разработке**: `process_voice_message()` требует API-ключей SaluteSpeech и дополнительного тестирования. Распознавание и синтез могут работать нестабильно без корректной настройки. |
| 2 | Высокий расход токенов: на каждый запрос до 4 вызовов LLM (meta_classifier + extract_facts + generator + self-check) |
| 3 | Self-check нестабилен — иногда ухудшает качество ответа |
| 4 | RAG может возвращать нерелевантный контекст при размытых запросах |
| 5 | GigaChat возвращает 429 при частых запросах — встроенный retry с экспоненциальной задержкой |
| 6 | Машина состояний требует последовательного прохождения шагов — пропуск шага возможен только при явном указании всех фактов в одном сообщении |

+++ README.md (修改后)
# ДТП-ассистент

AI-агент для консультаций по дорожно-транспортным происшествиям. Помогает пользователю пошагово оформить ДТП, определить возможность Европротокола, разрешить разногласия между участниками и ответить на вопросы по ОСАГО.

Поддерживает текстовый ввод. **Голосовой модуль (распознавание и синтез речи) находится в разработке** — функционал частично реализован, но требует API-ключей SaluteSpeech и дополнительного тестирования перед использованием в продакшене.

---

## Содержание

- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Интеграция с бэкендом](#интеграция-с-бэкендом)
- [Локальное тестирование](#локальное-тестирование)
- [Архитектура](#архитектура)
- [Известные ограничения](#известные-ограничения)

---

## Структура проекта

```
├── agent/
│   ├── core.py              # Публичный API: run_agent(), rate_answer(), process_voice_message()
│   ├── algorithm.py         # Загрузка и нарезка алгоритма по блокам
│   ├── generator.py         # Генерация ответа через GigaChat
│   ├── history.py           # Адаптивное формирование истории диалога
│   ├── meta_classifier.py   # LLM-классификатор намерений
│   └── retriever.py         # Категориально-зависимый RAG
│
├── services/
│   ├── dialog_flow.py       # Детерминированная машина состояний диалога
│   ├── gigachat_client.py   # Function Calling для извлечения фактов о ДТП
│   ├── salutespeech_client.py # Клиент SaluteSpeech API (TTS/STT) [в разработке]
│   └── scheme_flow.py       # Пошаговый мастер создания схемы ДТП
│
├── utils/
│   ├── audio_utils.py       # Нормализация аудио (PCM 16bit, 16kHz, моно)
│   ├── catalog.py           # Каталог поддерживаемых моделей GigaChat
│   ├── knowledge_loader.py  # Загрузка файлов (.md, .txt, .json, .pdf)
│   └── prompts.py           # Структурированные промпты с ограничителями
│
├── evaluation/
│   ├── critic.py            # AI-критик: оценка качества ответа
│   └── self_check.py        # Самопроверка и улучшение ответа
│
├── rag/
│   ├── retrieval.py         # Поиск контекста в векторных базах
│   ├── feedback_db.py       # Сохранение хороших Q&A для дообучения
│   └── init_db.py           # Инициализация ChromaDB
│
├── templates/
│   ├── matcher.py           # Regex-матчер шаблонных ответов
│   ├── responses.py         # Шаблоны частых вопросов (без LLM)
│   └── llm_classifier.py    # LLM-классификатор шаблонов
│
├── Docs_md/                 # Документы для RAG-базы
├── chroma_db/               # Основная векторная база (генерируется через build_db.py)
├── chroma_feedback/         # База дообучения на хороших Q&A (генерируется)
│
├── build_db.py              # Умная сборка RAG-индекса с манифестами
├── config.py                # Конфигурация через переменные окружения (.env)
├── main_AI.py               # CLI для локального тестирования
└── requirements.txt         # Зависимости проекта
```

---

## Требования

- Python 3.10+
- Токен GigaChat ([получить здесь](https://developers.sber.ru/gigachat))
- API-ключи SaluteSpeech (для голосового ввода-вывода, опционально — модуль в разработке)

Основные зависимости устанавливаются через `requirements.txt`:

```bash
gigachat
langchain-community
langchain-huggingface
chromadb
sentence-transformers
python-dotenv
pypdf>=4.0.0
requests>=2.31.0
```

---

## Установка

```bash
git clone <repo-url>
cd dtp-agent
pip install -r requirements.txt
```

---

## Конфигурация

Токен GigaChat и API-ключи SaluteSpeech передаются через переменные окружения. **Никогда не вписывай токены в код и не коммить `.env` в git.**

```bash
# Linux / Mac
export GIGACHAT_AUTH="ваш_токен"
export SALUTESPEECH_CLIENT_ID="ваш_client_id"
export SALUTESPEECH_CLIENT_SECRET="ваш_client_secret"

# Windows
set GIGACHAT_AUTH=ваш_токен
set SALUTESPEECH_CLIENT_ID=ваш_client_id
set SALUTESPEECH_CLIENT_SECRET=ваш_client_secret
```

Или через `.env` файл (убедись что он добавлен в `.gitignore`):

```env
GIGACHAT_AUTH=ваш_токен
SALUTESPEECH_CLIENT_ID=ваш_client_id
SALUTESPEECH_CLIENT_SECRET=ваш_client_secret
```

```bash
# .gitignore
.env
chroma_db/
chroma_feedback/
*.pyc
__pycache__/
```

---

## Интеграция с бэкендом

Агент предоставляет методы для текстового и голосового взаимодействия. **История диалога и состояние машины состояний хранятся на стороне бэкенда** и передаются в каждый запрос.

### Импорт

```python
from agent.core import run_agent, rate_answer, process_voice_message
```

---

### `run_agent` — получить ответ агента (текст)

```python
run_agent(
    query: str,
    history: list = None,
    db=None,
    feedback_db=None,
    state: dict = None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `query` | `str` | Сообщение пользователя |
| `history` | `list` | История диалога — список `{"query": ..., "answer": ...}`. Бэкенд хранит и передаёт сам. |
| `db` | ChromaDB | Основная RAG-база. Передать `None` если не используется. |
| `feedback_db` | ChromaDB | База дообучения. Передать `None` если не используется. |
| `state` | `dict` | **Состояние машины состояний диалога**. Хранит текущий шаг опроса и известные факты о ДТП. Бэкенд должен сохранять это значение и передавать в каждый следующий запрос одного диалога. |

**Что такое `state`:**

Параметр `state` — это объект состояния детерминированной машины состояний, которая управляет пошаговым сбором фактов о ДТП. Он содержит:
- `current_step` — текущий этап диалога (например, "спросить о пострадавших", "спросить об ОСАГО")
- `scenario` — текущий сценарий (европротокол, вызов ГИБДД, особое случаи)
- `facts` — известные факты о ДТП (пострадавшие, количество участников, наличие ОСАГО, разногласия и т.д.)
- `last_assistant_question` — последний вопрос бота

**Зачем это нужно:** машина состояний гарантирует, что бот последовательно соберёт все необходимые факты для принятия решения о возможности оформления Европротокола. Без передачи `state` между запросами бот будет "забывать" контекст диалога.

**Возвращает:**

```python
{
    "answer": str,           # ответ агента
    "source": str,           # откуда пришёл ответ: "template" | "llm" | "filter" | "error"
    "category": str | None,  # категория намерения (например, "dtp_registration")
    "state": dict,           # обновлённое состояние диалога (сохранить и передать в следующий запрос)
}
```

**Пример:**

```python
# Первое сообщение — история и состояние пустые
response = run_agent(query="попал в ДТП, что делать?")
# {"answer": "Сохраняйте спокойствие...", "source": "llm", "state": {...}}

# Бэкенд сохраняет пару в своей БД и состояние в сессии
history = [{"query": "попал в ДТП, что делать?", "answer": response["answer"]}]
state = response["state"]  # важно сохранить!

# Следующее сообщение — передаём историю и состояние
response = run_agent(
    query="пострадавших нет",
    history=history,
    state=state  # передаём сохранённое состояние
)
```

**Значения `source`:**

| Значение | Описание |
|----------|----------|
| `template` | Ответ из шаблона (regex, без вызова LLM) |
| `llm` | Ответ сгенерирован моделью |
| `filter` | Запрос не по теме ДТП |
| `error` | Произошла ошибка |

---

### `process_voice_message` — обработать голосовое сообщение [в разработке]

⚠️ **Модуль голосового ввода-вывода находится в стадии активной разработки.** Код частично реализован, но требует:
- Настройки API-ключей SaluteSpeech (`SALUTESPEECH_CLIENT_ID`, `SALUTESPEECH_CLIENT_SECRET`)
- Дополнительного тестирования в реальных условиях
- Проверки качества распознавания русской речи
- Тестирования синтеза ответа

Используйте на свой страх и риск. В продакшене рекомендуется пока использовать только текстовый режим.

```python
process_voice_message(
    audio_bytes: bytes,
    content_type: str = "audio/ogg;codecs=opus",
    history: list = None,
    db=None,
    feedback_db=None,
    state: dict = None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `audio_bytes` | `bytes` | Аудиосообщение пользователя (OGG/Opus, WAV) |
| `content_type` | `str` | MIME-тип аудио (по умолчанию `"audio/ogg;codecs=opus"`) |
| `history` | `list` | История диалога (как в `run_agent`) |
| `db` | ChromaDB | Основная RAG-база |
| `feedback_db` | ChromaDB | База дообучения |
| `state` | `dict` | Состояние машины состояний диалога |

**Возвращает:**

```python
{
    "answer": str,              # текстовый ответ агента
    "source": str,              # источник ответа
    "category": str | None,     # категория намерения
    "state": dict,              # обновлённое состояние
    "transcribed_text": str,    # распознанный текст
    "audio_response": bytes,    # аудиответ (синтезированный голос)
    "audio_media_type": str,    # MIME-тип аудиответа (например, "audio/opus")
}
```

**Пример:**

```python
# Бэкенд получает аудиосообщение от пользователя
with open("user_message.ogg", "rb") as f:
    audio_bytes = f.read()

response = process_voice_message(
    audio_bytes=audio_bytes,
    content_type="audio/ogg;codecs=opus",
)

# Отправить текстовый ответ в UI
print(response["transcribed_text"])  # "попал в ДТП, что делать?"
print(response["answer"])            # "Сохраняйте спокойствие..."

# Отправить аудиответ пользователю (если успешно синтезирован)
if response.get("audio_response"):
    send_audio_to_user(
        audio=response["audio_response"],
        media_type=response["audio_media_type"],
    )
```

---

### `rate_answer` — оценить ответ

Вызывается после того как пользователь поставил оценку. Бэкенд передаёт сюда `query` и `answer`, которые сам достаёт из своей БД.

```python
rate_answer(
    query: str,
    answer: str,
    rating: int,
    feedback_db=None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `query` | `str` | Вопрос пользователя (из БД бэкенда) |
| `answer` | `str` | Ответ агента (из БД бэкенда) |
| `rating` | `int` | Оценка пользователя от 0 до 5 |
| `feedback_db` | ChromaDB | База дообучения. При оценке ≥4 хороший ответ сохраняется для улучшения RAG. |

**Возвращает:**

```python
{
    "critic_score": int,    # оценка AI-критика от 1 до 5
    "critic_comment": str,  # комментарий критика
}
```

**Пример:**

```python
# Пользователь поставил оценку 5
# Бэкенд достаёт из своей БД нужный query и answer
result = rate_answer(
    query="попал в ДТП, что делать?",
    answer="Включите аварийку...",
    rating=5,
)
# {"critic_score": 4, "critic_comment": "Хороший ответ, но можно добавить..."}
```

---

### Пример Django view

```python
import json
from django.http import JsonResponse
from django.views import View
from agent.core import run_agent, rate_answer, process_voice_message


class ChatView(View):
    def post(self, request):
        data = json.loads(request.body)

        # История берётся из БД бэкенда
        history = list(
            Message.objects.filter(session_id=data["session_id"])
            .values("query", "answer")
            .order_by("created_at")
        )

        # Состояние диалога хранится в сессии или БД
        state = data.get("state")

        response = run_agent(
            query=data["query"],
            history=history,
            state=state,
        )

        # Бэкенд сохраняет пару сам
        Message.objects.create(
            session_id=data["session_id"],
            query=data["query"],
            answer=response["answer"],
            source=response["source"],
            category=response.get("category"),
        )

        return JsonResponse({
            "answer": response["answer"],
            "source": response["source"],
            "category": response.get("category"),
            "state": response.get("state"),  # важно вернуть состояние клиенту
        })


class VoiceMessageView(View):
    """Обработка голосовых сообщений [в разработке — требует тестирования]"""
    def post(self, request):
        # Аудиофайл передаётся как multipart/form-data
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return JsonResponse({"error": "No audio file"}, status=400)

        audio_bytes = audio_file.read()
        content_type = audio_file.content_type or "audio/ogg;codecs=opus"

        # История и состояние (как в ChatView)
        history = [...]  # из БД
        state = {...}    # из сессии

        response = process_voice_message(
            audio_bytes=audio_bytes,
            content_type=content_type,
            history=history,
            state=state,
        )

        # Сохраняем в БД
        Message.objects.create(
            session_id=request.POST.get("session_id"),
            query=response["transcribed_text"],
            answer=response["answer"],
            source="voice",
        )

        # Возвращаем текст + аудио (если синтез успешен)
        result = {
            "answer": response["answer"],
            "transcribed_text": response["transcribed_text"],
        }
        if response.get("audio_response"):
            import base64
            result["audio_response"] = base64.b64encode(response["audio_response"]).decode()
            result["audio_media_type"] = response["audio_media_type"]

        return JsonResponse(result)


class RateView(View):
    def post(self, request):
        data = json.loads(request.body)

        # Бэкенд достаёт сообщение из своей БД
        msg = Message.objects.get(id=data["message_id"])

        result = rate_answer(
            query=msg.query,
            answer=msg.answer,
            rating=data["rating"],
        )

        return JsonResponse(result)
```

---

## Локальное тестирование

```bash
python main_AI.py
```

История хранится в памяти на время сессии — имитирует поведение бэкенда. После каждого ответа можно поставить оценку и увидеть мнение AI-критика.

```
ДТП-ассистент запущен. Введите 'выход' для завершения.

Ты: попал в ДТП, пострадавших нет

Бот [llm]: Сохраняйте спокойствие. Первым делом...

Оцени ответ (0-5 или Enter): 5
Критик: 4/5 — Ответ полный, но можно добавить...
```

---

## Архитектура

```
Запрос пользователя (текст / голос)
        │
        ▼
┌───────────────┐
│ Template      │ ──── совпадение regex ──▶ ответ из шаблона (0 токенов)
│ Matcher       │
└──────┬────────┘
       │ нет совпадения
       ▼
┌───────────────┐
│ Dialog Flow   │  детерминированная машина состояний диалога
│ (State Machine)│
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Meta          │  классификация намерения + извлечение фактов (Function Calling)
│ Classifier    │
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ RAG Retrieval │ ◀── chroma_db + chroma_feedback
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Generator     │  генерирует ответ (GigaChat) с учётом STATE-карточки
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Self-Check    │  оценивает и при необходимости переписывает
└──────┬────────┘
       │
       ▼
    ответ (текст / аудио)
```

**Детерминированная машина состояний** (`services/dialog_flow.py`) управляет пошаговым сбором фактов о ДТП: наличие пострадавших, количество участников, повреждения, ОСАГО, разногласия, фотофиксация. Переходы между шагами явные, без зависимости от LLM.

**Function Calling** (`services/gigachat_client.py`) надёжно извлекает факты из сообщения пользователя через нативный API GigaChat — больше никаких парсингов JSON через regex.

**STATE-карточка** (`utils/prompts.py`) передаёт в генератор текущий шаг диалога, известные факты, фокус шага и ограничения — что можно/нельзя упоминать.

**Шаблонные ответы** (`source: template`) — самый быстрый путь. Regex-матчер покрывает частые вопросы: приветствие, лимиты выплат, сроки, экстренные номера, приложения и др. Нулевой расход токенов.

**RAG** использует две базы: `chroma_db` с документами по ДТП и ОСАГО, `chroma_feedback` с хорошими Q&A из реальных диалогов. Вторая база пополняется автоматически при высоких оценках. Поддерживаются форматы `.md`, `.txt`, `.json`, `.pdf`.

---

## Известные ограничения

| # | Проблема |
|---|----------|
| 1 | **Голосовой модуль в разработке**: `process_voice_message()` требует API-ключей SaluteSpeech и дополнительного тестирования. Распознавание и синтез могут работать нестабильно без корректной настройки. Не рекомендуется для продакшена. |
| 2 | Высокий расход токенов: на каждый запрос до 4 вызовов LLM (meta_classifier + extract_facts + generator + self-check) |
| 3 | Self-check нестабилен — иногда ухудшает качество ответа |
| 4 | RAG может возвращать нерелевантный контекст при размытых запросах |
| 5 | GigaChat возвращает 429 при частых запросах — встроенный retry с экспоненциальной задержкой |
| 6 | Машина состояний требует последовательного прохождения шагов — пропуск шага возможен только при явном указании всех фактов в одном сообщении |
| 7 | **Требуется передача `state` между запросами**: бэкенд должен хранить и передавать состояние диалога в каждый вызов `run_agent()` для корректной работы машины состояний |