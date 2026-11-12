"""Visual Easy Prompt Selector (Visual EPS) internals.

Forge loads every file in scripts/ as a WebUI script, so the modules live in this package instead.
Forge puts the extension folder on sys.path, which makes "visual_eps" importable from scripts/.

Layers (each module only imports the ones above it):
    utils               generic helpers (logging, JSON, text keys, YAML locators)
    config              config.json, defaults and the folders derived from it
    entities            shape of EPS items and metadata entries, and pure functions on them
    services            domain logic: loading EPS YAML, metadata, previews, saving edits
    extra_networks_page Forge Extra Networks page that renders the cards
"""
