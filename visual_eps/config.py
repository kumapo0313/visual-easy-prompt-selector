"""config.json, its defaults, and the folders derived from it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import load_json, log, resolve_path


EXTENSION_NAME = "visual-easy-prompt-selector"
# The extension folder (this package sits directly inside it).
BASE_DIR = Path(__file__).absolute().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
# Files kept under the "eps_dir" folder of config.json.
EPS_PROMPTS_DIRNAME = "prompts"
METADATA_FILENAME = "visual_eps_metadata.json"
EPS_PREVIEWS_DIRNAME = "previews"
PREVIEWS_DIR = BASE_DIR / "previews"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

DEFAULT_CONFIG = {
    "eps_dir": "eps",
    "append_separator": ", ",
    "load_mode": "on_tab_open",
    "max_tree_leaf_items": 5000,
    # Delete images in <eps_dir>/previews that no current EPS prompt uses.
    "auto_remove_unused_previews": True,
    # Delete metadata entries (names, tags, notes, ...) whose prompt no current EPS YAML file has.
    "auto_remove_unused_metadata": True,
    # Longest side (px) of preview images uploaded from Prompt edit.
    "preview_max_size": 800,
}


def config_eps_dir(config: dict[str, Any]) -> Path:
    """Folder that holds the prompts, previews and metadata. Relative to the extension folder."""
    path_text = str(config.get("eps_dir") or "").strip() or DEFAULT_CONFIG["eps_dir"]
    return resolve_path(path_text, BASE_DIR)


def eps_prompts_dir(config: dict[str, Any]) -> Path:
    """Folder with the EPS YAML files."""
    return config_eps_dir(config) / EPS_PROMPTS_DIRNAME


def metadata_path(config: dict[str, Any]) -> Path:
    return config_eps_dir(config) / METADATA_FILENAME


def eps_previews_dir(config: dict[str, Any]) -> Path:
    return config_eps_dir(config) / EPS_PREVIEWS_DIRNAME


def preview_max_size(config: dict[str, Any]) -> int:
    try:
        size = int(config.get("preview_max_size", DEFAULT_CONFIG["preview_max_size"]))
    except (TypeError, ValueError):
        size = DEFAULT_CONFIG["preview_max_size"]
    return max(32, min(size, 4096))


def stored_path(path: Path) -> str:
    """Path saved in the metadata: relative to the extension folder when inside it, absolute otherwise."""
    try:
        return path.resolve().relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def ensure_files(config: dict[str, Any]) -> None:
    try:
        PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        eps_prompts_dir(config).mkdir(parents=True, exist_ok=True)
        eps_previews_dir(config).mkdir(parents=True, exist_ok=True)
        metadata = metadata_path(config)
        if not metadata.exists():
            metadata.parent.mkdir(parents=True, exist_ok=True)
            metadata.write_text("{}", encoding="utf-8", newline="\n")
    except Exception as exc:
        log(f"startup file generation failed: {exc}")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        try:
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        except Exception as exc:
            log(f"failed to create config.json: {exc}")
    config = dict(DEFAULT_CONFIG)
    loaded = load_json(CONFIG_PATH, {})
    if isinstance(loaded, dict):
        config.update(loaded)
    ensure_files(config)
    return config
