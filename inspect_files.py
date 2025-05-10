#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
import zipfile
import sys # For sys.exit if needed, though CLI should handle it

# Import utilities
from utils import (
    Style, print_error, print_info,
    print_header_line, print_field, print_multiline_text,
    make_clickable_link # If ComicInfo.xml contains URLs we want to make clickable
)
# No natsort needed here unless we decide to sort displayed tags, which is less common for check

# --- XML Reading and Parsing ---
def read_comic_info_from_archive(archive_path):
    """
    Reads ComicInfo.xml from a CBZ and parses it into a dictionary.
    Returns the dictionary or None if not found, error, or not a CBZ.
    """
    comic_info_filename = "ComicInfo.xml"
    ext = os.path.splitext(archive_path)[1].lower()

    if ext != ".cbz":
        # Silently skip non-CBZ files for the 'check' command, or print a specific info message
        # print_info(f"Skipping non-CBZ file for ComicInfo check: {os.path.basename(archive_path)}")
        return None

    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            if comic_info_filename not in zf.namelist():
                return None # ComicInfo.xml not found

            with zf.open(comic_info_filename) as xml_file:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    comic_info_dict = {}
                    # Standard tags known to sometimes be comma-separated lists
                    known_list_tags = [
                        "Writer", "Penciller", "Inker", "Colorist", "Letterer", 
                        "CoverArtist", "Editor", "Artist", "Genre", "Characters", 
                        "Teams", "Locations", "StoryArc"
                    ]
                    for element in root:
                        tag = element.tag
                        text = (element.text or "").strip() # Ensure text is not None before strip
                        
                        if text: # Only process if there's actual text content
                            if tag in known_list_tags:
                                # Split by comma, strip whitespace from each item, filter out empty strings
                                items = [item.strip() for item in text.split(',') if item.strip()]
                                if len(items) > 1: # If multiple items after split, store as list
                                    comic_info_dict[tag] = items
                                else: # Single item or empty after split, store as string
                                    comic_info_dict[tag] = text
                            else: # Not a known list tag, store as string
                                comic_info_dict[tag] = text
                        # else:
                            # comic_info_dict[tag] = None # Or "" if preferred for empty tags
                            # For check, it's probably better to just omit keys for empty tags
                    
                    return comic_info_dict
                except ET.ParseError as e:
                    print_error(f"    Error parsing {comic_info_filename} in {os.path.basename(archive_path)}: {e}")
                    return None
    except zipfile.BadZipFile:
        print_error(f"  Error: {os.path.basename(archive_path)} is not a valid CBZ file or is corrupted.")
        return None
    except FileNotFoundError: # Should not happen if path is validated before calling
        print_error(f"  File not found: {archive_path}")
        return None
    except Exception as e:
        print_error(f"  Error reading CBZ {os.path.basename(archive_path)}: {e}")
        return None

# --- Display Function for ComicInfo Data ---
def display_comic_info_details(comic_info_dict, file_path):
    """Pretty prints details from a ComicInfo.xml dictionary."""
    
    # Use the file_path for the header, as ComicInfo.xml might not have a reliable Title
    print_header_line(f"ComicInfo: {os.path.basename(file_path)}", color=Style.GREEN)
    print_info(f"  Source File: {file_path}") # Add full path for clarity

    if not comic_info_dict:
        print_info(f"  {Style.BRIGHT_BLACK}No ComicInfo.xml data found or parsed in this file.{Style.RESET}")
        return

    # --- Core Info ---
    print_field("Title:", comic_info_dict.get('Title'), value_style=Style.BOLD, value_color=Style.WHITE)
    print_field("Series:", comic_info_dict.get('Series'), value_color=Style.WHITE)
    print_field("Number:", comic_info_dict.get('Number'), value_color=Style.WHITE)
    print_field("Volume:", comic_info_dict.get('Volume'), value_color=Style.WHITE)
    print_field("Count:", comic_info_dict.get('Count'), value_color=Style.WHITE)
    if comic_info_dict.get('Web'):
        print_field("Web URL:", comic_info_dict.get('Web'), is_url=True)
    
    # --- Publication Details ---
    if any(k in comic_info_dict for k in ['Publisher', 'Imprint']):
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Publication:':<18}{Style.RESET}")
        print_field("Publisher:", comic_info_dict.get('Publisher'), indent=1, value_color=Style.WHITE)
        print_field("Imprint:", comic_info_dict.get('Imprint'), indent=1, value_color=Style.WHITE)
    
    # --- Date ---
    if any(k in comic_info_dict for k in ['Year', 'Month', 'Day']):
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Date:':<18}{Style.RESET}")
        print_field("Year:", comic_info_dict.get('Year'), indent=1, value_color=Style.WHITE)
        print_field("Month:", comic_info_dict.get('Month'), indent=1, value_color=Style.WHITE)
        print_field("Day:", comic_info_dict.get('Day'), indent=1, value_color=Style.WHITE)

    # --- Description & Notes ---
    if comic_info_dict.get('Summary'):
        print_multiline_text("Summary:", comic_info_dict.get('Summary'), indent=0)
    if comic_info_dict.get('Notes'):
        print_multiline_text("Notes:", comic_info_dict.get('Notes'), indent=0)

    # --- Creators ---
    creator_tags_map = {
        "Writer": "Writer(s)", "Penciller": "Penciller(s)", "Inker": "Inker(s)",
        "Colorist": "Colorist(s)", "Letterer": "Letterer(s)",
        "CoverArtist": "Cover Artist(s)", "Editor": "Editor(s)", "Artist": "Artist(s)"
    }
    has_creators = any(tag in comic_info_dict for tag in creator_tags_map)
    if has_creators:
        print(f"\n  {Style.BOLD}{Style.GREEN}{'Creators:':<18}{Style.RESET}")
        for ci_tag, display_label in creator_tags_map.items():
            value = comic_info_dict.get(ci_tag)
            if value:
                display_value = ", ".join(value) if isinstance(value, list) else value
                print_field(display_label, display_value, indent=1, value_color=Style.WHITE) # Removed ':' from label
    
    # --- Other Metadata ---
    other_meta_tags_map = {
        "Genre": "Genre(s)", "Characters": "Character(s)", "Teams": "Team(s)",
        "Locations": "Location(s)", "StoryArc": "Story Arc(s)",
        "SeriesGroup": "Series Group", "Format": "Format", "AgeRating": "Age Rating",
        "LanguageISO": "Language", "PageCount": "Page Count",
        "BlackAndWhite": "B&W", "Manga": "Manga",
        "ScanInformation": "Scan Info"
    }
    has_other_meta = any(tag in comic_info_dict for tag in other_meta_tags_map)
    if has_other_meta:
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Additional Info:':<18}{Style.RESET}")
        for ci_tag, display_label in other_meta_tags_map.items():
            value = comic_info_dict.get(ci_tag)
            # Handle boolean-like values for B&W and Manga appropriately
            if ci_tag in ["BlackAndWhite", "Manga"]:
                if value is not None: # Only print if tag exists
                    bool_val = str(value).lower() == 'yes' or str(value).lower() == 'true'
                    display_value = "Yes" if bool_val else "No"
                    print_field(display_label, display_value, indent=1, value_color=Style.WHITE) # Removed ':'
            elif value is not None: # For other tags, print if value exists
                display_value = ", ".join(value) if isinstance(value, list) else str(value)
                print_field(display_label, display_value, indent=1, value_color=Style.WHITE) # Removed ':'

# --- Main Handler for 'check' command ---
def handle_check(args):
    """
    Handles checking ComicInfo.xml in specified files/directories.
    """
    print_header_line("ComicInfo.xml Check", color=Style.GREEN)
    files_to_check_q = [] # Use a list as a queue

    for path_arg in args.paths:
        abs_path = os.path.abspath(os.path.expanduser(path_arg)) 
        if os.path.isdir(abs_path):
            # print_info(f"Scanning directory: {abs_path}") # Can be verbose
            for root, _, files_in_dir in os.walk(abs_path):
                for f_name in files_in_dir:
                    if f_name.lower().endswith(('.cbz')): # Only check CBZ for ComicInfo.xml
                        files_to_check_q.append(os.path.join(root, f_name))
        elif os.path.isfile(abs_path):
            if abs_path.lower().endswith(('.cbz')):
                files_to_check_q.append(abs_path)
            else:
                print_info(f"Skipping non-CBZ file for check: {os.path.basename(abs_path)}")
        else:
            print_error(f"Path not found or invalid: {abs_path}")

    if not files_to_check_q:
        print_info("No CBZ files found to check in the specified paths.")
        return

    unique_files_to_check = sorted(list(set(files_to_check_q))) # Process unique files, sorted
    found_tags_count = 0

    for i, comic_file_path in enumerate(unique_files_to_check):
        comic_info_data_dict = read_comic_info_from_archive(comic_file_path)
        
        # display_comic_info_details handles the header and "not found" message internally now
        display_comic_info_details(comic_info_data_dict, comic_file_path)
            
        if comic_info_data_dict is not None and comic_info_data_dict: # Check if dict is not None AND not empty
            found_tags_count += 1
        
        if i < len(unique_files_to_check) - 1: # Add a visual separator between files
            print("\n" + Style.BRIGHT_BLACK + "-" * shutil.get_terminal_size((80,20)).columns + Style.RESET)


    print_header_line("Check Summary", color=Style.GREEN)
    print_info(f"  Processed {len(unique_files_to_check)} CBZ file(s).")
    if found_tags_count > 0:
        print_info(f"  Found and displayed ComicInfo.xml for {Style.GREEN}{found_tags_count}{Style.RESET} file(s).")
    else:
        print_info(f"  ComicInfo.xml not found or empty in any of the processed CBZ files.")