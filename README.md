# Visual Easy Prompt Selector

Visual Easy Prompt Selector is an extension for Stable Diffusion WebUI, Forge, and reForge. It displays Easy Prompt Selector YAML entries as searchable visual cards in the Extra Networks panel.

The prompt of a card can be edited from `Prompt edit`. The change is written back to the YAML file under `<eps_dir>/prompts`, keeping its comments and block styles (`|-`). Everything else you edit (display name, tags, notes, prompt additions, preview images) is stored in this extension folder.

## Introduction

dr1610さん開発の "Visual Easy Prompt Selector" の個人的なフォークバージョンです。
素晴らしい拡張機能を公開してくださった dr1610さんに感謝申し上げます。

## What It Does

- Adds a `Visual EPS` tab to Extra Networks.
- Reads `.yml` and `.yaml` files from Easy Prompt Selector folders.
- Converts nested YAML entries into searchable prompt cards.
- Inserts the selected prompt into the active prompt box.
- Edits a card's prompt and saves it back to its YAML file (requires `ruamel.yaml`, installed automatically by `install.py`).
- Supports text search, category filtering, tag filtering, AND/OR search, and image/no-image filtering.
- Supports optional preview images.
- Stores local display names, tags, notes, prompt additions, and preview-image links in this extension folder.
- Automatically deletes mapped preview images for deleted EPS prompts.

## Installation

### Recommended: install from Git URL

Use this method if you want WebUI's extension updater to work.

1. Open WebUI.
2. Go to `Extensions` > `Install from URL`.
3. Paste this URL:

```text
https://github.com/kumapo0313/visual-easy-prompt-selector
```

4. Click install.
5. Click `Apply and quit`.
6. Restart WebUI.

After this, future updates can be installed from:

```text
Extensions > Installed > Check for updates > Apply and quit
```

### ZIP/manual install

Manual install also works, but WebUI's update button will not update the extension automatically.

1. Download the ZIP or copy the folder.
2. Put it here:

```text
stable-diffusion-webui/extensions/visual-easy-prompt-selector
```

3. Restart WebUI.

If you installed an older ZIP test version, delete the old `visual-easy-prompt-selector` folder before installing the new one.

## Updating

### If installed from Git URL

1. Open `Extensions` > `Installed`.
2. Click `Check for updates`.
3. Click `Apply and quit`.
4. Restart WebUI.
5. Reload the browser page once.

### If installed from ZIP

1. Stop WebUI.
2. Delete the old `extensions/visual-easy-prompt-selector` folder.
3. Install the new version.
4. Restart WebUI.
5. Reload the browser page once.

## reForge Note

On reForge, after updating or on the first launch, Extra Networks may occasionally appear blank before the browser page is refreshed.

If `Checkpoint`, `LoRA`, or `Visual EPS` appears blank:

1. Reload the browser page.
2. If it is still blank, press `Ctrl + F5`.
3. If needed, restart WebUI once more.

`v0.1-test2` reworks the Visual EPS tree rendering so Visual EPS tree errors should not affect other Extra Networks pages.

## First Run

Visual EPS keeps its data in the `eps_dir` folder (default: `eps` inside this extension):

```text
eps/
  prompts/                    <- Easy Prompt Selector YAML files
  previews/                   <- images uploaded from Prompt edit
  visual_eps_metadata.json    <- display names, tags, notes, image links
```

Put your Easy Prompt Selector YAML files in `prompts/`. All `.yml` / `.yaml` files in it, including subfolders, are loaded.

To move the whole folder, edit `config.json`:

```json
{
  "eps_dir": "eps"
}
```

- `eps_dir` is relative to the Visual EPS extension folder, or an absolute path. The `prompts/`, `previews/` and `visual_eps_metadata.json` names inside it are fixed.
- After changing `eps_dir`, move the existing folder contents yourself and restart WebUI.

## Load Timing

Visual EPS does not need to scan a large prompt library during WebUI startup. The default mode is:

```json
{
  "load_mode": "on_tab_open"
}
```

Available modes:

- `on_tab_open`: load the library the first time a Visual EPS tab is opened. This is the default.
- `manual`: wait until the user presses `Load Visual EPS`.
- `startup`: preserve the original behavior and load with the other Extra Networks pages.

The `Load Visual EPS` / `Reload Visual EPS` button remains available in every mode, so the library can be refreshed at any time after WebUI has settled.

## Preview Images

Preview images are optional.

Place images under:

```text
previews/
```

If a prompt has no preview image, Visual EPS will show a normal card without a custom preview.

Images set from Prompt edit are saved in `<eps_dir>/previews/`. Visual EPS deletes images there that no current prompt uses:

- When an image is replaced or cleared in Prompt edit, the old image is deleted unless another prompt still uses it.
- When the library is loaded, images whose prompt was removed from the YAML files are deleted, and their metadata entries lose the image.

The cleanup is skipped when no prompts were loaded or a YAML file failed to load. Files are deleted permanently without a backup. Only images directly in `<eps_dir>/previews/` are touched; `previews/` in the extension folder is left alone.

Editing a list-style prompt directly in the YAML changes its ID, so its image is treated as unused. Edit prompts from Prompt edit to keep their images. To disable the cleanup, set this in `config.json`:

```json
{
  "auto_remove_unused_previews": false
}
```

### Unused metadata

When the library is loaded, Visual EPS deletes the entries in `visual_eps_metadata.json` (display names, tags, notes, prompt additions, image links) of prompts that were removed from the YAML files.

The same safety rules as the image cleanup apply: it is skipped when no prompts were loaded or a YAML file failed to load. Entries are deleted permanently without a backup, including those of list-style prompts whose ID changed because they were edited directly in the YAML, and those of YAML files that are temporarily moved out of `prompts/`. To keep these entries, set this in `config.json`:

```json
{
  "auto_remove_unused_metadata": false
}
```

## Performance Notes

Visual EPS can become heavy if many high-resolution reference images are kept in `previews/` and rendered through Extra Networks.

This release keeps the visual workflow while reducing the amount of work done in the browser:

- Preview images are lazy-loaded instead of forcing every card image to load immediately.
- Visual EPS search, tag, image, and source/folder filters run entirely in the Visual EPS toolbar, independent of the native Extra Networks search, so they combine across all EPS files.
- Repeated background rebinding was removed to reduce unnecessary browser work.

The recommended preview size is around 256-800 px.

`preview_max_size` in `config.json` (default `800`) sets the longest side in pixels of images uploaded from `Prompt edit`:

```json
{
  "preview_max_size": 800
}
```

## Files Written by This Extension

Visual EPS writes these files:

- `config.json`
- `<eps_dir>/visual_eps_metadata.json`
- `<eps_dir>/previews/`
- YAML files under `<eps_dir>/prompts/`, only when you edit a card's prompt

It does not modify:

- model files
- LoRA files
- other extensions
- WebUI settings outside this extension

## Troubleshooting

### The tab shows no prompts

Put your Easy Prompt Selector YAML files in `<eps_dir>/prompts/` (default: `eps/prompts/`). To try the bundled samples, copy the files from `sample_eps/` there.

You can also delete `config.json` and restart WebUI to let Visual EPS regenerate it.

### Checkpoint/LoRA/Visual EPS is blank after launch

Reload the browser page once. If needed, press `Ctrl + F5`.

### WebUI's update button does not update the extension

This usually means the extension was installed manually from ZIP. Install it from the GitHub URL if you want WebUI's updater to work.

### JavaScript or card UI looks old after updating

Restart WebUI and hard-refresh the browser with `Ctrl + F5`.

## Credits

- **[visual-easy-prompt-selector](https://github.com/dr1610/visual-easy-prompt-selector)**  dr1610 — original project

## License

MIT License. See `LICENSE` for details.


