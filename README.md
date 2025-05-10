# Comic-Tagger

[![Version](https://img.shields.io/badge/version-v0.5-blue.svg)](#)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

**comic-tagger** is a command-line tool for fetching comic metadata from ComicVine, tagging CBZ files with `ComicInfo.xml`, inspecting and removing tags, and converting between comic archive formats.

---

## 📦 Features

### 🔍 Search ComicVine
- Search volumes by series name, title, author, year, publisher, or number of issues.
- Retrieve volume or issue details using ComicVine volume/issue IDs.
- Output can be summarized or verbose.

### 🏷️ Tag CBZ Files
- Tag `.cbz` files using metadata from a ComicVine issue ID.
- Tag `.cbz` files using local JSON metadata.
- Choose to merge or overwrite existing `ComicInfo.xml`.

### 🧾 Inspect Metadata
- Display existing `ComicInfo.xml` data inside `.cbz` archives.

### ❌ Erase Metadata
- Remove `ComicInfo.xml` files from `.cbz` archives.

### 🔄 Convert Formats
- Convert `.cbr` (RAR), `.cb7` (7z), `.cbt` (TAR), and `.pdf` to `.cbz` (ZIP).
- Outputs are saved in a `converted/` subdirectory.

### 🖥️ User-Friendly CLI
- Clear, colorized terminal output.
- Clickable URLs where supported.
- Organized commands with usage help.

---

## ⚙️ Requirements

- **Python**: 3.8 or newer  
- **Dependencies**:
  - `requests`
  - `natsort`

Install via:

```bash
pip install -r requirements.txt
