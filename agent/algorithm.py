def load_algorithm(path: str = "Docs_md/ai-algorithm.md") -> str:
    """Загружает алгоритм из файла. Вызывается один раз при старте."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""