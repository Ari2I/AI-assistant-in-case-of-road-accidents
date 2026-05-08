# ДТП-ассистент

AI-агент для консультаций по дорожно-транспортным происшествиям. Помогает пользователю пошагово оформить ДТП, определить возможность Европротокола и ответить на вопросы по ОСАГО.

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
├── core.py                  # Публичный API: run_agent(), rate_answer()
├── config.py                # Конфигурация (токен GigaChat)
├── main_AI.py               # CLI для локального тестирования
│
├── agent/
│   ├── filter.py            # Фильтр нерелевантных запросов
│   ├── generator.py         # Генерация ответа через LLM
│   └── planner.py           # Определение намерения пользователя
│
├── evaluation/
│   ├── critic.py            # AI-критик: оценка качества ответа
│   └── self_check.py        # Самопроверка и улучшение ответа
│
├── rag/
│   ├── retrieval.py         # Поиск контекста в векторных базах
│   └── feedback_db.py       # Сохранение хороших Q&A для дообучения
│
├── templates/
│   ├── matcher.py           # Regex-матчер шаблонных ответов
│   └── responses.py         # Шаблоны частых вопросов (без LLM)
│
├── Docs_md/                 # Документы для RAG-базы
├── chroma_db/               # Основная векторная база (генерируется)
└── chroma_feedback/         # База дообучения на хороших Q&A (генерируется)
```

---

## Требования

- Python 3.10+
- Токен GigaChat ([получить здесь](https://developers.sber.ru/gigachat))

```
gigachat
langchain-community
langchain-huggingface
chromadb
sentence-transformers
python-dotenv
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

Токен GigaChat передаётся через переменную окружения. **Никогда не вписывай токен в код и не коммить `.env` в git.**

```bash
# Linux / Mac
export GIGACHAT_AUTH="ваш_токен"

# Windows
set GIGACHAT_AUTH=ваш_токен
```

Или через `.env` файл (убедись что он добавлен в `.gitignore`):

```env
GIGACHAT_AUTH=ваш_токен
```

```bash
# .gitignore
.env
chroma_db/
chroma_feedback/
```

---

## Интеграция с бэкендом

Агент предоставляет два метода. **История диалога хранится на стороне бэкенда** и передаётся в каждый запрос.

### Импорт

```python
from core import run_agent, rate_answer
```

---

### `run_agent` — получить ответ агента

```python
run_agent(
    query: str,
    history: list = None,
    db=None,
    feedback_db=None,
) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `query` | `str` | Сообщение пользователя |
| `history` | `list` | История диалога — список `{"query": ..., "answer": ...}`. Бэкенд хранит и передаёт сам. |
| `db` | ChromaDB | Основная RAG-база. Передать `None` если не используется. |
| `feedback_db` | ChromaDB | База дообучения. Передать `None` если не используется. |

**Возвращает:**

```python
{
    "answer": str,   # ответ агента
    "source": str,   # откуда пришёл ответ: "template" | "llm" | "filter" | "error"
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
from core import run_agent, rate_answer


class ChatView(View):
    def post(self, request):
        data = json.loads(request.body)

        # История берётся из БД бэкенда
        history = list(
            Message.objects.filter(session_id=data["session_id"])
            .values("query", "answer")
            .order_by("created_at")
        )

        response = run_agent(
            query=data["query"],
            history=history,
        )

        # Бэкенд сохраняет пару сам
        Message.objects.create(
            session_id=data["session_id"],
            query=data["query"],
            answer=response["answer"],
            source=response["source"],
        )

        return JsonResponse(response)


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
Запрос пользователя
        │
        ▼
┌───────────────┐
│ Template      │ ──── совпадение regex ──▶ ответ из шаблона (0 токенов)
│ Matcher       │
└──────┬────────┘
       │ нет совпадения
       ▼
┌───────────────┐
│ Topic Filter  │ ──── не по теме ──▶ "Я консультирую только по ДТП"
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ RAG Retrieval │ ◀── chroma_db + chroma_feedback
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Planner       │  определяет намерение и тип ответа
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Generator     │  генерирует ответ (GigaChat)
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Self-Check    │  оценивает и при необходимости переписывает
└──────┬────────┘
       │
       ▼
    ответ
```

**Шаблонные ответы** (`source: template`) — самый быстрый путь. Regex-матчер покрывает частые вопросы: приветствие, лимиты выплат, сроки, экстренные номера, приложения и др. Нулевой расход токенов.

**RAG** использует две базы: `chroma_db` с документами по ДТП и ОСАГО, `chroma_feedback` с хорошими Q&A из реальных диалогов. Вторая база пополняется автоматически при высоких оценках.

---

## Известные ограничения

| # | Проблема |
|---|----------|
| 1 | Высокий расход токенов: на каждый запрос до 4 вызовов LLM (filter + planner + generator + self-check) |
| 2 | Self-check нестабилен — иногда ухудшает качество ответа |
| 3 | RAG может возвращать нерелевантный контекст при размытых запросах |
| 4 | GigaChat возвращает 429 при частых запросах — нужен retry или кэш клиента |
