#!/usr/bin/env python3

import argparse
import sys
import os

# Import handler functions from their respective modules
from fetch_api import handle_fetch_comicvine
from tagging import handle_tagging_dispatch # Corrected import from previous step
from convert_files import handle_convert
from utils import Style # For a startup message or error styling if needed directly in CLI

# Import configuration for CV_USER_AGENT default
try:
    from config import CV_USER_AGENT as DEFAULT_CV_USER_AGENT
except ImportError:
    DEFAULT_CV_USER_AGENT = "Python-Comic-Tagger/Modular-1.0"


def main():
    try:
        import natsort
    except ImportError:
        # Use Style for error if utils.py might not have been imported yet or if Style is defined here
        # For safety, let's use a raw string if Style might not be available
        # print(f"{Style.RED}Fatal Error: The 'natsort' library is required for this script.")
        # print(f"Please install it by running: pip install natsort{Style.RESET}")
        print("\033[91mFatal Error: The 'natsort' library is required for this script.\033[0m")
        print("Please install it by running: pip install natsort")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Comic Tagger, ComicVine Searcher, and Converter.", # Updated description
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""Example Usage:
  {os.path.basename(sys.argv[0])} search -s "Batman" --year 2011         # Search volumes by series and year
  {os.path.basename(sys.argv[0])} search -t "Walking Dead" -p Image      # Search volumes by title and publisher
  {os.path.basename(sys.argv[0])} search -v 12345                        # Get details for volume ID 12345
  {os.path.basename(sys.argv[0])} search -i 67890 -V                     # Get verbose details for issue ID 67890
  
  {os.path.basename(sys.argv[0])} tag -id 48791 my_comic.cbz             # Tag comic.cbz with data from CV issue 48791
  {os.path.basename(sys.argv[0])} tag -f metadata.json -o my_comic.cbz   # Tag comic.cbz from file, overwriting all
  {os.path.basename(sys.argv[0])} tag -c my_comic.cbz                    # Check ComicInfo.xml in my_comic.cbz
  {os.path.basename(sys.argv[0])} tag -e my_comic.cbz                    # Erase ComicInfo.xml from my_comic.cbz
  
  {os.path.basename(sys.argv[0])} convert /path/to/comics_to_convert/    # Convert all supported files in a directory
  {os.path.basename(sys.argv[0])} convert my_comic.pdf /another/comic.cbr # Convert specific files"""
    )
    subparsers = parser.add_subparsers(dest='main_command', title='Main Commands', 
                                     help='Select an operation', required=True)
# In comic_tagger_cli.py, within main()

    # --- Search Subcommand (formerly Fetch) ---
    search_parser = subparsers.add_parser('search', 
                                          help='Search ComicVine for volumes or get specific volume/issue details', # Updated help
                                          formatter_class=argparse.RawTextHelpFormatter)
    
    # Mode group for search: get specific item OR use search criteria (implicitly)
    # This group ensures that if -v or -i is used, other search criteria flags are contextually less relevant
    # for that specific fetch, though they won't cause an error.
    search_action_group = search_parser.add_mutually_exclusive_group(required=False) # No longer required
    search_action_group.add_argument('--get-volume', '-v', 
                                     type=int, metavar='VOLUME_ID', 
                                     help='Get a specific volume by ID.')
    search_action_group.add_argument('--get-issue', '-i', 
                                     type=int, metavar='ISSUE_ID', 
                                     help='Get a specific issue by ID.')
    # REMOVED: search_action_group.add_argument('--query', '-q', action='store_true', ...)

    # Arguments for the 'search' command (used for criteria-based search if --get-volume/--get-issue not present)
    search_parser.add_argument('--verbose', '-V', action='store_true', 
                               help="Show verbose output, especially for --get-issue.")
    search_parser.add_argument('--series', '-s', dest='cv_series_name', 
                               help="Search criteria: series name.")
    search_parser.add_argument('--title', '-t', dest='cv_title_desc', 
                               help="Search criteria: title/description.")
    search_parser.add_argument('--author', '-a', dest='cv_author_name', 
                               help="Search criteria: author/creator name.")
    search_parser.add_argument('--year', '-y', dest='cv_start_year', type=int, 
                               help="Search criteria: EXACT start year.")
    search_parser.add_argument('--publisher', '-p', dest='cv_publisher_name', 
                               help="Search criteria: publisher name.")
    search_parser.add_argument('--num-issues', '-n', dest='cv_issues_count', type=int, 
                               help="Search criteria: EXACT number of issues.")
    
    search_parser.set_defaults(func=handle_fetch_comicvine)
    # --- Tag Subcommand ---
    tag_parser = subparsers.add_parser('tag', 
                                       help='Tag a comic file, erase its tags, or check existing tags.')
    
    tag_action_exclusive_group = tag_parser.add_mutually_exclusive_group(required=True)
    # Ensuring '--issue-id' and its short form '-id' are unique here
    tag_action_exclusive_group.add_argument('--issue-id', '-id', # Short flag is -id
                                            type=int, metavar='CV_ISSUE_ID',
                                            help="Tag using ComicVine Issue ID.")
    tag_action_exclusive_group.add_argument('--from-file', '-f', metavar='METADATA_JSON_FILE',
                                            help="Tag using metadata from a local JSON file.")
    tag_action_exclusive_group.add_argument('--erase', '-e', action='store_true',
                                            help="Erase ComicInfo.xml from the CBZ file.")
    tag_action_exclusive_group.add_argument('--check', '-c', action='store_true',
                                            help="Check and display existing ComicInfo.xml from the CBZ file.")

    tag_parser.add_argument('cbz_file_path', metavar='COMIC_FILE_PATH',
                            help="Path to the .cbz comic file to operate on.")
    
    tag_parser.add_argument('--overwrite-all', '-o', action='store_true',
                            help="Completely replace existing ComicInfo.xml when tagging (default is to merge/update).")
    
    tag_parser.set_defaults(func=handle_tagging_dispatch)

    # --- Convert Subcommand ---
    convert_parser = subparsers.add_parser('convert', 
                                           help='Convert comic files (CBR, CB7, CBT, PDF) to CBZ', 
                                           formatter_class=argparse.RawTextHelpFormatter)
    convert_parser.add_argument('paths', nargs='+', 
                                help="Path(s) to comic file(s) or directory(s) to convert.\n"
                                     "A 'converted' subdirectory will be created relative to the input.")
    convert_parser.set_defaults(func=handle_convert)

    parsed_args = parser.parse_args()
    
    # Set global User-Agent (config.py will read this environment variable)
    # This is just to ensure the env var is set if specified by user; config.py does the actual read.
    if 'CV_FETCHER_USER_AGENT' in os.environ:
        # This line is more for completeness; config.py should handle the os.environ.get directly.
        # If config.py reads os.environ.get('CV_FETCHER_USER_AGENT', DEFAULT_CV_USER_AGENT) at import time,
        # this line here isn't strictly necessary to *change* the value used by other modules.
        pass 
    
    if hasattr(parsed_args, 'func'):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()