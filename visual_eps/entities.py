"""Shape of Visual EPS data, and pure functions that build or read it.

Items stay plain dicts (they go straight to JSON and Forge); the TypedDicts document their keys.
"""

from __future__ import annotations

from typing import Any, TypedDict


# Where a prompt lives in its YAML file: [["key", "<key text>"] | ["index", <n>], ...].
YamlLocator = list[list[Any]]


class EpsItem(TypedDict, total=False):
    """One prompt read from an EPS YAML file."""

    id: str
    source_type: str
    display_name: str
    category_path: str
    prompt: str
    source_file: str
    source_path: str
    raw_path: str
    yaml_locator: YamlLocator
    prompt_editable: bool


class MetadataEntry(TypedDict, total=False):
    """Per-item settings saved in visual_eps_metadata.json, keyed by EpsItem id."""

    image: str
    display_name_override: str
    prepend_prompt: str
    append_prompt: str
    append_negative: str
    memo: str
    tags: list[str]


class VisualEpsCard(EpsItem, MetadataEntry, total=False):
    """An EpsItem merged with its metadata, as shown on a card and sent to the Prompt edit dialog."""

    display_name_effective: str


# MetadataEntry text fields that the Prompt edit dialog can save.
METADATA_TEXT_FIELDS = (
    "image",
    "display_name_override",
    "prepend_prompt",
    "append_prompt",
    "append_negative",
    "memo",
)


def make_item(path_parts: list[str], prompt: str, source_file: str, locator: YamlLocator) -> EpsItem:
    safe_parts = [str(part).strip() for part in path_parts if str(part).strip()]
    display_name = safe_parts[-1] if safe_parts else prompt[:60]
    category_path = "/".join(safe_parts[:-1])
    raw_path = "/".join(safe_parts)
    return {
        "id": f"eps:{raw_path}",
        "source_type": "eps",
        "display_name": display_name,
        "category_path": category_path,
        "prompt": str(prompt or ""),
        "source_file": source_file,
        "raw_path": raw_path,
        "yaml_locator": locator,
        "prompt_editable": bool(locator),
    }


def stable_ids(items: list[dict[str, str]]) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item["id"]] = counts.get(item["id"], 0) + 1
    for item in items:
        if counts.get(item["id"], 0) > 1:
            item["id"] = f"eps:{item['source_file']}:{item['raw_path']}"
    return items


def metadata_entry_for_save(payload: dict[str, Any], existing: dict[str, Any]) -> MetadataEntry:
    entry = dict(existing) if isinstance(existing, dict) else {}
    for field in METADATA_TEXT_FIELDS:
        if field in payload:
            entry[field] = str(payload.get(field) or "")
    if "tags" in payload:
        tags = payload.get("tags")
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",")]
        if isinstance(tags, list):
            entry["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
    return {key: value for key, value in entry.items() if value not in ("", [], None)}


def compose_prompt(item: dict[str, Any], separator: str) -> str:
    parts = [item.get("prepend_prompt", ""), item.get("prompt", ""), item.get("append_prompt", "")]
    return separator.join([str(part).strip() for part in parts if str(part).strip()])


def search_blob(item: dict[str, Any]) -> str:
    fields = [
        item.get("display_name", ""),
        item.get("display_name_effective", ""),
        item.get("category_path", ""),
        item.get("prompt", ""),
        item.get("prepend_prompt", ""),
        item.get("append_prompt", ""),
        item.get("append_negative", ""),
        " ".join([str(tag) for tag in item.get("tags", [])]),
        item.get("memo", ""),
        item.get("source_file", ""),
    ]
    return " ".join(str(field) for field in fields).lower()
