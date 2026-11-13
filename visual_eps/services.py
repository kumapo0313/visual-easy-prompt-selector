"""Domain services: read EPS YAML, manage metadata and preview images, and save Prompt edit changes."""

from __future__ import annotations

import base64
import difflib
import io
import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from .config import (
    BASE_DIR,
    IMAGE_EXTENSIONS,
    SAMPLE_EPS_DIR,
    eps_previews_dir,
    eps_prompts_dir,
    load_config,
    metadata_path,
    stored_path,
)
from .entities import YamlLocator, make_item, metadata_entry_for_save, stable_ids
from .utils import is_scalar, load_json, log, resolve_path, safe_filename, yaml_value_at


class ItemNotFoundError(LookupError):
    """No EPS item has the requested id."""


class InvalidEditError(ValueError):
    """The Prompt edit request asks for a change that is not allowed."""


class SamplesNotCopiedError(RuntimeError):
    """The bundled samples cannot be copied (missing, or the prompts folder already has YAML files)."""


# --- EPS YAML ---------------------------------------------------------------


def yaml_files(root: Path) -> list[Path]:
    try:
        if not root.exists():
            log(f"EPS path does not exist: {root}")
            return []
        return sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml"))
    except Exception as exc:
        log(f"failed to scan EPS path {root}: {exc}")
        return []


def walk_yaml(
    node: Any,
    path_parts: list[str],
    source_file: str,
    items: list[dict[str, Any]],
    locator: YamlLocator | None = None,
) -> None:
    locator = locator or []
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            child_locator = locator + [["key", key_text]]
            if is_scalar(value):
                items.append(make_item(path_parts + [key_text], str(value or key_text), source_file, child_locator))
            else:
                walk_yaml(value, path_parts + [key_text], source_file, items, child_locator)
        return

    if isinstance(node, list):
        for index, value in enumerate(node):
            child_locator = locator + [["index", index]]
            if is_scalar(value):
                text = str(value or "")
                if text.strip():
                    items.append(make_item(path_parts + [text], text, source_file, child_locator))
            elif isinstance(value, dict):
                walk_yaml(value, path_parts, source_file, items, child_locator)
            else:
                walk_yaml(value, path_parts + [str(index)], source_file, items, child_locator)
        return

    if is_scalar(node):
        text = str(node or "")
        if text.strip():
            # A bare scalar file has no key to write back to, so it stays read-only.
            items.append(make_item(path_parts + [text], text, source_file, []))


def load_eps_items(config: dict[str, Any], failed_files: list[Path] | None = None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for path in yaml_files(eps_prompts_dir(config)):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
            if data is None:
                continue
            before = len(items)
            walk_yaml(data, [], path.name, items)
            for item in items[before:]:
                item["source_file"] = path.name
                item["source_path"] = str(path)
        except Exception as exc:
            log(f"skipped YAML {path}: {exc}")
            if failed_files is not None:
                failed_files.append(path)

    return stable_ids(items)


def ruamel_modules() -> tuple[Any, Any, Any]:
    """(YAML, LiteralScalarString, ScalarString) from ruamel.yaml, which round-trip edits need."""
    try:
        from ruamel.yaml import YAML
        from ruamel.yaml.scalarstring import LiteralScalarString, ScalarString
    except ImportError as exc:
        raise RuntimeError("Editing EPS prompts requires ruamel.yaml. Restart WebUI to install it, or run: pip install ruamel.yaml") from exc
    return YAML, LiteralScalarString, ScalarString


def editable_location(item: dict[str, Any]) -> tuple[Path, YamlLocator]:
    locator = item.get("yaml_locator") or []
    source_path = str(item.get("source_path") or "")
    if not item.get("prompt_editable") or not locator or not source_path:
        raise ValueError("This EPS entry cannot be edited.")
    return Path(source_path), locator


def check_current_prompt(path: Path, locator: YamlLocator, current: Any, item: dict[str, Any]) -> None:
    """Refuse to write when the entry no longer holds the prompt Visual EPS loaded."""
    current_prompt = str(current or (str(locator[-1][1]) if locator[-1][0] == "key" else ""))
    if current_prompt != item.get("prompt", ""):
        raise RuntimeError(f"{path.name} changed on disk. Reload Visual EPS and try again.")


def styled_prompt(current: Any, new_prompt: str) -> Any:
    """new_prompt as a scalar in the same style as current (block style when it has several lines)."""
    _, LiteralScalarString, ScalarString = ruamel_modules()
    if isinstance(current, LiteralScalarString) or "\n" in new_prompt:
        return LiteralScalarString(new_prompt)
    if isinstance(current, ScalarString):
        return type(current)(new_prompt)
    return new_prompt


def rewrite_yaml(path: Path, edit: Any) -> Any:
    """Load path with ruamel, call edit(data) to change it in place, and write it back.

    Comments and block styles are kept. Nothing is written yet: returns (the output parsed as plain YAML,
    a function that writes it), so the caller can check the result first.
    """
    YAML, _, _ = ruamel_modules()
    raw = path.read_bytes()
    # ruamel keeps "\r" inside comments, so work in LF and restore the file's line endings on write.
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    newline = "\r\n" if b"\r\n" in raw else "\n"

    def render(mapping: int, sequence: int, offset: int) -> str:
        rt = YAML()
        rt.preserve_quotes = True
        rt.width = 4096
        rt.indent(mapping=mapping, sequence=sequence, offset=offset)
        data = rt.load(text)
        edit(data)
        buffer = io.StringIO()
        rt.dump(data, buffer)
        return buffer.getvalue()

    # ruamel re-indents the whole document, and its indent guess is unreliable,
    # so render with common layouts and keep the one that changes the fewest lines.
    original_lines = text.splitlines()

    def changed_lines(output: str) -> int:
        matcher = difflib.SequenceMatcher(None, original_lines, output.splitlines(), autojunk=False)
        return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")

    layouts = [(m, s, o) for m in (2, 4) for s in (2, 4) for o in (0, 2) if o < s]
    output = min((render(*layout) for layout in layouts), key=changed_lines)
    parsed = yaml.safe_load(output)

    def write() -> None:
        path.write_text(output, encoding="utf-8", newline=newline)

    return parsed, write


def update_yaml_prompt(item: dict[str, Any], new_prompt: str) -> None:
    """Write a new prompt into the item's YAML file, keeping comments and block styles."""
    path, locator = editable_location(item)

    def edit(data: Any) -> None:
        parent, slot, current = yaml_value_at(data, locator)
        check_current_prompt(path, locator, current, item)
        parent[slot] = styled_prompt(current, new_prompt)

    parsed, write = rewrite_yaml(path, edit)
    _, _, written = yaml_value_at(parsed, locator)
    if str(written) != new_prompt:
        raise RuntimeError(f"Could not write the prompt to {path.name} safely; the file was not changed.")
    write()


def duplicate_yaml_entry(item: dict[str, Any]) -> YamlLocator:
    """Add a copy of a "key: prompt" entry right after it, under a free "<key>_copy" key. Returns its locator."""
    path, locator = editable_location(item)
    if locator[-1][0] != "key":
        # List-style entries are identified by their prompt text, so an identical copy would share the id.
        raise InvalidEditError("Only \"name: prompt\" entries can be duplicated; list-style entries cannot.")
    parent_locator = locator[:-1]
    new_key = ""

    def edit(data: Any) -> None:
        nonlocal new_key
        parent, slot, current = yaml_value_at(data, locator)
        check_current_prompt(path, locator, current, item)
        taken = {str(key) for key in parent}
        base = f"{slot}_copy"
        new_key, counter = base, 2
        while new_key in taken:
            new_key = f"{base}{counter}"
            counter += 1
        # An empty value means "the key is the prompt", which the new key would change, so always write the prompt.
        prompt = str(item.get("prompt") or "")
        parent.insert(list(parent.keys()).index(slot) + 1, new_key, styled_prompt(current, prompt))

    parsed, write = rewrite_yaml(path, edit)
    new_locator = parent_locator + [["key", new_key]]
    _, _, written = yaml_value_at(parsed, new_locator)
    _, _, original = yaml_value_at(parsed, locator)
    if str(written) != item.get("prompt", "") or str(original or locator[-1][1]) != item.get("prompt", ""):
        raise RuntimeError(f"Could not duplicate the entry in {path.name} safely; the file was not changed.")
    write()
    return new_locator


def delete_yaml_entry(item: dict[str, Any]) -> None:
    """Remove the item's entry from its YAML file, keeping the rest of the file as it is."""
    path, locator = editable_location(item)

    def remove(data: Any) -> None:
        parent, slot, current = yaml_value_at(data, locator)
        check_current_prompt(path, locator, current, item)
        del parent[slot]

    parsed, write = rewrite_yaml(path, remove)
    # The result must be exactly the old file's data minus this one entry.
    expected = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    remove(expected)
    if parsed != expected:
        raise RuntimeError(f"Could not delete the entry from {path.name} safely; the file was not changed.")
    write()


# --- Metadata ---------------------------------------------------------------


def load_metadata() -> dict[str, Any]:
    loaded = load_json(metadata_path(load_config()), {})
    return loaded if isinstance(loaded, dict) else {}


def save_metadata(metadata: dict[str, Any]) -> None:
    try:
        metadata_path(load_config()).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    except Exception as exc:
        log(f"failed to save metadata: {exc}")
        raise


# --- Preview images ---------------------------------------------------------


def managed_preview_path(image_text: str, config: dict[str, Any]) -> Path | None:
    """Resolve a metadata image path, but only when it is an image directly inside <eps_dir>/previews."""
    text = str(image_text or "").strip()
    if not text:
        return None
    path = resolve_path(text, BASE_DIR).resolve()
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    if path.parent != eps_previews_dir(config).resolve():
        return None
    return path


def referenced_previews(metadata: dict[str, Any], config: dict[str, Any], ids: set[str] | None = None) -> set[Path]:
    """Managed preview files referenced by metadata entries (only entries in ids, when given)."""
    files: set[Path] = set()
    for item_id, entry in metadata.items():
        if ids is not None and item_id not in ids:
            continue
        if isinstance(entry, dict):
            path = managed_preview_path(entry.get("image", ""), config)
            if path:
                files.add(path)
    return files


def delete_preview_if_unused(image_text: str, metadata: dict[str, Any], config: dict[str, Any]) -> None:
    """Delete a replaced or cleared preview image unless another metadata entry still uses it."""
    if not config.get("auto_remove_unused_previews", True):
        return
    path = managed_preview_path(image_text, config)
    if not path or not path.exists() or path in referenced_previews(metadata, config):
        return
    try:
        path.unlink()
        log(f"deleted unused preview image: {path.name}")
    except Exception as exc:
        log(f"failed to delete unused preview image {path}: {exc}")


def can_cleanup(raw_items: list[dict[str, str]], failed_files: list[Path], what: str) -> bool:
    """Cleanups judge "unused" from the loaded prompts, so they only run after a complete, non-empty load."""
    if failed_files:
        log(f"{what} cleanup skipped because some EPS YAML files failed to load")
        return False
    if not raw_items:
        log(f"{what} cleanup skipped because no EPS prompts were loaded")
        return False
    return True


def cleanup_unused_metadata(
    raw_items: list[dict[str, str]],
    metadata: dict[str, Any],
    config: dict[str, Any],
    failed_files: list[Path],
) -> None:
    """Delete metadata entries whose prompt no longer exists in the EPS YAML files (on by default)."""
    if not config.get("auto_remove_unused_metadata", True):
        return
    if not can_cleanup(raw_items, failed_files, "unused metadata"):
        return

    try:
        active_ids = {str(item["id"]) for item in raw_items}
        orphan_ids = [key for key in metadata if key not in active_ids]
        if not orphan_ids:
            return
        for item_id in orphan_ids:
            del metadata[item_id]
        save_metadata(metadata)
        log(f"auto removed {len(orphan_ids)} unused metadata entr{'y' if len(orphan_ids) == 1 else 'ies'}")
    except Exception as exc:
        log(f"unused metadata cleanup failed: {exc}")


def cleanup_unused_previews(
    raw_items: list[dict[str, str]],
    metadata: dict[str, Any],
    config: dict[str, Any],
    failed_files: list[Path],
) -> None:
    """Delete images in <eps_dir>/previews that no current EPS prompt uses.

    Metadata entries whose prompt no longer exists lose their "image" (and are dropped when nothing else is left).
    """
    if not config.get("auto_remove_unused_previews", True):
        return
    if not can_cleanup(raw_items, failed_files, "unused preview"):
        return

    try:
        active_ids = {str(item["id"]) for item in raw_items}
        keep = referenced_previews(metadata, config, active_ids)

        metadata_changed = False
        for item_id in [key for key in metadata if key not in active_ids]:
            entry = metadata[item_id]
            if isinstance(entry, dict) and "image" in entry:
                del entry["image"]
                metadata_changed = True
                if not any(entry.values()):
                    del metadata[item_id]
        if metadata_changed:
            save_metadata(metadata)

        removed = 0
        for path in eps_previews_dir(config).iterdir():
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS or path.resolve() in keep:
                continue
            path.unlink()
            removed += 1
            log(f"deleted unused preview image: {path.name}")
        if removed:
            log(f"auto removed {removed} unused preview image(s)")
    except Exception as exc:
        log(f"unused preview cleanup failed: {exc}")


def save_image_data_url(data_url: str, original_name: str, item: dict[str, Any]) -> str:
    match = re.match(r"^data:(?P<mime>image/(?:png|jpeg|jpg|webp));base64,(?P<data>.+)$", data_url or "", re.DOTALL)
    if not match:
        raise ValueError("Unsupported image data")
    mime = match.group("mime").replace("image/jpg", "image/jpeg")
    ext = mimetypes.guess_extension(mime) or Path(original_name or "").suffix.lower()
    if ext == ".jpe":
        ext = ".jpg"
    if ext.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image extension")

    raw = base64.b64decode(match.group("data"), validate=True)
    if len(raw) > 40 * 1024 * 1024:
        raise ValueError("Image is too large")

    base_name = safe_filename(str(item.get("raw_path") or item.get("display_name") or item.get("id")))
    previews_dir = eps_previews_dir(load_config())
    target = previews_dir / f"{base_name}{ext}"
    counter = 2
    while target.exists():
        target = previews_dir / f"{base_name}_{counter}{ext}"
        counter += 1
    target.write_bytes(raw)
    return stored_path(target)


# --- Samples ----------------------------------------------------------------


def prompt_file_count() -> int:
    return len(yaml_files(eps_prompts_dir(load_config())))


def copy_samples() -> int:
    """Copy sample_eps (prompts, previews, metadata) into eps_dir. Returns the number of YAML files copied.

    Only allowed while <eps_dir>/prompts has no YAML files. Existing files and metadata values are never overwritten
    (only empty fields are filled in), and image links are rewritten to the configured previews folder.
    """
    config = load_config()
    prompts_dir = eps_prompts_dir(config)
    previews_dir = eps_previews_dir(config)
    if yaml_files(prompts_dir):
        raise SamplesNotCopiedError("The prompts folder already has YAML files; samples were not copied.")
    sample_files = yaml_files(SAMPLE_EPS_DIR / "prompts")
    if not sample_files:
        raise SamplesNotCopiedError("No bundled samples were found.")

    for source in sample_files:
        target = prompts_dir / source.relative_to(SAMPLE_EPS_DIR / "prompts")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    sample_previews = SAMPLE_EPS_DIR / "previews"
    if sample_previews.is_dir():
        previews_dir.mkdir(parents=True, exist_ok=True)
        for source in sample_previews.iterdir():
            target = previews_dir / source.name
            if source.is_file() and source.suffix.lower() in IMAGE_EXTENSIONS and not target.exists():
                shutil.copy2(source, target)

    sample_metadata = load_json(SAMPLE_EPS_DIR / "visual_eps_metadata.json", {})
    if isinstance(sample_metadata, dict) and sample_metadata:
        metadata = load_metadata()
        for item_id, entry in sample_metadata.items():
            if not isinstance(entry, dict):
                continue
            entry = dict(entry)
            image = str(entry.get("image") or "").strip()
            if image:
                entry["image"] = stored_path(previews_dir / Path(image).name)
            current = metadata.get(item_id)
            if not isinstance(current, dict):
                metadata[item_id] = entry
                continue
            # Keep what the user already set; only fill in the empty fields.
            for key, value in entry.items():
                if not current.get(key):
                    current[key] = value
        save_metadata(metadata)

    log(f"copied {len(sample_files)} sample EPS file(s) to {prompts_dir}")
    return len(sample_files)


# --- Cards ------------------------------------------------------------------


def merge_metadata(item: dict[str, str], metadata: dict[str, Any]) -> dict[str, Any]:
    meta = metadata.get(item["id"], {})
    if not isinstance(meta, dict):
        meta = {}
    merged = dict(item)
    merged["display_name_override"] = meta.get("display_name_override") or ""
    merged["display_name_effective"] = meta.get("display_name_override") or item["display_name"]
    merged["prepend_prompt"] = meta.get("prepend_prompt") or ""
    merged["append_prompt"] = meta.get("append_prompt") or ""
    merged["append_negative"] = meta.get("append_negative") or ""
    merged["tags"] = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    merged["memo"] = meta.get("memo") or ""
    merged["image"] = meta.get("image") or ""
    return merged


def load_visual_eps_cards() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = load_config()
    metadata = load_metadata()
    failed_files: list[Path] = []
    raw_items = load_eps_items(config, failed_files)
    cleanup_unused_metadata(raw_items, metadata, config, failed_files)
    cleanup_unused_previews(raw_items, metadata, config, failed_files)
    return [merge_metadata(item, metadata) for item in raw_items], config


def visual_eps_item_map() -> dict[str, dict[str, Any]]:
    items, _ = load_visual_eps_cards()
    return {str(item["id"]): item for item in items}


def find_item_by_location(items: dict[str, dict[str, Any]], source_path: str, locator: YamlLocator) -> dict[str, Any] | None:
    for item in items.values():
        if item.get("source_path") == source_path and item.get("yaml_locator") == locator:
            return item
    return None


def get_item(item_id: str) -> dict[str, Any]:
    item = visual_eps_item_map().get(item_id)
    if not item:
        raise ItemNotFoundError("Item not found")
    return item


def save_item(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Apply a Prompt edit request. Returns (item id after the save, its saved metadata entry)."""
    item_id = str(payload.get("id") or "")
    item = get_item(item_id)
    metadata = load_metadata()

    new_prompt = payload.get("prompt")
    if isinstance(new_prompt, str):
        new_prompt = new_prompt.replace("\r\n", "\n")
        if new_prompt != item["prompt"]:
            if not new_prompt.strip():
                raise InvalidEditError("The EPS prompt cannot be empty.")
            update_yaml_prompt(item, new_prompt)
            # List-style entries use the prompt in their id, so carry the metadata over to the new id.
            updated = find_item_by_location(visual_eps_item_map(), item["source_path"], item["yaml_locator"])
            if updated:
                if updated["id"] != item_id and item_id in metadata:
                    metadata[updated["id"]] = metadata.pop(item_id)
                item, item_id = updated, updated["id"]

    existing = metadata.get(item_id, {})
    old_image = str(existing.get("image") or "") if isinstance(existing, dict) else ""
    entry = metadata_entry_for_save(payload, existing)

    data_url = str(payload.get("image_data_url") or "")
    if data_url:
        entry["image"] = save_image_data_url(data_url, str(payload.get("image_name") or ""), item)
    if payload.get("clear_image"):
        entry["image"] = ""

    if entry:
        metadata[item_id] = entry
    elif item_id in metadata:
        del metadata[item_id]
    save_metadata(metadata)
    if old_image and old_image != str(metadata.get(item_id, {}).get("image") or ""):
        delete_preview_if_unused(old_image, metadata, load_config())
    return item_id, metadata.get(item_id, {})


def duplicate_item(item_id: str) -> str:
    """Copy a card: its YAML entry (next to the original) and its metadata. Returns the new item id.

    The copy shares the original's preview image; replacing it on either card keeps the other's image.
    """
    item = get_item(item_id)
    new_locator = duplicate_yaml_entry(item)
    created = find_item_by_location(visual_eps_item_map(), item["source_path"], new_locator)
    if not created:
        raise RuntimeError("The copy was written but could not be found. Reload Visual EPS.")

    metadata = load_metadata()
    entry = metadata.get(item_id)
    if isinstance(entry, dict) and entry:
        entry = json.loads(json.dumps(entry))
        if entry.get("display_name_override"):
            entry["display_name_override"] = f"{entry['display_name_override']} (copy)"
        metadata[created["id"]] = entry
        save_metadata(metadata)
    return str(created["id"])


def delete_item(item_id: str) -> None:
    """Delete a card: its YAML entry, its metadata, and its preview image when no other card uses it."""
    item = get_item(item_id)
    delete_yaml_entry(item)
    metadata = load_metadata()
    entry = metadata.pop(item_id, None)
    if entry is None:
        return
    save_metadata(metadata)
    image = str(entry.get("image") or "") if isinstance(entry, dict) else ""
    if image:
        delete_preview_if_unused(image, metadata, load_config())
