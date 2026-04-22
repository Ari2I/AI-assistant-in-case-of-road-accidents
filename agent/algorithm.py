"""
Загрузка алгоритма с нарезкой по блокам.

Вместо передачи всего файла (~3000 токенов) в генератор
передаётся только нужный блок + соседние для контекста (~400 токенов).
"""

from __future__ import annotations

import re

_FULL_ALGORITHM: str = ""
_BLOCKS: dict[int, str] = {}


def load_algorithm(path: str = "Docs_md/ai-algorithm.md") -> str:
    """Загружает алгоритм из файла. Вызывается один раз при старте."""
    global _FULL_ALGORITHM, _BLOCKS
    try:
        with open(path, encoding="utf-8") as f:
            _FULL_ALGORITHM = f.read()
        _BLOCKS = _parse_blocks(_FULL_ALGORITHM)
        return _FULL_ALGORITHM
    except FileNotFoundError:
        return ""


def get_algorithm_slice(block: int, window: int = 1) -> str:
    """
    Возвращает блок алгоритма ± window соседних блоков.

    Args:
        block:  номер текущего блока (0-9)
        window: сколько блоков до и после включать

    Returns:
        Строка с нужными блоками. Если парсинг не сработал — весь алгоритм.
    """
    if not _BLOCKS:
        return _FULL_ALGORITHM

    indices = range(
        max(0, block - window),
        min(9, block + window) + 1,
    )
    parts = [_BLOCKS[i] for i in indices if i in _BLOCKS]

    if not parts:
        return _FULL_ALGORITHM

    return "\n\n".join(parts)


def _parse_blocks(text: str) -> dict[int, str]:
    """Разбивает алгоритм на блоки по заголовкам '## БЛОК N'."""
    blocks: dict[int, str] = {}
    pattern = re.compile(r"(##\s+БЛОК\s+(\d+)[^\n]*\n)", re.IGNORECASE)
    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        block_num = int(match.group(2))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[block_num] = text[start:end].strip()

    return blocks