#!/usr/bin/env python3

import argparse
import sys
import os

# Import handler functions from their respective modules
from fetch_api import handle_fetch_comicvine
from tagging import handle_tagging
from inspect_files import handle_check # Renamed module to inspect_files.py for clarity
from convert_files import handle_convert
from utils import Style # For a startup message or error styling if needed directly in CLI
# No direct need for erase_handler yet as it's a placeholder

# Import configuration for CV_USER_AGENT default
try:
    from config import CV_USER_AGENT as DEFAULT_CV_USER_AGENT
except ImportError:
    # Fallback if config.py is not created or CV_USER_AGENT is not in it
    DEFAULT_CV_USER_AGENT = "Python-Comic-Tagger/Modular-1.0"


def main():
    # Check for natsort at startup, as it's a critical dependency for multiple modules
    # We'll do this check here as it's the entry point.
    # Individual modules that use it can also import it.
    try:
        import natsort
    except ImportError:
        print(f"{Style.RED}Fatal Error: The 'natsort' library is required for this script.")
        print(f"Please install it by running: pip install natsort{Style.RESET}")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Comic Tagger, Comic Vine Fetcher, and Converter.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""Example Usage:
  {os.path.basename(sys.argv[0])} fetch --search-volumes --series "Batman" --year 2011
  {os.path.basename(sys.argv[0])} fetch --get-volume 12345
  {os.path.basename(sys.argv[0])} fetch --get-issue 67890 --verbose
  {os.path.basename(sys.argv[0])} tag --issue-id 48791 my_comic.cbz
  {os.path.basename(sys.argv[0])} tag --from-file metadata.json my_comic.cbz --overwrite-all
  {os.path.basename(sys.argv[0])} check ./comics_folder/ my_comic.cbz
  {os.path.basename(sys.argv[0])} convert /path/to/comics_dir/
  {os.path.basename(sys.argv[0])} convert my_comic.pdf /another/comic.cbr"""
    )
    subparsers = parser.add_subparsers(dest='main_command', title='Main Commands', 
                                     help='Select an operation', required=True)

    # --- Fetch Subcommand ---
    fetch_parser = subparsers.add_parser('fetch', help='Fetch data from ComicVine', formatter_class=argparse.RawTextHelpFormatter)
    fetch_mode_group = fetch_parser.add_mutually_exclusive_group(required=True)
    fetch_mode_group.add_argument('--search-volumes', action='store_true', help='Search for volumes (use with search criteria below)')
    fetch_mode_group.add_argument('--get-volume', type=int, metavar='VOLUME_ID', help='Fetch a specific volume by ID')
    fetch_mode_group.add_argument('--get-issue', type=int, metavar='ISSUE_ID', help='Fetch a specific issue by ID')
    fetch_parser.add_argument('--verbose', '-V', action='store_true', help="Show verbose output, especially for --get-issue.")
    fetch_parser.add_argument('--series', dest='cv_series_name', help="Filter volumes by series name (local 'contains' match)")
    fetch_parser.add_argument('--title', dest='cv_title_desc', help="Filter by title/description (local 'contains' match)")
    fetch_parser.add_argument('--author', dest='cv_author_name', help="Filter by author/creator name (API 'person' filter)")
    fetch_parser.add_argument('--year', dest='cv_start_year', type=int, help="Filter volumes by EXACT start year (local match)")
    fetch_parser.add_argument('--publisher', dest='cv_publisher_name', help="Filter by publisher name (API filter + local 'contains' match)")
    fetch_parser.add_argument('--num-issues', dest='cv_issues_count', type=int, help="Filter by EXACT number of issues (local match)")
    fetch_parser.set_defaults(func=handle_fetch_comicvine) # Link to handler
    
    

    # --- Tag Subcommand ---
    tag_parser = subparsers.add_parser('tag', 
                                      help='Tag a comic file or erase its existing ComicInfo.xml') # Updated help
   
    # Option to erase ComicInfo.xml
    tag_parser.add_argument('--erase', action='store_true',
                           help="Erase ComicInfo.xml from the specified CBZ file.")

    # Group for specifying the source of metadata (now optional if --erase is used)
    metadata_source_group = tag_parser.add_mutually_exclusive_group(required=False) # Changed required to False
    metadata_source_group.add_argument('--issue-id', type=int, metavar='CV_ISSUE_ID',
                                      help="ComicVine Issue ID to fetch metadata from (ignored if --erase is present).")
    metadata_source_group.add_argument('--from-file', metavar='METADATA_JSON_FILE',
                                      help="Path to a JSON file with metadata to apply (ignored if --erase is present).")

    # Positional argument for the CBZ file to be tagged/erased
    tag_parser.add_argument('cbz_file_path', metavar='COMIC_FILE_PATH',
                           help="Path to the .cbz comic file to be tagged or have its tags erased.")
   
    tag_parser.add_argument('--overwrite-all', action='store_true', 
                           help="Completely replace existing ComicInfo.xml when tagging (ignored if --erase is present).")
    tag_parser.set_defaults(func=handle_tagging) # Link to existing handler

    # --- Check Subcommand ---
    check_parser = subparsers.add_parser('check', help='Check/list ComicInfo.xml tags in CBZ files')
    check_parser.add_argument('paths', nargs='+', help="Path(s) to CBZ file(s) or directory(s) to check.")
    check_parser.set_defaults(func=handle_check) # Link to handler

    # --- Convert Subcommand ---
    convert_parser = subparsers.add_parser('convert', help='Convert comic files (CBR, CB7, CBT, PDF) to CBZ', formatter_class=argparse.RawTextHelpFormatter)
    convert_parser.add_argument('paths', nargs='+', help="Path(s) to comic file(s) or directory(s) to convert.\nA 'converted' subdirectory will be created relative to the input.")
    convert_parser.set_defaults(func=handle_convert) # Link to handler

    # --- Global Options ---
    # Example: Could add a global --no-color flag here if desired
    # parser.add_argument('--no-color', action='store_true', help="Disable colored output.")

    parsed_args = parser.parse_args()

    # --- Set global User-Agent from environment or default ---
    # This should ideally be accessed via config module, but for now, let's set it here.
    # The individual modules (like fetch_api) will import it from config.
    # For the purpose of this CLI entry point, we ensure the env var is considered for config.
    os.environ['CV_USER_AGENT'] = os.environ.get('CV_FETCHER_USER_AGENT', DEFAULT_CV_USER_AGENT)
    
    # Call the function associated with the chosen subparser
    if hasattr(parsed_args, 'func'):
        parsed_args.func(parsed_args)
    else:
        # Should not happen if a subparser is required and one is always selected
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()