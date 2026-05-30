"""
CLI для локального тестирования ДТП-ассистента.

Режимы:
  1. Полный pipeline (step1 → step2 → step3)
  2. Отдельные модули:
     - Step 1: сбор фактов
     - Step 2: заполнение Европротокола
     - Step 3: взаимодействие со страховой
     - Disagreement helper: анализ разногласий
     - Meta classifier: классификация запроса
     - Template matcher: шаблонные ответы
     - Consultant: режим консультанта
     - Document scanner: сканирование документов по фото
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable

from gigachat import GigaChat

from config import GIGA_AUTH
from agent.core import run_agent, rate_answer
from agent.step_types import Step
from agent.step1_stateless import process_step1_with_llm
from agent.step2_europrotocol import process_step2_with_llm
from agent.step3_insurance import process_step3
from agent.disagreement_helper import run_disagreement_help
from agent.meta_classifier import meta_classify
from templates.matcher import match_template
from rag.db_manager import get_main_db, get_feedback_db, get_disagreement_db
from profile.scanner import scan_to_profile
from profile.utils import find_images, ensure_test_docs_dir

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
GRAY   = "\033[90m"
BLUE   = "\033[94m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def hr(char: str = "─", width: int = 60) -> str:
    return char * width


def prompt(label: str = "Вы") -> str:
    try:
        return input(f"\n{c(label + ':', CYAN)} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "выход"


def assistant_says(text: str) -> None:
    print(f"\n{c('Ассистент:', GREEN)} {text}")


def system_msg(text: str) -> None:
    print(f"\n{c('[система]', GRAY)} {text}")


def error_msg(text: str) -> None:
    print(f"\n{c('[ошибка]', RED)} {text}")


def section(title: str) -> None:
    print(f"\n{c(hr('═'), BLUE)}")
    print(c(f"  {title}", BOLD))
    print(c(hr('═'), BLUE))


def show_json(data: dict, label: str = "JSON") -> None:
    print(f"\n{c(f'[{label}]', YELLOW)}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def make_giga() -> GigaChat:
    return GigaChat(
        credentials=GIGA_AUTH,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_B2B",
    )


EXIT_COMMANDS = {"выход", "exit", "quit", "q", ":q"}
SHOW_STATE_COMMANDS = {"состояние", "state", "s", ":s"}


def is_exit(text: str) -> bool:
    return text.lower() in EXIT_COMMANDS


def is_show_state(text: str) -> bool:
    return text.lower() in SHOW_STATE_COMMANDS


def maybe_rate(query: str, answer: str, feedback_db) -> None:
    rating_str = input(
        f"\n{c('Оценить ответ (0-5 или Enter чтобы пропустить):', GRAY)} "
    ).strip()
    if rating_str.isdigit():
        rating = int(rating_str)
        if 0 <= rating <= 5:
            r = rate_answer(query=query, answer=answer, rating=rating, feedback_db=feedback_db)
            system_msg(f"Критик: {r['critic_score']}/5 — {r['critic_comment']}")


# ===========================================================================
# РЕЖИМ 1: Полный pipeline
# ===========================================================================

def _print_pipeline_state(current_step: str, slots: dict, collected_fields: dict) -> None:
    print(f"\n{c(hr('─', 50), GRAY)}")
    print(c(f"  Шаг: {current_step}", BOLD))
    if current_step == Step.STEP1:
        filled = {k: v for k, v in slots.items()
                  if v is not None and not k.startswith("_") and k not in ("disagreement_slots",)}
        print(c(f"  Слоты ({len(filled)}/6): {filled or '(пусто)'}", GRAY))
    elif current_step == Step.STEP2:
        filled = {k: v for k, v in collected_fields.items() if v and not k.startswith("_")}
        print(c(f"  Поля ({len(filled)}): {list(filled.keys()) or '(пусто)'}", GRAY))
    elif current_step == Step.FILL_EXTERNAL:
        method = slots.get("fill_method", "paper")
        label = "стороннее приложение" if method == "app_external" else "бумажный бланк"
        print(c(f"  Метод: {label}", GRAY))
    print(c(hr("─", 50), GRAY))


def run_full_pipeline() -> None:
    section("ПОЛНЫЙ PIPELINE: step1 → step2 → step3")
    print(c("Команды: 'выход' — завершить | 'состояние' — показать данные\n", GRAY))

    history: list[dict] = []
    current_step: str = Step.STEP1
    slots: dict = {}
    collected_fields: dict = {}
    feedback_db = get_feedback_db()

    while True:
        _print_pipeline_state(current_step, slots, collected_fields)
        query = prompt()
        if not query:
            continue
        if is_exit(query):
            break
        if is_show_state(query):
            show_json({"step": current_step, "slots": slots, "collected_fields": collected_fields}, "Состояние")
            continue

        response = run_agent(
            query=query, current_step=current_step, history=history,
            slots=slots, collected_fields=collected_fields,
        )

        answer = response.get("answer") or ""
        if answer:
            assistant_says(answer)
        else:
            system_msg("[системный переход, ответ отсутствует]")

        history.append({"query": query, "answer": answer})

        if response.get("slots") is not None:
            slots = response["slots"]
        if response.get("collected_fields") is not None:
            collected_fields = response["collected_fields"]

        system_msg(
            f"source={response.get('source')} | "
            f"step_completed={response.get('step_completed')} | "
            f"next_step={response.get('next_step')}"
        )

        if answer:
            maybe_rate(query, answer, feedback_db)

        if not response.get("step_completed"):
            continue

        next_s = response.get("next_step")
        if next_s is None:
            continue

        if next_s == Step.STEP1:
            current_step = Step.STEP1
        elif next_s == Step.OFFER_EUROPROTOCOL:
            current_step = Step.OFFER_EUROPROTOCOL
            system_msg("→ Предложение Европротокола")
        elif next_s == Step.OFFER_METHOD:
            current_step = Step.OFFER_EUROPROTOCOL
        elif next_s == Step.STEP2:
            current_step = Step.STEP2
            system_msg("→ Шаг 2: заполнение через приложение")
        elif next_s == Step.FILL_EXTERNAL:
            current_step = Step.FILL_EXTERNAL
            method = slots.get("fill_method", "paper")
            label = "стороннее приложение" if method == "app_external" else "бумажный бланк"
            system_msg(f"→ Самостоятельное заполнение ({label})")
        elif next_s == Step.STEP3:
            current_step = Step.STEP3
            system_msg("→ Шаг 3: взаимодействие со страховой")
        elif next_s == Step.CONSULTANT_ONLY:
            current_step = Step.CONSULTANT_ONLY
            slots = {}
            collected_fields = {}
            system_msg("→ Режим консультанта")
        elif next_s == Step.DONE:
            if response.get("final_json"):
                system_msg("✅ Протокол готов!")
                show_json(response["final_json"], "Протокол")
            current_step = Step.STEP3
            system_msg("→ Шаг 3: взаимодействие со страховой")
        elif next_s == Step.CALL_GIBDD:
            system_msg("⚠️  Вызовите ГИБДД (102). Сессия завершена.")
            break


# ===========================================================================
# РЕЖИМ 2: Step 1
# ===========================================================================

def run_module_step1() -> None:
    section("МОДУЛЬ: Step 1 — сбор фактов")
    print(c("Тестируем process_step1_with_llm напрямую.", GRAY))
    print(c("Команды: 'выход' | 'состояние' | 'сброс'\n", GRAY))

    history: list[dict] = []
    slots: dict = {}

    with make_giga() as giga:
        while True:
            query = prompt()
            if not query:
                continue
            if is_exit(query):
                break
            if is_show_state(query):
                show_json(slots, "Слоты")
                continue
            if query.lower() in ("сброс", "reset"):
                slots = {}
                history = []
                system_msg("Состояние сброшено.")
                continue

            result = process_step1_with_llm(giga, query, history, slots)
            if result.answer:
                assistant_says(result.answer)

            slots = dict(result.slots)
            history.append({"query": query, "answer": result.answer or ""})
            system_msg(f"step_completed={result.step_completed} | next_step={result.next_step}")
            show_json(
                {k: v for k, v in slots.items()
                 if not k.startswith("_") and k != "disagreement_slots"},
                "Слоты"
            )

            if result.step_completed:
                system_msg(f"✅ Шаг завершён → {result.next_step}")
                if result.prefilled_fields:
                    show_json(result.prefilled_fields, "Prefilled fields")
                cont = input(c("\nПродолжить с новыми слотами? (да/нет): ", GRAY)).strip().lower()
                if cont != "да":
                    break
                slots = dict(result.slots)


# ===========================================================================
# РЕЖИМ 3: Step 2
# ===========================================================================

def _ask_prefill_step2() -> tuple[dict, dict]:
    print(c("\nВвести начальные поля? (Enter — пропустить, 'да' — ввести JSON):", GRAY))
    choice = input().strip().lower()
    if choice != "да":
        return {}, {}
    print(c("Вставьте JSON со слотами step1 (Enter дважды для завершения):", GRAY))
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    try:
        slots = json.loads("\n".join(lines))
        print(c("Вставьте JSON с начальными collected_fields (Enter дважды):", GRAY))
        lines2 = []
        while True:
            line2 = input()
            if not line2:
                break
            lines2.append(line2)
        fields = json.loads("\n".join(lines2)) if lines2 else {}
        return slots, fields
    except json.JSONDecodeError as e:
        error_msg(f"Ошибка парсинга JSON: {e}")
        return {}, {}


def run_module_step2() -> None:
    section("МОДУЛЬ: Step 2 — заполнение Европротокола")
    print(c("Тестируем process_step2_with_llm напрямую.", GRAY))
    print(c("Команды: 'выход' | 'состояние' | 'сброс'\n", GRAY))

    slots, collected_fields = _ask_prefill_step2()
    history: list[dict] = []

    with make_giga() as giga:
        while True:
            query = prompt()
            if not query:
                continue
            if is_exit(query):
                break
            if is_show_state(query):
                show_json(collected_fields, "Поля протокола")
                continue
            if query.lower() in ("сброс", "reset"):
                collected_fields = {}
                history = []
                system_msg("Состояние сброшено.")
                continue

            result = process_step2_with_llm(giga, query, history, slots, collected_fields)
            if result.answer:
                assistant_says(result.answer)

            collected_fields = dict(result.collected_fields or {})
            history.append({"query": query, "answer": result.answer or ""})
            filled = {k: v for k, v in collected_fields.items() if not k.startswith("_")}
            system_msg(f"step_completed={result.step_completed} | Заполнено полей: {len(filled)}")

            if result.step_completed:
                system_msg("✅ Протокол готов!")
                if result.final_json:
                    show_json(result.final_json, "Final JSON")
                break


# ===========================================================================
# РЕЖИМ 4: Step 3
# ===========================================================================

def run_module_step3() -> None:
    section("МОДУЛЬ: Step 3 — взаимодействие со страховой")
    print(c("Тестируем process_step3 напрямую.", GRAY))
    print(c("Команды: 'выход' | 'состояние'\n", GRAY))

    print(c("Вставьте JSON с collected_fields (или Enter для пустого старта):", GRAY))
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)

    try:
        collected_fields = json.loads("\n".join(lines)) if lines else {}
    except json.JSONDecodeError:
        collected_fields = {}
        error_msg("Ошибка JSON, старт с пустыми полями.")

    history: list[dict] = []
    db = get_main_db()
    feedback_db = get_feedback_db()

    with make_giga() as giga:
        while True:
            query = prompt()
            if not query:
                continue
            if is_exit(query):
                break
            if is_show_state(query):
                show_json(collected_fields, "Поля")
                continue

            result = process_step3(giga, query, history, collected_fields, db, feedback_db)
            if result.answer:
                assistant_says(result.answer)

            collected_fields = dict(result.collected_fields or {})
            history.append({"query": query, "answer": result.answer or ""})
            system_msg(
                f"step_completed={result.step_completed} | "
                f"next_step={result.next_step} | "
                f"phase={collected_fields.get('step3_phase', 'phase1')}"
            )

            if result.final_json:
                show_json(result.final_json, "Обращение")

            if result.step_completed:
                system_msg(f"✅ Шаг завершён → {result.next_step}")
                break


# ===========================================================================
# РЕЖИМ 5: Disagreement Helper
# ===========================================================================

def run_module_disagreement() -> None:
    section("МОДУЛЬ: Disagreement Helper — анализ разногласий")
    print(c("Тестируем run_disagreement_help напрямую.", GRAY))
    print(c("Команды: 'выход' | 'состояние' | 'сброс'\n", GRAY))

    history: list[dict] = []
    slots: dict = {
        "safety_confirmed": True, "emergency_sign": True, "victims": False,
        "participants_count": 2, "osago_both": True, "disagreement": True,
        "disagreement_help_active": True, "disagreement_help_offered": True,
    }
    disagreement_db = get_disagreement_db()

    system_msg("Стартовые слоты установлены (2 участника, есть ОСАГО, разногласия).")
    show_json(slots, "Начальные слоты")

    with make_giga() as giga:
        while True:
            query = prompt()
            if not query:
                continue
            if is_exit(query):
                break
            if is_show_state(query):
                show_json(slots.get("disagreement_slots", {}), "Слоты разногласий")
                continue
            if query.lower() in ("сброс", "reset"):
                slots.pop("disagreement_slots", None)
                history = []
                system_msg("Слоты разногласий сброшены.")
                continue

            result = run_disagreement_help(giga, query, history, slots, disagreement_db)
            if result.answer:
                assistant_says(result.answer)

            slots = dict(result.slots or {})
            history.append({"query": query, "answer": result.answer or ""})

            d_slots = slots.get("disagreement_slots", {})
            if d_slots:
                filled = {k: v for k, v in d_slots.items() if v is not None and not k.startswith("_")}
                system_msg(f"Заполнено слотов разногласий: {len(filled)}")
                show_json(filled, "Слоты разногласий")

            system_msg(
                f"step_completed={result.step_completed} | "
                f"next_step={result.next_step} | "
                f"disagreement_help_active={slots.get('disagreement_help_active')}"
            )

            if result.step_completed:
                system_msg(f"✅ Режим завершён → {result.next_step}")
                break


# ===========================================================================
# РЕЖИМ 6: Meta Classifier
# ===========================================================================

def run_module_classifier() -> None:
    section("МОДУЛЬ: Meta Classifier")
    print(c("Тестируем meta_classify напрямую.", GRAY))
    print(c("Каждое сообщение → категория + блок алгоритма.\n", GRAY))

    history: list[dict] = []

    with make_giga() as giga:
        while True:
            query = prompt("Запрос")
            if not query:
                continue
            if is_exit(query):
                break

            from agent.history import build_history
            history_text = build_history(history, component="classifier")
            result = meta_classify(giga, query, history_text)

            print(f"\n{c('Результат:', YELLOW)}")
            print(f"  category : {c(result['category'], CYAN)}")
            print(f"  block    : {result['block']}")
            print(f"  relevant : {result['relevant']}")

            history.append({"query": query, "answer": f"[category={result['category']}]"})


# ===========================================================================
# РЕЖИМ 7: Template Matcher
# ===========================================================================

def run_module_templates() -> None:
    section("МОДУЛЬ: Template Matcher")
    print(c("Тестируем match_template напрямую.", GRAY))
    print(c("Каждое сообщение → шаблонный ответ или None.\n", GRAY))

    while True:
        query = prompt("Запрос")
        if not query:
            continue
        if is_exit(query):
            break

        result = match_template(query)
        if result:
            print(f"\n{c('✅ Шаблон найден:', GREEN)}")
            print(result)
        else:
            print(c("\n❌ Шаблон не найден — передать в LLM.", YELLOW))


# ===========================================================================
# РЕЖИМ 8: Консультант
# ===========================================================================

def run_module_consultant() -> None:
    section("МОДУЛЬ: Консультант (general mode)")
    print(c("Режим: current_step=None, полный pipeline без шагов.", GRAY))
    print(c("Команды: 'выход'\n", GRAY))

    history: list[dict] = []
    feedback_db = get_feedback_db()

    while True:
        query = prompt()
        if not query:
            continue
        if is_exit(query):
            break

        response = run_agent(query=query, current_step=None, history=history)
        answer = response.get("answer") or ""
        if answer:
            assistant_says(answer)

        history.append({"query": query, "answer": answer})
        system_msg(f"source={response.get('source')} | category={response.get('category')}")

        if answer:
            maybe_rate(query, answer, feedback_db)


# ===========================================================================
# РЕЖИМ 9: Сканер документов
# ===========================================================================

_TEST_DOCS_DIR = "test_docs"


def _select_image() -> str | None:
    """Показывает список фото из test_docs/ и предлагает выбрать одно."""
    docs_dir = ensure_test_docs_dir(_TEST_DOCS_DIR)
    images = find_images(docs_dir)

    if not images:
        print(c(
            f"\n  Папка {_TEST_DOCS_DIR}/ пуста.\n"
            f"  Положи туда фото документа (.jpg, .jpeg, .png, .webp) и запусти снова.",
            YELLOW
        ))
        return None

    print(f"\n{c('  Найденные фото:', BOLD)}")
    for i, path in enumerate(images, 1):
        size_kb = path.stat().st_size // 1024
        print(f"  {c(str(i), CYAN)}. {path.name}  {c(f'({size_kb} КБ)', GRAY)}")

    choice = input(f"\n{c('Выберите номер фото (или Enter для отмены):', CYAN)} ").strip()
    if not choice:
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(images):
            return str(images[idx])
        error_msg(f"Неверный номер: {choice}")
        return None
    except ValueError:
        error_msg(f"Введите число от 1 до {len(images)}")
        return None


def run_module_scanner() -> None:
    section("МОДУЛЬ: Сканер документов")
    print(c(
        f"  Кладёшь фото в папку  {c(_TEST_DOCS_DIR + '/', CYAN)}\n"
        f"  Агент сам определяет тип документа и извлекает поля профиля.\n"
        f"  Поддерживаемые форматы: JPEG, PNG, WEBP.\n",
        GRAY
    ))

    ensure_test_docs_dir(_TEST_DOCS_DIR)

    while True:
        image_path = _select_image()
        if image_path is None:
            break

        print(f"\n{c('[система]', GRAY)} Сканирую документ...")
        try:
            result = scan_to_profile(image_path)
        except (FileNotFoundError, ValueError) as e:
            error_msg(str(e))
            break
        except Exception as e:
            error_msg(f"Неожиданная ошибка: {e}")
            break

        print(f"\n{c(hr(), BLUE)}")
        doc_type = result.get("document_type")

        if doc_type:
            type_labels = {
                "osago":          "Полис ОСАГО",
                "driver_license": "Водительское удостоверение",
                "sts":            "СТС / ПТС",
            }
            system_msg(f"Тип документа: {c(type_labels.get(doc_type, doc_type), CYAN)}")

        fields = {k: v for k, v in result.items() if k != "document_type"}

        if fields:
            print(c(f"  ✅ Извлечено полей: {len(fields)}", GREEN))
            print(c(hr(), BLUE))
            show_json(fields, "Поля профиля")
        else:
            print(c("  ❌ Не удалось извлечь данные.", RED))
            print(c("  Проверь качество фото и убедись что документ целиком в кадре.", YELLOW))
            print(c(hr(), BLUE))

        again = input(
            f"\n{c('Сканировать ещё один документ? (да/Enter для выхода):', GRAY)} "
        ).strip().lower()
        if again != "да":
            break


# ===========================================================================
# ГЛАВНОЕ МЕНЮ
# ===========================================================================

MENU_ITEMS: list[tuple[str, str, Callable]] = [
    ("1", "Полный pipeline (step1 → step2 → step3)",      run_full_pipeline),
    ("2", "Только Step 1 — сбор фактов",                  run_module_step1),
    ("3", "Только Step 2 — заполнение Европротокола",     run_module_step2),
    ("4", "Только Step 3 — взаимодействие со страховой",  run_module_step3),
    ("5", "Disagreement Helper — анализ разногласий",     run_module_disagreement),
    ("6", "Meta Classifier — классификация запроса",      run_module_classifier),
    ("7", "Template Matcher — шаблонные ответы",          run_module_templates),
    ("8", "Консультант — general mode",                   run_module_consultant),
    ("9", "Сканер документов — фото → поля профиля",      run_module_scanner),
    ("0", "Выход",                                        None),
]


def print_menu() -> None:
    print(f"\n{c(hr('═'), BLUE)}")
    print(c("  ДТП-ассистент — локальное тестирование", BOLD))
    print(c(hr('═'), BLUE))
    for key, label, _ in MENU_ITEMS:
        marker = c(f"  [{key}]", CYAN)
        print(f"{marker} {label}")
    print(c(hr('─'), GRAY))


def main() -> None:
    while True:
        print_menu()
        choice = input(c("\nВыбор: ", BOLD)).strip()

        if choice == "0":
            print(c("\nДо свидания!\n", GREEN))
            break

        handler = None
        for key, _, fn in MENU_ITEMS:
            if choice == key:
                handler = fn
                break

        if handler is None:
            error_msg(f"Неизвестный выбор: {choice!r}")
            continue

        try:
            handler()
        except KeyboardInterrupt:
            system_msg("Прервано. Возврат в меню.")
        except Exception as e:
            error_msg(f"Неожиданная ошибка: {e}")
            import traceback
            traceback.print_exc()

        input(c("\n[Enter для возврата в меню]", GRAY))


if __name__ == "__main__":
    main()