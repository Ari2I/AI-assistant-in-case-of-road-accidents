AI-агент для пошагового оформления ДТП. Помогает пользователю собрать факты, определить возможность Европротокола, заполнить протокол и ответить на вопросы по ОСАГО.
---
## Содержание
- [Структура проекта](#структура-проекта)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Интеграция с бэкендом](#интеграция-с-бэкендом)
- [Локальное тестирование](#локальное-тестирование)
- [Архитектура](#архитектура)
---
## Структура проекта
```
├── agent/
│   ├── core.py                # Публичный API: run_agent(), rate_answer()
│   ├── step_types.py          # Типы: Step, StepResponse
│   ├── step1_stateless.py     # Шаг 1: сбор фактов
│   ├── step2_europrotocol.py  # Шаг 2: заполнение Европротокола
│   ├── step3_insurance.py     # Шаг 3: помощь со страховой
│   ├── meta_classifier.py     # Классификация запроса (фильтр + планировщик)
│   ├── generator.py           # Генерация ответа через LLM
│   ├── retriever.py           # Поиск контекста в RAG-базах
│   └── history.py             # Форматирование истории диалога
│
├── evaluation/
│   ├── critic.py              # AI-критик: оценка качества ответа
│   └── self_check.py          # Самопроверка и улучшение ответа
│
├── rag/
│   ├── init_db.py             # Инициализация основной RAG-базы
│   ├── init_disagreement_db.py # База для режима разногласий
│   └── feedback_db.py         # Сохранение хороших Q&A для дообучения
│
├── templates/
│   ├── matcher.py             # Regex-матчер шаблонных ответов
│   └── responses.py           # Шаблоны частых вопросов (без LLM)
│
├── Docs_md/                   # Документы для RAG-базы
├── chroma_db/                 # Основная векторная база (генерируется)
├── chroma_feedback/           # База дообучения на хороших Q&A (генерируется)
├── config.py                  # Конфигурация (токен GigaChat)
├── main_AI.py                 # CLI для локального тестирования
└── requirements.txt           # Зависимости
```
---
## Требования
- Python 3.10+
- Токен GigaChat ([получить здесь](https://developers.sber.ru/gigachat))
### Зависимости
Все зависимости указаны в `requirements.txt`:
```
gigachat>=0.1.35
langchain-gigachat>=0.3.0
langchain-community>=0.2.0
langchain-chroma>=0.1.0
chromadb>=0.5.0
python-dotenv>=1.0.0
pytest>=8.0.0  # опционально, для тестов
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
Токен GigaChat передаётся через переменную окружения `GIGA_AUTH`. **Никогда не вписывай токен в код и не коммить `.env` в git.**
```bash
# Linux / Mac
export GIGA_AUTH="ваш_токен"
# Windows
set GIGA_AUTH=ваш_токен
```
Или через `.env` файл (убедись что он добавлен в `.gitignore`):
```env
GIGA_AUTH=ваш_токен
```
```bash
# .gitignore
.env
chroma_db/
chroma_feedback/
```
---
## Интеграция с бэкендом
### Основной API
Агент предоставляет два метода. **Бэкенд хранит состояние диалога** и передаёт его в каждый запрос.
#### Импорт
```python
from agent.core import run_agent, rate_answer
from agent.step_types import Step
```
---
### `run_agent` — получить ответ агента
```python
run_agent(
    query: str,
    current_step: str | None = None,
    history: list | None = None,
    slots: dict | None = None,
    collected_fields: dict | None = None,
    db=None,
    feedback_db=None,
    disagreement_db=None,
) -> dict
```
**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `query` | `str` | ✅ | Сообщение пользователя |
| `current_step` | `str` | ❌ | Текущий шаг сценария: `"step1"`, `"step2"`, `"step3"`, `"offer_europrotocol"`, `"consultant_only"`. Если `None` — агент работает в режиме общего консультанта. |
| `history` | `list` | ❌ | История диалога — список `{"query": ..., "answer": ...}`. Бэкенд хранит и передаёт сам. |
| `slots` | `dict` | ❌ | Слоты для step1 (собранные факты). Передаётся только в step1. См. раздел [Слоты step1](#слоты-step1). |
| `collected_fields` | `dict` | ❌ | Поля для step2 (заполненные данные протокола). Передаётся только в step2. См. раздел [Поля step2](#поля-step2). |
| `db` | ChromaDB | ❌ | Основная RAG-база. Передать `None` если не используется. |
| `feedback_db` | ChromaDB | ❌ | База дообучения. Передать `None` если не используется. |
| `disagreement_db` | ChromaDB | ❌ | База для режима разногласий. Передать `None` если не используется. |
**Возвращает:**
```python
{
    "answer": str,              # текст ответа пользователю
    "source": str,              # откуда пришёл ответ: "template" | "llm" | "step1" | "step2" | "step3" | "filter" | "error"
    "category": str | None,     # категория запроса (для general-режима)
    "step_completed": bool,     # завершён ли текущий шаг
    "next_step": str | None,    # следующий шаг: "step1", "step2", "step3", "offer_europrotocol", "consultant_only", "done", "call_gibdd"
    "slots": dict | None,       # обновлённые слоты step1 (передавать обратно при следующем запросе в step1)
    "collected_fields": dict | None,  # обновлённые поля step2 (передавать обратно при следующем запросе в step2)
    "final_json": dict | None,  # готовый JSON Европротокола (появляется когда step_completed=True и next_step="done")
}
```
**Пример первого запроса (step1):**
```python
# Первый запрос — история и слоты пустые
response = run_agent(
    query="попал в ДТП, что делать?",
    current_step="step1",
    history=[],
    slots={},
    collected_fields={},
)
# Бэкенд сохраняет пару в своей БД
history = [{"query": "попал в ДТП, что делать?", "answer": response["answer"]}]
# Бэкенд сохраняет слоты для следующего запроса
slots = response.get("slots", {})
# Ответ пользователю
print(response["answer"])
```
**Пример второго запроса (step1, продолжение):**
```python
# Второй запрос — передаём историю и слоты
response = run_agent(
    query="пострадавших нет",
    current_step="step1",
    history=history,
    slots=slots,
    collected_fields={},
)
# Обновляем историю и слоты
history.append({"query": "пострадавших нет", "answer": response["answer"]})
slots = response.get("slots", slots)
```
**Переход на следующий шаг:**
```python
if response.get("step_completed") and response.get("next_step"):
    current_step = response["next_step"]
    
    # При переходе step1 -> step2 слоты преобразуются в collected_fields
    if current_step == "step2":
        collected_fields = _map_slots_to_fields(slots)
```
**Значения `source`:**

| Значение | Описание |
|----------|----------|
| `template` | Ответ из шаблона (regex, без вызова LLM) |
| `llm` | Ответ сгенерирован моделью (general-режим) |
| `step1` | Ответ от step1 (вопрос или инструкция) |
| `step2` | Ответ от step2 (вопрос или подтверждение) |
| `step3` | Ответ от step3 (помощь со страховой) |
| `filter` | Запрос не по теме ДТП |
| `error` | Произошла ошибка |
**Значения `next_step`:**

| Значение | Описание |
|----------|----------|
| `step1` | Продолжать сбор фактов |
| `step2` | Переход к заполнению Европротокола |
| `step3` | Переход к помощи со страховой |
| `offer_europrotocol` | Предложить пользователю заполнить Европротокол |
| `consultant_only` | Режим консультанта (пользователь отказался от Европротокола) |
| `done` | Протокол готов, `final_json` содержит результат |
| `call_gibdd` | Нужно вызвать ГИБДД (есть пострадавшие, >2 участников, нет ОСАГО) |
---
### Слоты step1
Бэкенд должен сохранять и передавать эти слоты при каждом запросе в step1:
```python
slots = {
    "safety_confirmed": None,      # bool: безопасность места ДТП
    "emergency_sign": None,        # bool: аварийка и знак выставлены
    "victims": None,               # bool: есть пострадавшие
    "participants_count": None,    # int: количество ТС
    "osago_both": None,            # bool: ОСАГО у всех участников
    "disagreement": None,          # bool: есть разногласия
    "disagreement_help_offered": False,  # bool: флаг, предложена ли помощь при разногласиях
    "disagreement_help_active": False,   # bool: флаг, активен ли режим помощи при разногласиях
}
```
Агент сам обновляет слоты и возвращает их в `response["slots"]`. Бэкенд должен сохранить это значение и передать при следующем запросе.
---
### Поля step2
Бэкенд должен сохранять и передавать эти поля при каждом запросе в step2:
```python
collected_fields = {
    "date": None,           # str: дата ДТП
    "location": None,       # str: место ДТП
    "witnesses": None,      # str: свидетели
    "first_driver_name": None,    # str: первый водитель
    "second_driver_name": None,   # str: второй водитель
    "first_car_model": None,      # str: марка авто первого
    "second_car_model": None,     # str: марка авто второго
    # ... другие поля протокола
}
```
Агент сам обновляет поля и возвращает их в `response["collected_fields"]`.
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
---
### Пример Django view
```python
import json
from django.http import JsonResponse
from django.views import View
from agent.core import run_agent, rate_answer
from agent.step_types import Step
class ChatView(View):
    def post(self, request):
        data = json.loads(request.body)
        # Бэкенд хранит состояние сессии
        session = Session.objects.get(id=data["session_id"])
        
        response = run_agent(
            query=data["query"],
            current_step=session.current_step,
            history=list(session.messages.values("query", "answer")),
            slots=session.slots,
            collected_fields=session.collected_fields,
        )
        # Бэкенд сохраняет сообщение
        session.messages.create(
            query=data["query"],
            answer=response["answer"],
        )
        # Бэкенд обновляет состояние
        if response.get("slots"):
            session.slots = response["slots"]
        if response.get("collected_fields"):
            session.collected_fields = response["collected_fields"]
        if response.get("step_completed") and response.get("next_step"):
            session.current_step = response["next_step"]
        session.save()
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
export GIGA_AUTH="ваш_токен"
python main_AI.py
```
CLI симулирует поведение бэкенда: хранит историю, слоты и поля локально, передаёт их в `run_agent()` при каждом запросе.
```
=== ДТП-ассистент — локальное тестирование ===
  1. Шаговый режим (step1 → step2)
  2. General-режим (вопросы по ДТП/ОСАГО)
  0. Выход
Выбор: 1
=== Шаговый режим: Оформление Европротокола ===
────────────────────────────────────────
  Шаг: step1
  Слоты (0/6): (пусто)
────────────────────────────────────────
Вы: попал в ДТП
Ассистент: Место ДТП безопасно? Нет угрозы пожара или взрыва?
Оценить ответ (0-5 или Enter): 
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
│ Meta          │ ──── один вызов LLM: фильтр + классификатор + планировщик
│ Classifier    │
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Step1 /       │ ──── пошаговый сбор фактов или заполнение протокола
│ Step2 /       │
│ Step3         │
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ RAG Retrieval │ ◀── chroma_db + chroma_feedback
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Generator     │  генерирует ответ (GigaChat)
└──────┬────────┘
       │
       ▼
┌───────────────┐
│ Self-Check    │  запускается только при маркерах неуверенности
└──────┬────────┘
       │
       ▼
    ответ
```
**Оптимизации v4.0:**
- `filter + classifier + planner` → один вызов LLM (~1500 токенов вместо ~4000)
- Генератор получает только нужный блок алгоритма (~400 токенов вместо ~3000)
- `self_check` запускается только при маркерах неуверенности (~2500 токенов экономии)
**Итого:** 2-3 вызова LLM, ~4000-5000 токенов на запрос (было до 5 вызовов, ~10000 токенов).
---
## Известные ограничения
| # | Проблема |
|---|----------|
| 1 | Высокий расход токенов: на каждый запрос 2-3 вызова LLM |
| 2 | Self-check нестабилен — иногда ухудшает качество ответа |
| 3 | RAG может возвращать нерелевантный контекст при размытых запросах |
| 4 | GigaChat возвращает 429 при частых запросах — нужен retry или кэш клиента |


---

## Сканер документов

Агент умеет извлекать данные из фотографий документов через GigaChat Vision
и возвращать их в формате полей профиля пользователя.

**Схема работы:**
```
Фото на диске → scan_to_profile() → поля профиля
                                           ↓
                                   Бэкенд сохраняет в БД профиля
                                           ↓
                                   При старте сессии ДТП → collected_fields
```

### Поддерживаемые документы и поля профиля

| Документ | `document_type` | Поля профиля |
|---|---|---|
| Полис ОСАГО | `osago` | `insurer`, `policy_number`, `policy_expiry` |
| Водительское удостоверение | `driver_license` | `driver_name`, `license_number` |
| СТС / ПТС | `sts` | `car_brand`, `car_number`, `owner_name` |

### Импорт

```python
from profile.scanner import scan_to_profile
```

---

### `scan_to_profile` — единственный публичный метод

```python
scan_to_profile(image_path: str) -> dict
```

**Параметры:**

| Параметр | Тип | Описание |
|---|---|---|
| `image_path` | `str` | Абсолютный путь к файлу фото на диске. Поддерживаемые форматы: JPEG, PNG, WEBP |

**Возвращает:**

```python
{
    "document_type": "osago" | "driver_license" | "sts" | None,

    # Поля присутствуют только если успешно извлечены из документа:

    # Из полиса ОСАГО:
    "insurer":       "Росгосстрах",
    "policy_number": "ХХХ 1234567890",
    "policy_expiry": "31.12.2025",

    # Из водительского удостоверения:
    "driver_name":    "Иванов Иван Иванович",
    "license_number": "77 77 123456",

    # Из СТС / ПТС:
    "car_brand":  "Toyota Camry",
    "car_number": "А123БВ777",
    "owner_name": "Иванов Иван Иванович",
}
```

При ошибке или нераспознанном документе → `{"document_type": None}`

**Raises:**
- `FileNotFoundError` — файл по указанному пути не найден
- `ValueError` — формат файла не поддерживается

---

### Пример использования (Django)

```python
import os
from profile.scanner import scan_to_profile

def handle_document_upload(request, user_id):
    photo = request.FILES["photo"]

    # Сохраняем фото во временный файл
    tmp_path = f"/tmp/uploads/user_{user_id}_{photo.name}"
    with open(tmp_path, "wb") as f:
        f.write(photo.read())

    try:
        # Агент конвертирует, сканирует и удаляет файл из GigaChat сам
        result = scan_to_profile(tmp_path)

        if result.get("document_type") is None:
            return JsonResponse({"error": "Документ не распознан"}, status=400)

        # Мёржим в профиль пользователя
        profile = UserProfile.objects.get(user_id=user_id)
        profile.update_from_scan(result)
        profile.save()

        return JsonResponse(result)

    finally:
        # Бэкенд ОБЯЗАН удалить временный файл сразу после сканирования
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
```

---

### Конфиденциальность и удаление данных

| # | Что происходит с фото |
|---|---|
| 1 | Фото передаётся в GigaChat **только для распознавания текста** — никакого постоянного хранения на стороне агента |
| 2 | После завершения сканирования файл **гарантированно удаляется** из хранилища GigaChat через `finally`-блок — даже если в процессе произошла ошибка |
| 3 | Временный файл на диске бэкенд **обязан удалить самостоятельно** сразу после получения результата `scan_to_profile()` (см. пример выше) |
| 4 | В базу данных сохраняются **только извлечённые текстовые поля** — само фото нигде не хранится |

### Ограничения

| # | Ограничение |
|---|---|
| 1 | Требуется доступ к GigaChat B2B (`scope="GIGACHAT_API_B2B"`) — загрузка файлов недоступна на PERS-тарифе |
| 2 | Поддерживаемые форматы: JPEG, PNG, WEBP |
| 3 | Модуль извлекает поля только для **автомобиля пользователя** (vehicle A). Данные второго участника заполняются вручную в step2 |
| 4 | Качество распознавания зависит от качества фото: хорошее освещение, без бликов, документ целиком в кадре |