
# comic-tagger v0.6

**A command-line tool for fetching comic metadata from ComicVine, tagging CBZ files with `ComicInfo.xml`, inspecting tags, managing metadata, and converting comic formats.**

`comic-tagger` helps you organize your digital comic collection by leveraging the ComicVine database and providing utilities to embed and manage metadata within `.cbz` files.

---

## ✨ Features

### 🔍 Search ComicVine (`search` command)

- **Volume Search**  
  Find comic series/volumes using filters:
  - `--title` / `-t`: Volume name or title
  - `--author` / `-a`: Creator name (broad search, best used with filters)
  - `--year` / `-y`: Start year
  - `--publisher` / `-p`: Publisher name
  - `--num-issues` / `-n`: Exact number of issues

- **Fetch Specific Metadata**
  - `--get-volume` / `-v`: Fetch volume details by ComicVine volume ID
  - `--get-issue` / `-i`: Fetch issue details by ComicVine issue ID
  - `--verbose` / `-V`: Detailed metadata output

- `--include-issues` / `-ii`: Optionally include issue lists in volume results (API-intensive)

All data is shown in a clean, colorized terminal output with clickable links.

---

### 🏷️ Metadata Management (`tag` command)

- **Tag from ComicVine**  
  Automatically tag a `.cbz` file with metadata from a ComicVine `--issue-id` / `-id`.

- **Tag from Local File**  
  Use metadata from a local JSON file with `--from-file` / `-f`.

- **Rename After Tagging**  
  Use `--rename` / `-r` to rename files to a standard format.

- **Inspect Tags**  
  Use `--check` / `-c` to display existing `ComicInfo.xml` metadata.

- **Erase Tags**  
  Use `--erase` / `-e` to remove `ComicInfo.xml`.

- **Overwrite Existing Tags**  
  Use `--overwrite-all` / `-o` to fully replace existing metadata.

---

### 🔄 Format Conversion (`convert` command)

- Convert `.cbr`, `.cb7`, `.cbt`, and `.pdf` files to `.cbz`
- Supports batch or individual file conversion
- Converted files saved in a `converted/` subdirectory

---

## 📦 Prerequisites

### Python (3.8+)

Install dependencies:

```bash
pip install -r requirements.txt
````

Make sure `requirements.txt` includes:

* `requests`
* `natsort`

### External Tools for `convert`

Install and ensure the following are in your system’s `PATH`:

| Format | Tool     | macOS                      | Linux                              | Windows                                         |
| ------ | -------- | -------------------------- | ---------------------------------- | ----------------------------------------------- |
| `.cbr` | `unrar`  | `brew install unrar`       | `sudo apt-get install unrar`       | [RARLab](https://www.rarlab.com/rar_add.htm)    |
| `.cb7` | `7z`     | `brew install p7zip`       | `sudo apt-get install p7zip-full`  | [7-Zip](https://www.7-zip.org/)                 |
| `.pdf` | `mutool` | `brew install mupdf-tools` | `sudo apt-get install mupdf-tools` | [MuPDF](https://mupdf.com/downloads/index.html) |

### ComicVine API Key

The API key is hardcoded in `config.py`. You can replace it with your own key from [ComicVine API](https://comicvine.gamespot.com/api/).
To customize the User-Agent, set the environment variable:

```bash
export CV_FETCHER_USER_AGENT="YourAppName"
```

---

## ⚙️ Installation

1. Install Python 3.8+
2. Place all script files in the same directory
3. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Install external tools (see above)
5. Make the script executable (optional):

   ```bash
   chmod +x comic-tagger.py
   ```

---

## 🚀 Usage

```bash
python3 comic-tagger.py [COMMAND] [OPTIONS...]
# or, if executable:
./comic-tagger.py [COMMAND] [OPTIONS...]
```

### 🔎 General Help

```bash
./comic-tagger.py -h
```

### 📘 Command Help

```bash
./comic-tagger.py search -h
./comic-tagger.py tag -h
./comic-tagger.py convert -h
```

---

## 📌 Examples

### Search

```bash
./comic-tagger.py search -t "Sandman" -p "Vertigo"
./comic-tagger.py search -v 1892 -ii
./comic-tagger.py search -i 23039 -V
./comic-tagger.py search -a "Neil Gaiman" -ii
```

### Tagging

```bash
./comic-tagger.py tag -id 12345 -r MyComic.cbz
./comic-tagger.py tag -f meta.json -o AnotherComic.cbz
./comic-tagger.py tag -c Existing.cbz
./comic-tagger.py tag -e ComicToClean.cbz
```

### Converting

```bash
./comic-tagger.py convert ~/Downloads/ComicsToConvert/
./comic-tagger.py convert my.pdf /path/to/another.cbr
```

---

## 🗂️ Project Structure

* `comic-tagger.py` – CLI entry point
* `config.py` – Global configuration
* `utils.py` – Terminal output styling, helpers
* `fetch_api.py` – ComicVine API handler
* `tagging.py` – Metadata read/write
* `inspect_files.py` – Reads/display existing tags
* `convert_files.py` – Format conversion logic

(See `ARCHITECTURE.md` for more details.)

---

## ⚠️ Known Limitations

* **Author Filtering**
  ComicVine's author filter is broad and may return unrelated results. For better precision, combine with other filters.

* **API Rate Limits**
  ComicVine enforces limits (e.g., 200 requests per type per hour). Use `--include-issues` and author-first searches cautiously.

* **Tag Coverage**
  Only common `ComicInfo.xml` fields are supported; not all ComicVine data maps cleanly.

---

## 🔮 Future Enhancements

* Interactive search selection
* API response caching
* Tag editing in-place
* GUI front-end

---

## 🤝 Contributing

This project is maintained for internal use and feedback. Contribution guidelines will be added if open development begins.

---

## 📄 License

To be determined. Consider using MIT, GPL, or another OSI-approved license.


