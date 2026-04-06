import json
import os


def load_history(user_id):
    """
    Загружает историю пользователя.

    Args:
        user_id (str): ID пользователя

    Returns:
        list: история сообщений
    """
    os.makedirs("history", exist_ok=True)

    path = f"history/{user_id}.json"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    return []


def save_history(user_id, history):
    """
    Сохраняет историю пользователя.

    Args:
        user_id (str): ID пользователя
        history (list): список сообщений
    """
    os.makedirs("history", exist_ok=True)

    path = f"history/{user_id}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)