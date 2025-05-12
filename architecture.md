# comic-tagger Application Architecture (v0.6)

## 1. Overall Project Purpose

**`comic-tagger`** is a command-line interface (CLI) application designed for comic book enthusiasts to manage their digital comic collections. Its primary functions include:

*   **Fetching Metadata:** Interacting with the ComicVine API to search for and retrieve detailed information about comic book volumes (series/trade paperbacks), individual issues, creators, characters, etc.
*   **Tagging Files:** Writing industry-standard `ComicInfo.xml` metadata into `.cbz` comic archive files. This metadata can be sourced from ComicVine or a local JSON file.
*   **Inspecting Tags:** Reading and displaying existing `ComicInfo.xml` metadata from `.cbz` files.
*   **Managing Tags:** Erasing existing `ComicInfo.xml` metadata from `.cbz` files.
*   **Renaming Files:** Automatically renaming `.cbz` files based on a standardized format derived from their embedded or newly applied metadata.
*   **Converting Formats:** Converting various comic book archive formats (e.g., `.cbr`, `.cb7`, `.cbt`) and `.pdf` files into the widely compatible `.cbz` (ZIP) format.

The application aims to provide a powerful, scriptable toolset for organizing and enriching digital comic libraries, with a user-friendly terminal interface that includes colorized output and clickable links.

## 2. Python Environment

*   **Python Version:** Developed and tested primarily with Python 3.8+. Compatibility with slightly older or newer 3.x versions is likely but not extensively tested.
*   **Required Python Packages:**
    *   **`requests`**: Used for making HTTP GET requests to the ComicVine API. Essential for all data fetching operations.
    *   **`natsort`**: Used for "natural sorting" of strings. This is critical for:
        *   Correctly ordering comic book issue numbers (e.g., "1", "2", "10" instead of "1", "10", "2").
        *   Sorting image filenames within archives before creating a `.cbz` file during conversion, ensuring pages are in the correct sequence.
    These dependencies are listed in `requirements.txt` and can be installed using `pip install -r requirements.txt`.

## 3. File-by-File Breakdown

The application is structured into several Python modules, each with a distinct responsibility:

### 3.1. `comic-tagger.py` (Main Entry Point)

*   **Purpose:** This script serves as the primary entry point for the application when run from the command line. It is responsible for parsing command-line arguments, setting up the overall command structure, and dispatching tasks to the appropriate handler functions located in other modules.
*   **Key Functions/Classes:**
    *   `main()`: Initializes `argparse`, defines all top-level commands (`search`, `tag`, `convert`) and their respective sub-arguments and flags. Parses the user's input and calls the designated handler function associated with the chosen command.
    *   `argparse.ArgumentParser` and `subparsers`: Used extensively to define the CLI structure.
*   **Interactions:**
    *   Imports handler functions (e.g., `handle_fetch_comicvine`, `handle_tagging_dispatch`, `handle_convert`) from their respective modules (`fetch_api.py`, `tagging.py`, `convert_files.py`).
    *   Imports `Style` from `utils.py` for consistent error message styling at startup (e.g., for missing `natsort`).
    *   May interact with `config.py` to set or read global configurations like `CV_USER_AGENT` (though `config.py` itself primarily handles the environment variable override).

### 3.2. `config.py`

*   **Purpose:** A centralized location for storing global configuration constants and settings for the application. This makes it easy to modify key parameters without searching through multiple code files.
*   **Key Constants:**
    *   `CV_API_KEY`: The API key required for ComicVine API access.
    *   `CV_BASE_URL`: The base URL for the ComicVine API.
    *   `CV_USER_AGENT`: The User-Agent string sent with API requests (reads `CV_FETCHER_USER_AGENT` environment variable).
    *   `CV_REQUEST_TIMEOUT`, `CV_RATE_LIMIT_WAIT_SECONDS`, `CV_MAX_RETRIES`: Parameters for API request behavior.
    *   `CV_VOLUME_PREFIX`, `CV_ISSUE_PREFIX`, etc.: Standard ID prefixes for various ComicVine resource types, used in constructing API URLs or fallback links.
*   **Interactions:**
    *   This module is imported by other modules (primarily `fetch_api.py`, but also potentially `tagging.py` if it directly constructs API URLs) that need access to these configuration values.
    *   It uses `os.environ.get` to allow overriding `CV_USER_AGENT` via an environment variable.

### 3.3. `utils.py`

*   **Purpose:** Contains shared, general-purpose utility functions and classes used across various modules of the application, primarily focused on terminal output styling and common data manipulations.
*   **Key Functions/Classes:**
    *   `Style` (class): Defines ANSI escape codes for text colors and styles (bold, underline).
    *   `print_error()`, `print_info()`, `print_success()`: Standardized functions for printing styled messages to the terminal (typically `stderr` for info/error, `stdout` for success).
    *   `strip_html()`: Removes HTML tags from strings (e.g., from ComicVine descriptions).
    *   `make_clickable_link()`: Generates terminal hyperlink escape sequences.
    *   `print_header_line()`: Prints a full-width, styled header line.
    *   `print_field()`: Formats and prints labeled data (e.g., "Title: Some Title").
    *   `print_multiline_text()`: Prints a label followed by text that is wrapped to fit the terminal width.
    *   `sanitize_filename()`: Cleans a string to make it suitable for use as a filename by removing/replacing invalid characters.
*   **Interactions:** This module is imported by almost all other modules (`comic-tagger.py`, `fetch_api.py`, `tagging.py`, `inspect_files.py`, `convert_files.py`) that produce terminal output or require string sanitization.

### 3.4. `fetch_api.py`

*   **Purpose:** Encapsulates all logic related to interacting with the ComicVine API. This includes constructing API requests, sending them, handling responses, and formatting the fetched data for display.
*   **Key Functions/Classes:**
    *   `make_comicvine_api_request()`: The core function for making GET requests to the ComicVine API. It handles adding the API key and format, managing retries for rate limiting, and basic error checking of the HTTP response and ComicVine's own status codes.
    *   `display_volume_search_results()`: Formats and prints a list of volume summaries.
    *   `display_volume_details()`: Formats and prints detailed information for a single volume, including its associated people and a list of its issues.
    *   `display_issue_details_summary()`: Formats and prints a concise summary for a single issue.
    *   `display_issue_details_verbose()`: Formats and prints comprehensive details for a single issue, including all credits (people, characters, teams, locations, concepts, objects, story arcs), aliases, deck, image URLs, associated images, and other available metadata.
    *   `handle_fetch_comicvine()`: The main handler function for the `search` command. It interprets the search arguments, decides which API endpoints to call (e.g., `/volumes/`, `/issues/`, `/people/`), orchestrates the API calls, and then invokes the appropriate display function. It implements the two-step search logic for author-centric queries and handles the `--include-issues` flag.
*   **Interactions:**
    *   Imports constants from `config.py` (API key, URLs, etc.).
    *   Imports styling and printing utilities from `utils.py`.
    *   Uses the `requests` library for HTTP calls.
    *   Uses `natsort` for sorting issues by number.
    *   Its `handle_fetch_comicvine` function is called by `comic-tagger.py`.
    *   Its `make_comicvine_api_request` function is also called by `tagging.py` when tagging from a ComicVine issue ID.

### 3.5. `tagging.py`

*   **Purpose:** Manages all operations related to `ComicInfo.xml` metadata within `.cbz` files. This includes fetching data for tagging, mapping it to the XML schema, writing the XML to archives, and erasing existing XML. It also handles the file renaming logic post-tagging.
*   **Key Functions/Classes:**
    *   `map_cv_to_comicinfo_dict()`: Translates the rich JSON data (typically for a single issue) fetched from ComicVine into a flat Python dictionary where keys correspond to `ComicInfo.xml` tag names. This function contains the detailed mapping logic.
    *   `create_comic_info_xml_element()`: Takes the metadata dictionary and builds an `xml.etree.ElementTree.Element` representing the `ComicInfo.xml` structure.
    *   `write_comic_info_to_cbz()`: Writes the generated `ComicInfo.xml` tree into a specified `.cbz` file. It handles merging with existing `ComicInfo.xml` (if not overwriting) and uses a safe temporary file mechanism to prevent CBZ corruption.
    *   `erase_comic_info_from_cbz()`: Removes an existing `ComicInfo.xml` file from a `.cbz` archive by rewriting the archive without it.
    *   `_generate_new_filename()`: Creates a standardized, sanitized filename string based on provided metadata (e.g., "Series V<Vol> #<Num> (Year) - Title.cbz").
    *   `_perform_actual_tagging_and_rename()`: Internal orchestrator for the tagging and optional renaming process.
    *   `handle_tagging_dispatch()`: The main handler function for the `tag` command. It interprets flags (`--issue-id`, `--from-file`, `--erase`, `--check`, `--rename`, `--overwrite-all`) and calls the appropriate internal functions.
*   **Interactions:**
    *   Imports `make_comicvine_api_request` from `fetch_api.py` to get data when tagging by `--issue-id`.
    *   Imports constants from `config.py`.
    *   Imports utilities from `utils.py` (styling, printing, `sanitize_filename`).
    *   Imports `handle_check` (as `perform_check_on_file`) from `inspect_files.py` when the `tag --check` action is invoked.
    *   Uses standard Python libraries: `os`, `json`, `xml.etree.ElementTree`, `datetime`, `zipfile`, `shutil`, `tempfile`, `sys`.
    *   Its `handle_tagging_dispatch` function is called by `comic-tagger.py`.

### 3.6. `inspect_files.py`

*   **Purpose:** Responsible for reading and displaying existing `ComicInfo.xml` metadata from local `.cbz` files. This functionality is invoked by the `tag --check` command.
*   **Key Functions/Classes:**
    *   `read_comic_info_from_archive()`: Opens a `.cbz` file, looks for `ComicInfo.xml`, parses it using `xml.etree.ElementTree`, and converts the XML structure into a Python dictionary. It attempts to identify and parse comma-separated list tags.
    *   `display_comic_info_details()`: Takes the dictionary representation of `ComicInfo.xml` and formats it for user-friendly terminal display, mirroring the style and structure of the verbose issue display from `fetch_api.py`.
    *   `handle_check()`: The main handler function for the inspection logic. It processes input file/directory paths, calls `read_comic_info_from_archive()` for each found `.cbz` file, and then uses `display_comic_info_details()` to show the results.
*   **Interactions:**
    *   Imports utilities from `utils.py` for output formatting.
    *   Uses standard Python libraries: `os`, `xml.etree.ElementTree`, `zipfile`.
    *   Its `handle_check` function is called by `handle_tagging_dispatch` in `tagging.py` when the `tag --check` action is chosen.

### 3.7. `convert_files.py`

*   **Purpose:** Contains all logic for converting various comic book archive formats and PDF files into the `.cbz` (ZIP) format.
*   **Key Functions/Classes:**
    *   `check_command_exists()`: A utility to verify if required external command-line tools (`unrar`, `7z`, `mutool`) are installed and in the system PATH.
    *   `create_cbz_from_images()`: Takes a directory of image files, sorts them naturally using `natsort`, and packages them into a new `.cbz` archive.
    *   `convert_cbr_to_cbz()`, `convert_cb7_to_cbz()`, `convert_cbt_to_cbz()`, `convert_pdf_to_cbz()`: Individual functions dedicated to converting a specific input format. They typically involve:
        *   Checking for necessary external tools.
        *   Extracting images from the source archive/PDF into a temporary directory (using `subprocess` to call external tools for CBR, CB7, PDF, or `tarfile` for CBT).
        *   Calling `create_cbz_from_images()` to create the final `.cbz`.
        *   Includes fallback logic (e.g., trying to treat a `.cbr` as a ZIP if `unrar` fails and reports it's not a RAR archive).
    *   `handle_convert()`: The main handler function for the `convert` command. It processes input file/directory paths, determines the output directory structure (creating a `converted` subfolder), and dispatches files to the appropriate `convert_XYZ_to_cbz` function based on their extension.
*   **Interactions:**
    *   Imports utilities from `utils.py`.
    *   Uses standard Python libraries: `os`, `shutil`, `subprocess`, `zipfile`, `tarfile`, `tempfile`.
    *   Uses the `natsort` library for sorting image filenames.
    *   Its `handle_convert` function is called by `comic-tagger.py`.

## 4. Execution Flow

1.  The user executes `python3 comic-tagger.py [COMMAND] [OPTIONS...]` from their terminal.
2.  **`comic-tagger.py` - `main()` function:**
    *   The `natsort` dependency is checked.
    *   `argparse.ArgumentParser` is initialized to define the overall application and its main commands (`search`, `tag`, `convert`).
    *   Subparsers are created for each main command, and their specific arguments and flags are defined.
    *   `parser.parse_args()` processes the command-line input provided by the user into an `args` namespace object.
    *   The `func` attribute of `parsed_args` (set by `set_defaults(func=HANDLER_FUNCTION)` for each subparser) is used to call the appropriate main handler function (e.g., `handle_fetch_comicvine(parsed_args)`, `handle_tagging_dispatch(parsed_args)`, or `handle_convert(parsed_args)`).
3.  **Handler Function Execution (e.g., `handle_fetch_comicvine(args)` in `fetch_api.py`):**
    *   The called handler function receives the `parsed_args` object.
    *   It interprets the specific arguments and flags relevant to its command (e.g., for `search`, it checks `args.get_issue`, `args.cv_name_filter`, `args.verbose`, etc.).
    *   **Data Fetching (for `search` and `tag --issue-id`):**
        *   `fetch_api.py`'s `make_comicvine_api_request()` is called with appropriate URL and parameters (from `config.py`).
        *   This function uses the `requests` library to make the HTTP GET call.
        *   It handles retries for rate limits and basic API error checking.
        *   It returns the parsed JSON data (as a Python dictionary) or `None` on failure.
    *   **Data Processing/Mapping (for `tag`):**
        *   `tagging.py`'s `map_cv_to_comicinfo_dict()` processes fetched ComicVine data (or data from a local JSON file) into a `ComicInfo.xml`-compatible dictionary.
    *   **File Operations (for `tag`, `convert`, `inspect`):**
        *   `tagging.py`: `write_comic_info_to_cbz()` and `erase_comic_info_from_cbz()` use `zipfile`, `xml.etree.ElementTree`, `shutil`, and `tempfile` to modify `.cbz` archives. `_generate_new_filename()` and `shutil.move()` handle renaming.
        *   `inspect_files.py`: `read_comic_info_from_archive()` uses `zipfile` and `xml.etree.ElementTree`.
        *   `convert_files.py`: Uses `subprocess` (for `unrar`, `7z`, `mutool`), `tarfile`, `zipfile`, and `tempfile` for file conversions.
    *   **Output Display:**
        *   Most handler functions call display helpers from `fetch_api.py` (for API data) or `inspect_files.py` (for local XML data), which in turn use generic printing utilities from `utils.py` (`print_field`, `print_header_line`, etc.) to present information to the user in the terminal.
4.  The application typically exits after the handler function completes its task. The main CLI script (`comic-tagger.py`) manages the final exit status implicitly (0 on normal completion, or Python's default for unhandled exceptions).

## 5. External Dependencies

*   **ComicVine API:**
    *   **Service:** The primary external data source, provided by [comicvine.gamespot.com](https://comicvine.gamespot.com/api/).
    *   **Interaction:** Via HTTPS GET requests using the `requests` library.
    *   **Authentication:** Requires an `api_key` (from `config.py`) appended to every request URL.
    *   **Data Format:** JSON is requested and processed.
    *   **User-Agent:** A non-empty `User-Agent` header (from `config.py`) is required for all API requests.
    *   **Rate Limits:** The API has rate limits (e.g., 200 requests/resource/hour). `make_comicvine_api_request()` implements basic retry logic with delays.
*   **External Command-Line Tools (for `convert` command only):**
    *   **`unrar`**: Used by `convert_files.py` to extract RAR archives (`.cbr`). Called via `subprocess`.
    *   **`7z`**: Used by `convert_files.py` to extract 7-Zip archives (`.cb7`). Called via `subprocess`.
    *   **`mutool`**: Used by `convert_files.py` to extract images from PDF files. Called via `subprocess`.
    *   The application checks for the existence of these tools using `shutil.which()` before attempting to use them. If a tool is missing, an error is reported, and the specific conversion requiring it will fail.

## 6. Configuration and Setup

*   **Main Configuration (`config.py`):**
    *   `CV_API_KEY`: **Users may need to edit this file to insert their personal ComicVine API key.**
    *   `CV_USER_AGENT`: Defaults to `"Python-Comic-Tagger/Modular-1.x"`. Can be overridden by setting the `CV_FETCHER_USER_AGENT` environment variable before running the script.
    *   Other API parameters (base URL, timeouts, retry settings, resource prefixes) are also defined here and are generally not intended for user modification unless the API itself changes.
*   **Setup:**
    *   Python 3.8+ environment.
    *   Installation of Python packages listed in `requirements.txt` (`pip install -r requirements.txt`).
    *   For the `convert` command to be fully functional, the external tools (`unrar`, `7z`, `mutool`) must be installed and available in the system's PATH. Instructions for these are typically provided in the `README.md`.
*   **No other explicit setup or configuration files are required by the application itself.**

## 7. Assumptions, Constraints, and To-Dos

### Assumptions:

*   The user has a stable internet connection for ComicVine API interactions.
*   The ComicVine API structure and endpoint URLs remain consistent with what's defined in `config.py`.
*   Input comic files for tagging/inspection are valid `.cbz` archives.
*   Input files for conversion are valid archives/PDFs of the types the script claims to support.
*   The `ComicInfo.xml` schema targeted is the generally accepted community standard (e.g., as used by ComicRack and other popular readers/managers).
*   The terminal used supports ANSI escape codes for color and styling for the intended visual output. Clickable links depend on terminal emulator support.

### Constraints & Known Limitations:

*   **ComicVine API Rate Limits:** Heavy usage, especially features like `search --include-issues` or author-first searches for prolific creators, can hit API rate limits. The retry mechanism is basic.
*   **Author Search for Volumes:** Searching volumes by author (`search -a ...`) relies on ComicVine's API filtering, which can be broad. Local post-filtering for author *roles* on the volume list is not performed due to the `/api/volumes/` endpoint not returning detailed `person_credits` for each volume in the list. Users are advised to combine author searches with more specific title/series names.
*   **`ComicInfo.xml` Mapping:** The `map_cv_to_comicinfo_dict()` function in `tagging.py` maps many common ComicVine fields to `ComicInfo.xml` tags. However, not all ComicVine data points have direct or standard equivalents in `ComicInfo.xml`. Some data (e.g., very specific concepts, objects, aliases) might be aggregated into more general tags like `Notes` or `Genre`. The mapping can always be expanded or refined.
*   **Error Handling:** While basic error handling is in place for API calls and file operations, more granular error reporting or recovery mechanisms could be added.
*   **PDF Conversion Quality:** PDF to image conversion via `mutool` uses a default DPI (150). Quality can vary depending on the source PDF. This DPI is not currently user-configurable via a CLI flag.
*   **File Renaming Pattern:** The renaming pattern in `tagging.py` (`_generate_new_filename`) is fixed. Making this user-configurable would be a future enhancement.

### To-Dos & Future Work (Ideas):

*   **`erase` Command Implementation:** The `erase` command (currently a placeholder in `comic-tagger.py`) needs its core logic to be implemented in `tagging.py` (or a new `erase.py` module) to safely remove `ComicInfo.xml` from CBZ files.
*   **Interactive Modes:**
    *   For `search`: Allow selecting from multiple volume/issue results if a search is ambiguous.
    *   For `tag`: An interactive mode to review and edit metadata before writing to `ComicInfo.xml`.
*   **Advanced Caching:** Implement local caching of ComicVine API responses to reduce redundant calls and respect rate limits more effectively.
*   **Batch Tagging from Manifest:** Extend the `tag --from-file` functionality to support a manifest file that maps multiple local comic files to their respective metadata (either ComicVine IDs or inline metadata), allowing batch processing.
*   **Configuration File for Naming Patterns:** Allow users to define their preferred filename patterns for the `--rename` feature.
*   **More Robust HTML Stripping:** For descriptions from ComicVine, `strip_html()` is basic. A library like `BeautifulSoup` could be used for more nuanced HTML parsing if needed.
*   **Plugin System for Converters/Metadata Sources:** (Very advanced) Allow new conversion formats or metadata sources to be added via plugins.
*   **Unit Tests:** Develop a suite of unit tests for individual functions and modules to ensure reliability and facilitate safer refactoring.
*   **Packaging:** Package the application properly for easier distribution and installation (e.g., using `setup.py` or `pyproject.toml` for PyPI).