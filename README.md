# Comic Tagger v0.1

**Comic Tagger** is a CLI tool to manage your comic book collection.  
It supports converting PDF and CBR files to CBZ format, tagging comics with detailed ComicInfo.xml metadata (from local JSON files or future online sources like Comic Vine), checking and erasing tags inside CBZ archives.

---

## Features

- **Convert** PDF and CBR files to CBZ (widely supported comic archive format).  
- **Tag** CBZ archives with detailed ComicInfo.xml metadata.  
- Supports both **single-issue** and **multi-issue series** tagging via customizable JSON metadata files.  
- **Check tags** inside CBZ files without unpacking.  
- **Erase tags** (ComicInfo.xml) from CBZ archives safely with backups.  
- Planned: integration with **Comic Vine API** for automatic metadata fetching.

---

## Requirements

### Python

- Python 3.6 or newer  
- Python libraries (install using `pip install -r requirements.txt`):
  - `pdf2image`
  - `Pillow`

### System tools

- `unar` - required to extract CBR (RAR) files  
- `zip` - required to create CBZ (ZIP) archives

#### On macOS (Homebrew):

```bash
brew install unar zip
```

#### On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install unar zip
```

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/comic-tagger.git
cd comic-tagger
```

2. Create and activate a Python virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install required Python libraries:

```bash
pip install -r requirements.txt
```

---

## Usage

### Help

```bash
python3 comic-tagger.py -h
```

### Convert PDF and/or CBR files to CBZ

- Convert a single file:

```bash
python3 comic-tagger.py -x file.pdf
```

- Convert multiple files:

```bash
python3 comic-tagger.py -x file1.pdf file2.cbr
```

- Convert all PDF and CBR files in a directory:

```bash
python3 comic-tagger.py -x -d /path/to/folder
```

### Check tags in CBZ files

- Check tags of a single file:

```bash
python3 comic-tagger.py -c file.cbz
```

- Check tags in all CBZ files in a directory:

```bash
python3 comic-tagger.py -c -d /path/to/folder
```

### Erase tags (ComicInfo.xml) from CBZ files

```bash
python3 comic-tagger.py -e -d /path/to/folder
```

---

### Tagging comics

- Tag a single file (requires JSON metadata file):

```bash
python3 comic-tagger.py -t single.json -s "file.cbz"
```

- Tag multiple issues in a directory (multi-issue series):

```bash
python3 comic-tagger.py -t multi.json -d /path/to/cbz_folder
```

---

## JSON Metadata Format

Two main JSON schemas are supported:

- **single.json** - metadata for a single issue.  
- **multi.json** - metadata for a series with multiple issues including an `issues` dictionary keyed by issue number with issue-specific data.

Example fields include:

- `series`, `title`, `publisher`, `year`, `genre`, `writer`, `illustrator`  
- `issues` (for multi.json) holds issue-specific fields like `description`, `tags`, `web`, etc.

---

## Notes and Future Improvements

- Integration with the Comic Vine API for automatic metadata fetching.  
- Support for more archive formats.  
- Improved error handling and reporting.  
- A GUI frontend for easier management.

---

## Contact and License

Created by deWille – your best buddy for comic tagging.  
Questions, suggestions, or issues? Open GitHub issues or ping me on Twitter @dewillepl.

MIT License — feel free to fork and improve!

---

## Additional Info

To avoid errors with very large image files, the code uses:

```python
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # disable DecompressionBombWarning
```

```

---

**requirements.txt**  
```
pdf2image
Pillow
```
