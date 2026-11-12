"""Generic helpers that know nothing about Visual EPS data or Forge."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LOG_PREFIX = "[Visual Easy Prompt Selector / Visual EPS]"


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}")


def resolve_path(path_text: str, base: Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else base / path


def load_json(path: Path, fallback: Any) -> Any:
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        log(f"failed to load {path.name}: {exc}")
        return fallback


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def normalize_key(value: str) -> str:
    value = value.lower().replace("\\", "/")
    value = re.sub(r"\.[a-z0-9]+$", "", value)
    value = re.sub(r"_[0-9a-f]{6,}$", "", value)
    value = re.sub(r"[^0-9a-z぀-ヿ㐀-鿿]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def natural_sort_key(value: Any) -> tuple[tuple[int, Any], ...]:
    """Return a natural-sort key without treating non-ASCII numerals as int()."""
    return tuple(
        (1, int(part)) if part.isascii() and part.isdigit() else (0, part.casefold())
        for part in re.split(r"([0-9]+)", str(value))
    )


def safe_filename(value: str, fallback: str = "visual_eps") -> str:
    normalized = normalize_key(value)
    return normalized[:120] or fallback


def yaml_child(node: Any, step: list[Any]) -> tuple[Any, Any]:
    """Resolve one locator step on a loaded YAML node. Returns (key or index in node, child value)."""
    kind, value = step
    if kind == "key" and isinstance(node, dict):
        for key in node:
            if str(key) == value:
                return key, node[key]
    if kind == "index" and isinstance(node, list) and isinstance(value, int) and 0 <= value < len(node):
        return value, node[value]
    raise KeyError(f"YAML entry not found: {step}")


def yaml_value_at(data: Any, locator: list[list[Any]]) -> tuple[Any, Any, Any]:
    """Return (parent container, key or index in parent, value) for a locator."""
    parent, slot, node = None, None, data
    for step in locator:
        parent = node
        slot, node = yaml_child(node, step)
    return parent, slot, node
