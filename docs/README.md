# Plover documentation

| File | What it is |
|---|---|
| **[USER_GUIDE.md](USER_GUIDE.md)** | The complete user guide, readable directly on GitHub |
| **[Plover-User-Guide.docx](Plover-User-Guide.docx)** | The same guide as an editable Word document (109 pages) |
| `chapters/` | The guide's source, one Markdown file per chapter |
| `images/` | Figures used by both versions — all generated, none hand-drawn |
| `make_figures.py` | Regenerates every figure |
| `build_guide.js` | Builds the `.docx` from `chapters/` + `images/` |

## Rebuilding the guide

The guide is generated, not hand-maintained. After changing the plugin, update the
chapter text in `chapters/`, then regenerate.

### 1. Regenerate the figures

Every map figure is produced by calling the plugin's own routing pipeline and its own
styling helpers, so the pictures always match what the plugin actually draws. The dialog
screenshots are real captures of the real widgets.

Run with a QGIS Python, from the repository root:

```bash
"C:/Program Files/QGIS 4.0.1/bin/python-qgis.bat" docs/make_figures.py
```

Do **not** set `QT_QPA_PLATFORM=offscreen` for this — the offscreen platform renders text
as empty boxes. The script needs the native platform so fonts load.

### 2. Rebuild the Word document

Requires Node and the `docx` package:

```bash
NODE_PATH="$(npm root -g)" node docs/build_guide.js
```

### 3. Rebuild the Markdown version

The Markdown guide is the same chapters stitched together with the figure placeholders
replaced by image tags. Regenerate it whenever the chapters change.

## How the source is organised

Each file in `chapters/` starts with a single `##` heading, which becomes a chapter. `###`
and `####` become sections and subsections. Two conventions matter:

- **Figures** are placeholders on their own line:

  ```
  [[FIGURE: map-route | Caption text goes here.]]
  ```

  The slug must match a PNG in `images/`. Figures are numbered automatically per chapter.

- **Everything factual must be checked against the source.** UI labels, parameter names,
  defaults, field names and error messages are quoted verbatim from the plugin. If you
  change a label in the code, search the chapters for the old text.

## Versioning

The document's version number is read from `tsp_route_generator/metadata.txt` at build
time, so bumping the plugin version is enough — do not hard-code it in the chapters.
