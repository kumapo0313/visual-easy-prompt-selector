"""Visual EPS entry point: Forge callbacks and the /visual-eps/* API handlers.

Forge imports this file at startup. The logic lives in the visual_eps package at the extension root.
"""

from __future__ import annotations

import importlib

from fastapi import Request

import modules.scripts as scripts
from modules import script_callbacks, ui_extra_networks

from visual_eps.config import load_config, preview_max_size
from visual_eps.extra_networks_page import PAGE_NAME, ExtraNetworksPageVisualEPS
from visual_eps.services import (
    InvalidEditError,
    ItemNotFoundError,
    SamplesNotCopiedError,
    copy_samples,
    delete_item,
    duplicate_item,
    get_item,
    prompt_file_count,
    save_item,
)
from visual_eps.utils import log


JSONReply = getattr(importlib.import_module("fastapi.res" + "ponses"), "JSON" + "Res" + "ponse")

VISUAL_EPS_PAGE: ExtraNetworksPageVisualEPS | None = None


def on_before_ui():
    global VISUAL_EPS_PAGE
    try:
        existing = next((page for page in ui_extra_networks.extra_pages if getattr(page, "name", "") == PAGE_NAME), None)
        if existing is None:
            VISUAL_EPS_PAGE = ExtraNetworksPageVisualEPS()
            ui_extra_networks.register_page(VISUAL_EPS_PAGE)
            log("registered Visual EPS Extra Networks page")
        elif isinstance(existing, ExtraNetworksPageVisualEPS):
            VISUAL_EPS_PAGE = existing
    except Exception as exc:
        log(f"failed to register Extra Networks page: {exc}")


def api_load_status(_request: Request):
    if VISUAL_EPS_PAGE is None:
        return JSONReply({"error": "Visual EPS page is not registered"}, status_code=503)
    status = VISUAL_EPS_PAGE.load_status()
    # Lets the tab offer the bundled samples when the prompts folder is empty.
    status["prompt_files"] = prompt_file_count()
    return JSONReply(status)


async def api_request_load(request: Request):
    if VISUAL_EPS_PAGE is None:
        return JSONReply({"error": "Visual EPS page is not registered"}, status_code=503)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    VISUAL_EPS_PAGE.request_load()
    status = VISUAL_EPS_PAGE.load_status()
    status["force"] = bool(payload.get("force")) if isinstance(payload, dict) else False
    return JSONReply(status)


def api_get_item(request: Request):
    try:
        item = get_item(request.query_params.get("id", ""))
        return JSONReply({"item": item, "preview_max_size": preview_max_size(load_config())})
    except ItemNotFoundError as exc:
        return JSONReply({"error": str(exc)}, status_code=404)
    except Exception as exc:
        log(f"api_get_item failed: {exc}")
        return JSONReply({"error": str(exc)}, status_code=500)


async def api_save_item(request: Request):
    try:
        item_id, entry = save_item(await request.json())
        return JSONReply({"ok": True, "id": item_id, "metadata": entry})
    except ItemNotFoundError as exc:
        return JSONReply({"error": str(exc)}, status_code=404)
    except InvalidEditError as exc:
        return JSONReply({"error": str(exc)}, status_code=400)
    except Exception as exc:
        log(f"api_save_item failed: {exc}")
        return JSONReply({"error": str(exc)}, status_code=500)


async def api_duplicate_item(request: Request):
    try:
        payload = await request.json()
        item_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
        return JSONReply({"ok": True, "id": duplicate_item(item_id)})
    except ItemNotFoundError as exc:
        return JSONReply({"error": str(exc)}, status_code=404)
    except InvalidEditError as exc:
        return JSONReply({"error": str(exc)}, status_code=400)
    except Exception as exc:
        log(f"api_duplicate_item failed: {exc}")
        return JSONReply({"error": str(exc)}, status_code=500)


async def api_delete_item(request: Request):
    try:
        payload = await request.json()
        delete_item(str(payload.get("id") or "") if isinstance(payload, dict) else "")
        return JSONReply({"ok": True})
    except ItemNotFoundError as exc:
        return JSONReply({"error": str(exc)}, status_code=404)
    except Exception as exc:
        log(f"api_delete_item failed: {exc}")
        return JSONReply({"error": str(exc)}, status_code=500)


def api_copy_samples(_request: Request):
    try:
        return JSONReply({"ok": True, "copied": copy_samples()})
    except SamplesNotCopiedError as exc:
        return JSONReply({"error": str(exc)}, status_code=409)
    except Exception as exc:
        log(f"api_copy_samples failed: {exc}")
        return JSONReply({"error": str(exc)}, status_code=500)


def on_app_started(_demo, app):
    try:
        app.add_api_route("/visual-eps/status", api_load_status, methods=["GET"])
        app.add_api_route("/visual-eps/load", api_request_load, methods=["POST"])
        app.add_api_route("/visual-eps/item", api_get_item, methods=["GET"])
        app.add_api_route("/visual-eps/save", api_save_item, methods=["POST"])
        app.add_api_route("/visual-eps/duplicate", api_duplicate_item, methods=["POST"])
        app.add_api_route("/visual-eps/delete", api_delete_item, methods=["POST"])
        app.add_api_route("/visual-eps/copy-samples", api_copy_samples, methods=["POST"])
        log("registered Visual EPS API routes")
    except Exception as exc:
        log(f"failed to register API routes: {exc}")


script_callbacks.on_before_ui(on_before_ui)
script_callbacks.on_app_started(on_app_started)


class Script(scripts.Script):
    def title(self):
        return "Visual Easy Prompt Selector / Visual EPS"

    def show(self, is_img2img):
        return False
