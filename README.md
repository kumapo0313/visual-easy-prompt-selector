# Visual Easy Prompt Selector

Visual Easy Prompt Selector is an extension for Stable Diffusion WebUI, Forge, and reForge. It displays Easy Prompt Selector YAML entries as searchable visual cards in the Extra Networks panel.

The extension reads Easy Prompt Selector files in read-only mode. It does not edit your original YAML files.

## Introduction

dr1610さん開発の "Visual Easy Prompt Selector" の個人的なフォークバージョンです。
素晴らしい拡張機能を公開してくださった dr1610さんに感謝申し上げます。

## What It Does

- Adds a `Visual EPS` tab to Extra Networks.
- Reads `.yml` and `.yaml` files from Easy Prompt Selector folders.
- Converts nested YAML entries into searchable prompt cards.
- Inserts the selected prompt into the active prompt box.
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

By default, Visual EPS loads YAML files from the `eps` folder inside this extension.

To use another folder, edit `config.json`:

```json
{
  "eps_path": "../sdweb-easy-prompt-selector/tags"
}
```

`eps_path` takes a single folder. All `.yml` / `.yaml` files in it, including subfolders, are loaded. Relative paths are resolved from the Visual EPS extension folder.

The older multi-folder `eps_paths` / `esp_paths` list is still read for compatibility, but only its first entry is used.

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

You can map prompt text to image filenames with `image_mapping.json`:

```json
{
  "smile": "smile_example.png",
  "long hair": "long_hair_example.png"
}
```

Recommended structure:

```text
previews/imported/
  image_mapping.json
  smile_example.png
  long_hair_example.png
```

If a prompt has no preview image, Visual EPS will show a normal card without a custom preview.

When a prompt is removed from the Easy Prompt Selector YAML files, Visual EPS also removes the matching entry from `image_mapping.json`. If that mapping pointed to a preview image that is not used by any remaining prompt or metadata entry, the image is deleted.

This keeps deleted EPS folders from leaving unused Visual EPS images behind. The files are permanently deleted without a backup, so disable this behavior if you want to keep them.

To disable this behavior, set this in `config.json`:

```json
{
  "auto_remove_orphaned_mapped_previews": false
}
```

### WebP preview resize tool

A helper tool is included at:

```text
tools/resize_visual_eps_previews.bat
```

Use it when your `previews/` folder contains many large PNG/JPG images. The tool can:

- Convert preview images to WebP thumbnails.
- Limit the number of files converted in one run.
- Skip small files below a chosen KB threshold.
- Back up original images before conversion.
- Update `image_mapping.json`, Visual EPS metadata, and YAML image references from PNG/JPG to WebP.

This is optional. Visual EPS also works without preview images.


## Performance Notes

Visual EPS can become heavy if many high-resolution reference images are kept in `previews/` and rendered through Extra Networks.

This release keeps the visual workflow while reducing the amount of work done in the browser:

- Preview images are lazy-loaded instead of forcing every card image to load immediately.
- Visual EPS search, tag, image, and source/folder filters run entirely in the Visual EPS toolbar, independent of the native Extra Networks search, so they combine across all EPS files.
- Repeated background rebinding was removed to reduce unnecessary browser work.
- A helper tool is included to resize existing preview images to small WebP thumbnails.

The recommended preview size is around 128-256 px. Keep original large images outside the extension folder, or use the backup option in the tool before conversion.

## Files Written by This Extension

Visual EPS writes only inside its own extension folder:

- `config.json`
- `visual_esp_metadata.json`
- `eps/previews/`

It does not modify:

- Easy Prompt Selector YAML files
- model files
- LoRA files
- other extensions
- WebUI settings outside this extension

## Troubleshooting

### The tab only shows sample prompts

Check `config.json`. If `eps_path` points to `sample_eps`, change it to your Easy Prompt Selector folder.

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


