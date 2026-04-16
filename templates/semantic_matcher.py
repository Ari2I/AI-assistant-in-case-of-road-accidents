"""
Семантический матчер шаблонных ответов.

Использует GigaChat Embeddings API вместо локальной модели —
та же модель, что и для RAG, никаких лишних зависимостей.

Якорные эмбеддинги вычисляются один раз при инициализации
(вызови _matcher._lazy_init() при старте сервера через app_state.py).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from gigachat import GigaChat

from config import GIGA_AUTH
from templates.responses import TEMPLATES

# ---------------------------------------------------------------------------
# Якорные фразы для каждого шаблона
# ---------------------------------------------------------------------------
ANCHORS: dict[str, list[str]] = {
    "greeting": [
        "привет",
        "здравствуйте",
        "добрый день",
        "добрый вечер",
        "добрый утро",
        "хай",
        "приветствую",
    ],
    "what_is_europrotocol": [
        "что такое европротокол",
        "как работает европротокол",
        "объясни европейский протокол",
        "оформить дтп без вызова полиции",
        "оформить аварию без гибдд",
        "упрощённое оформление дтп",
        "самостоятельно оформить дтп",
        "можно ли не вызывать гибдд",
        "европейское соглашение после аварии",
    ],
    "payment_limits": [
        "сколько выплатят по страховке",
        "максимальная выплата по осаго",
        "лимит страхового возмещения",
        "на какую сумму рассчитывать после дтп",
        "сколько денег получу за дтп",
        "сколько заплатит страховая",
        "максимальная сумма по европротоколу",
        "400 тысяч рублей осаго",
        "100 тысяч европротокол",
    ],
    "deadlines": [
        "когда подать документы в страховую",
        "в какой срок уведомить страховщика",
        "сколько дней на оформление дтп",
        "дедлайн для подачи извещения",
        "через сколько дней можно отремонтировать машину",
        "когда нужно сообщить страховой о дтп",
        "5 рабочих дней после дтп",
        "15 дней без ремонта",
    ],
    "emergency_numbers": [
        "куда звонить при аварии",
        "телефон полиции при дтп",
        "номер скорой помощи",
        "как вызвать гибдд",
        "телефон мчс при пожаре",
        "экстренные номера телефонов",
        "112 или 102 при аварии",
    ],
    "apps": [
        "какое приложение использовать для дтп",
        "как скачать помощник осаго",
        "мобильное приложение для оформления аварии",
        "госуслуги авто как пользоваться",
        "дтп европротокол приложение",
        "программа для фиксации дтп",
        "приложение для европротокола на телефон",
    ],
    "repair_ban": [
        "можно ли чинить машину после дтп",
        "когда разрешат ремонтировать автомобиль",
        "запрет на ремонт после аварии",
        "нельзя ехать в сервис после дтп",
        "страховая не разрешила ремонт",
        "согласие страховщика на ремонт",
    ],
    "check_osago": [
        "как проверить полис осаго",
        "проверка страховки онлайн",
        "узнать действителен ли полис осаго",
        "нсис проверить страховку",
        "рса проверить полис автомобиля",
        "подлинный ли полис осаго",
    ],
    "no_osago": [
        "у виновника нет страховки",
        "второй участник без осаго",
        "полис истёк у другого водителя",
        "нет страховки у второй стороны",
        "виновник не застрахован",
        "у него просроченный полис",
    ],
    "victims_injured": [
        "есть пострадавшие в аварии",
        "человек получил травму при дтп",
        "раненые в аварии что делать",
        "сбил пешехода",
        "пассажир ранен",
        "кровь после аварии",
        "потеря сознания после дтп",
    ],
}

# Минимальная косинусная схожесть для срабатывания шаблона (0.0–1.0).
# GigaChat-эмбеддинги точнее локальной модели, поэтому порог чуть выше.
SIMILARITY_THRESHOLD: float = 0.60

# GigaChat принимает не более 10 текстов за один вызов
_EMBEDDINGS_BATCH_SIZE = 10


def _make_giga() -> GigaChat:
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


class _SemanticMatcher:
    """
    Синглтон. Якорные эмбеддинги вычисляются один раз при инициализации.
    Все последующие запросы — только один API-вызов (эмбеддинг запроса).
    """

    def __init__(self) -> None:
        self._anchor_embeddings: Optional[np.ndarray] = None  # shape: (N, dim)
        self._anchor_keys: list[str] = []
        self._ready = False

    def _lazy_init(self) -> None:
        if self._ready:
            return

        anchors_flat: list[str] = []
        for key, phrases in ANCHORS.items():
            for phrase in phrases:
                anchors_flat.append(phrase)
                self._anchor_keys.append(key)

        print(f"[semantic_matcher] Вычисляем эмбеддинги для {len(anchors_flat)} якорей...")

        all_vectors: list[list[float]] = []

        with _make_giga() as giga:
            for i in range(0, len(anchors_flat), _EMBEDDINGS_BATCH_SIZE):
                batch = anchors_flat[i : i + _EMBEDDINGS_BATCH_SIZE]
                response = giga.embeddings(batch)
                for item in response.data:
                    all_vectors.append(item.embedding)

        self._anchor_embeddings = np.array(all_vectors, dtype=np.float32)
        self._ready = True
        print("[semantic_matcher] Готово.")

    def match(self, query: str, threshold: float = SIMILARITY_THRESHOLD) -> Optional[str]:
        """
        Возвращает готовый текст шаблонного ответа или None.

        Args:
            query:     текст запроса (желательно нижний регистр)
            threshold: минимальный порог схожести
        """
        self._lazy_init()

        with _make_giga() as giga:
            response = giga.embeddings([query])
            query_vec = np.array(response.data[0].embedding, dtype=np.float32)

        # Косинусное сходство через матричное умножение — быстро
        dot = self._anchor_embeddings @ query_vec
        norms = np.linalg.norm(self._anchor_embeddings, axis=1) * np.linalg.norm(query_vec)
        cosine_scores = dot / (norms + 1e-9)

        best_idx = int(np.argmax(cosine_scores))
        best_score = float(cosine_scores[best_idx])

        if best_score >= threshold:
            key = self._anchor_keys[best_idx]
            return TEMPLATES[key]["response"]

        return None


# Один экземпляр на весь процесс
_matcher = _SemanticMatcher()


def semantic_match(query: str, threshold: float = SIMILARITY_THRESHOLD) -> Optional[str]:
    """
    Публичная функция — семантический поиск шаблона.
    Вызывается из match_template() как второй уровень после regex.
    """
    return _matcher.match(query.lower().strip(), threshold)