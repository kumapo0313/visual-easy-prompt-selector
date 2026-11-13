"""Forge Extra Networks page that renders Visual EPS cards, the tree view and the dirs view."""

from __future__ import annotations

import html
from typing import Any

from modules import shared, ui_extra_networks
from modules.ui_extra_networks import quote_js

from .config import BASE_DIR, PREVIEWS_DIR, eps_previews_dir, load_config
from .entities import compose_prompt, search_blob
from .services import load_visual_eps_cards
from .utils import log, natural_sort_key, normalize_key


PAGE_NAME = "visual eps"


class ExtraNetworksPageVisualEPS(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__("Visual EPS")
        # Visual EPS has its own "Prompt edit" button; hide Forge's standard "Edit metadata" button.
        self.btn_edit_item_tpl = ""
        self.allow_negative_prompt = True
        self._config = load_config()
        self._loaded = self.load_mode() == "startup"
        self._load_revision = 0

    def load_mode(self) -> str:
        mode = str(self._config.get("load_mode", "on_tab_open")).strip().lower()
        return mode if mode in {"manual", "on_tab_open", "startup"} else "on_tab_open"

    def request_load(self) -> None:
        self._config = load_config()
        self._loaded = True
        self._load_revision += 1

    def load_status(self) -> dict[str, Any]:
        self._config = load_config()
        mode = self.load_mode()
        if mode == "startup":
            self._loaded = True
        return {"loaded": self._loaded, "load_mode": mode, "revision": self._load_revision}

    def refresh(self):
        self._config = load_config()

    def create_item(self, item: dict[str, Any], index: int = 0) -> dict[str, Any]:
        separator = str(self._config.get("append_separator", ", "))
        prompt = compose_prompt(item, separator)
        image_rel = str(item.get("image", ""))
        image_path = BASE_DIR / image_rel if image_rel else None
        has_image = bool(image_path and image_path.exists())
        name = str(item.get("display_name_effective") or item.get("display_name") or item.get("id"))
        category = str(item.get("category_path") or "Root")
        source = str(item.get("source_file") or "")
        # Forge requires the key; no-image cards have no file, so leave it empty.
        filename = str(image_path) if has_image else ""
        preview = self.link_preview(str(image_path)) if has_image else None
        description_parts = [str(item.get("prompt") or ""), category, source]
        tags = [f"#{tag}" for tag in item.get("tags", [])]
        if tags:
            description_parts.append(" ".join(tags))

        return {
            "name": name,
            "veps_id": str(item.get("id", "")),
            "veps_category": category,
            "veps_source": source,
            "veps_tags": ",".join(str(tag) for tag in item.get("tags", [])),
            "veps_has_image": "1" if has_image else "0",
            "filename": filename,
            "shorthash": "",
            "preview": preview,
            "description": "\n".join(part for part in description_parts if part),
            "search_terms": [search_blob(item), category, source],
            "prompt": quote_js(prompt),
            "negative_prompt": quote_js(str(item.get("append_negative") or "").strip()),
            "local_preview": str(image_path if has_image else PREVIEWS_DIR / f"{normalize_key(name) or 'visual_eps'}.preview.{shared.opts.samples_format}"),
            "sort_keys": {
                "default": index,
                "name": name.lower(),
                "path": str(item.get("raw_path", "")).lower(),
                "date_created": 0,
                "date_modified": 0,
            },
        }

    @staticmethod
    def card_onclick(tabname: str, item: dict) -> str:
        """Card click handler: vepsCardClicked() in javascript/visual_easy_prompt_selector.js.

        Forge's default cardClicked() puts the prompt into whichever prompt box had focus last
        when allow_negative_prompt is True, so Visual EPS inserts the prompts itself.
        "prompt" and "negative_prompt" are already JS string literals (quote_js).
        """
        negative = item.get("negative_prompt") or '""'
        # Forge escapes only the onclick it builds itself, so escape this one for the HTML attribute.
        return html.escape(f"vepsCardClicked({quote_js(tabname)}, {item['prompt']}, {negative});")

    def create_item_html(self, tabname: str, item: dict, template=None):
        item["onclick"] = self.card_onclick(tabname, item)
        rendered = super().create_item_html(tabname, item, template)
        if not isinstance(rendered, str):
            return rendered
        attrs = (
            f'data-veps-id="{html.escape(item.get("veps_id", ""), quote=True)}" '
            f'data-veps-category="{html.escape(item.get("veps_category", ""), quote=True)}" '
            f'data-veps-source="{html.escape(item.get("veps_source", ""), quote=True)}" '
            f'data-veps-tags="{html.escape(item.get("veps_tags", ""), quote=True)}" '
            f'data-veps-has-image="{html.escape(item.get("veps_has_image", "0"), quote=True)}"'
        )
        rendered = rendered.replace('<div class="card"', f'<div class="card veps-extra-card" {attrs}', 1)
        veps_id = html.escape(str(item.get("veps_id", "")), quote=True)
        buttons = (
            '<button type="button" class="veps-card-tool veps-preview-button" title="Preview">View</button>'
            f'<button type="button" class="veps-card-tool veps-edit-button" data-veps-id="{veps_id}" title="Edit insert prompt and Visual EPS metadata">Prompt edit</button>'
            f'<button type="button" class="veps-card-tool veps-duplicate-button" data-veps-id="{veps_id}" title="Duplicate this card (adds a copy of its YAML entry and settings)">Copy</button>'
            f'<button type="button" class="veps-card-tool veps-delete-button" data-veps-id="{veps_id}" title="Delete this card (removes its entry from the YAML file)">Delete</button>'
        )
        rendered = rendered.replace('<div class="button-row">', f'<div class="button-row">{buttons}', 1)
        return rendered

    def create_tree_view_html(self, tabname: str) -> str:
        try:
            max_tree_leaf_items = int(self._config.get("max_tree_leaf_items", 5000))
        except (TypeError, ValueError):
            max_tree_leaf_items = 5000
        include_leaf_items = max_tree_leaf_items < 0 or len(self.items) <= max_tree_leaf_items

        def tree_button(
            *,
            label: str,
            data_path: str,
            subclass: str,
            search_terms: str = "",
            onclick_extra: str = "",
            data_hash: str = "",
            action_trailing: str = "",
            leading: str = "",
        ) -> str:
            return self.btn_tree_tpl.format(
                **{
                    "search_terms": search_terms,
                    "subclass": subclass,
                    "tabname": tabname,
                    "extra_networks_tabname": self.extra_networks_tabname,
                    "onclick_extra": onclick_extra,
                    "data_path": html.escape(data_path, quote=True),
                    "data_hash": html.escape(data_hash, quote=True),
                    "action_list_item_action_leading": "<i class='tree-list-item-action-chevron'></i>",
                    "action_list_item_visual_leading": leading,
                    "action_list_item_label": html.escape(label),
                    "action_list_item_visual_trailing": "",
                    "action_list_item_action_trailing": action_trailing,
                }
            )

        def file_item(item: dict[str, Any]) -> str:
            item["onclick"] = self.card_onclick(tabname, item)
            args = super(ExtraNetworksPageVisualEPS, self).create_item_html(tabname, item)
            if not isinstance(args, dict):
                return ""
            action_buttons = "".join(
                [
                    args.get("copy_path_button", ""),
                    args.get("metadata_button", ""),
                    args.get("edit_button", ""),
                ]
            )
            if action_buttons:
                action_buttons = f'<div class="button-row">{action_buttons}</div>'
            data_path = "/".join(
                part
                for part in [
                    str(item.get("veps_source") or "unknown.yml"),
                    str(item.get("veps_category") or "Root"),
                    str(item.get("name") or ""),
                ]
                if part
            )
            button = tree_button(
                label=str(item.get("name") or "Visual EPS"),
                data_path=data_path,
                subclass="tree-list-content-file veps-tree-file",
                search_terms=args.get("search_terms", ""),
                onclick_extra=args.get("card_clicked", ""),
                data_hash=str(item.get("shorthash") or ""),
                action_trailing=action_buttons,
                leading="",
            )
            attrs = (
                f'data-veps-id="{html.escape(str(item.get("veps_id", "")), quote=True)}" '
                f'data-veps-category="{html.escape(str(item.get("veps_category", "")), quote=True)}" '
                f'data-veps-source="{html.escape(str(item.get("veps_source", "")), quote=True)}" '
                f'data-veps-tags="{html.escape(str(item.get("veps_tags", "")), quote=True)}" '
                f'data-veps-has-image="{html.escape(str(item.get("veps_has_image", "0")), quote=True)}"'
            )
            return (
                "<li class='tree-list-item tree-list-item--subitem veps-extra-card' "
                f"data-tree-entry-type='file' {attrs}>{button}</li>"
            )

        def new_node() -> dict[str, Any]:
            return {"dirs": {}, "items": []}

        def add_to_tree(root: dict[str, Any], item: dict[str, Any]) -> None:
            source = str(item.get("veps_source") or "unknown.yml")
            category = str(item.get("veps_category") or "Root")
            parts = [source] + [part for part in category.replace("\\", "/").split("/") if part]
            node = root
            for part in parts:
                node = node["dirs"].setdefault(part, new_node())
            node["items"].append(item)

        def render_node(node: dict[str, Any], path_parts: list[str]) -> str:
            chunks: list[str] = []
            for name, child in sorted(node["dirs"].items(), key=lambda pair: natural_sort_key(pair[0])):
                child_path = "/".join(path_parts + [name])
                children_html = render_node(child, path_parts + [name])
                if not children_html and not child["items"]:
                    continue
                parent = tree_button(
                    label=name,
                    data_path=child_path,
                    subclass="tree-list-content-dir veps-tree-dir",
                    search_terms=html.escape(child_path),
                    leading="",
                )
                if children_html:
                    chunks.append(
                        "<li class='tree-list-item tree-list-item--has-subitem' data-tree-entry-type='dir'>"
                        f"{parent}<ul class='tree-list tree-list--subgroup' hidden>{children_html}</ul>"
                        "</li>"
                    )
                else:
                    chunks.append(
                        "<li class='tree-list-item tree-list-item--subitem' data-tree-entry-type='dir'>"
                        f"{parent}</li>"
                    )
            if include_leaf_items:
                for item in sorted(node["items"], key=lambda value: natural_sort_key(value.get("name") or "")):
                    chunks.append(file_item(item))
            return "".join(chunks)

        try:
            root = new_node()
            for item in self.items.values():
                add_to_tree(root, item)
            return (
                "<ul class='tree-list tree-list--tree veps-source-tree' "
                f"data-veps-revision='{self._load_revision}'>{render_node(root, [])}</ul>"
            )
        except Exception as exc:
            log(f"Extra Networks tree view failed: {exc}")
            return (
                "<ul class='tree-list tree-list--tree veps-source-tree' "
                f"data-veps-revision='{self._load_revision}'></ul>"
            )

    def create_dirs_view_html(self, tabname: str) -> str:
        sources = sorted({str(item.get("veps_source") or "unknown.yml") for item in self.items.values()}, key=natural_sort_key)
        revision_marker = f"<div class='veps-source-tree' data-veps-revision='{self._load_revision}' hidden></div>"
        # Filtered by the Visual EPS toolbar (data-veps-path), not Forge's native search box.
        buttons = "".join(
            f"""
            <button type='button' class='lg secondary gradio-button custom-button veps-source-button' data-veps-path='{html.escape(source, quote=True)}'>
            {html.escape(source)}
            </button>
            """
            for source in sources
        )
        return revision_marker + buttons

    def list_items(self):
        try:
            self._config = load_config()
            if self.load_mode() == "startup":
                self._loaded = True
            if not self._loaded:
                return
            items, _ = load_visual_eps_cards()
            for index, item in enumerate(items):
                yield self.create_item(item, index)
        except Exception as exc:
            log(f"Extra Networks list_items failed: {exc}")

    def allowed_directories_for_previews(self):
        # Uploaded card images live in <eps_dir>/previews, outside PREVIEWS_DIR, so Forge must be told to serve it too.
        # Forge reads this once at startup, so changing eps_dir needs a WebUI restart.
        return [str(PREVIEWS_DIR), str(eps_previews_dir(load_config()))]

    def read_user_metadata(self, item, use_cache=True):
        # Visual EPS keeps its metadata in visual_eps_metadata.json. Forge's sidecar <filename>.json
        # is keyed by the preview file, which several cards can share,
        # so its description would leak one card's prompt into other cards.
        item["user_metadata"] = {}
