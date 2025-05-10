#!/usr/bin/env python3

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime # For parsing dates
import zipfile
import shutil # For shutil.move
import tempfile # For temporary zip creation
import sys
from inspect_files import handle_check as perform_check_on_file # Alias to avoid name clash

# Import from our other modules
from config import CV_BASE_URL, CV_ISSUE_PREFIX # For fetching data if tagging by ID
from utils import (
    Style, print_error, print_info, print_success,
    strip_html, print_header_line
)
# We need the API request function if tagging by issue ID
from fetch_api import make_comicvine_api_request 

def _perform_actual_tagging(args, cbz_file_path): # Internal helper for actual tagging
    """Performs the tagging operation once metadata source is determined."""
    print_header_line(f"Tagging: {os.path.basename(cbz_file_path)}", color=Style.GREEN)
    print_info(f"  File: {cbz_file_path}")
    comic_info_data_to_write = {}

    if args.issue_id:
        print_info(f"Fetching metadata from ComicVine for issue ID: {args.issue_id}...")
        issue_params = {} # No field_list to get all fields
        cv_api_response = make_comicvine_api_request(f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.issue_id}/", issue_params)
        if cv_api_response and cv_api_response.get('results'):
            cv_issue_details = cv_api_response.get('results')
            print_info("  Successfully fetched data from ComicVine.")
            comic_info_data_to_write = map_cv_to_comicinfo_dict(cv_issue_details)
            if not comic_info_data_to_write:
                print_error("  Could not map ComicVine data to ComicInfo format. No data to tag."); return
        else:
            print_error(f"  Failed to fetch data for issue ID {args.issue_id} from ComicVine."); return
    elif args.from_file:
        metadata_file_path = os.path.abspath(os.path.expanduser(args.from_file))
        # ... (logic for loading from --from-file as before) ...
        print_info(f"Loading metadata from file: {metadata_file_path}...")
        # ... (error handling for file not found, JSON decode error etc.) ...
        # ... comic_info_data_to_write = loaded_data ...
        if not os.path.isfile(metadata_file_path):
            print_error(f"  Metadata file not found: {metadata_file_path}"); return
        try:
            with open(metadata_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f) 
                if not isinstance(loaded_data, dict):
                    print_error(f"  Metadata file {args.from_file} does not contain a valid JSON object."); return
                comic_info_data_to_write = {k: str(v) if v is not None else None for k, v in loaded_data.items()}
                print_info(f"  Successfully loaded metadata from {args.from_file}.")
        except json.JSONDecodeError: print_error(f"  Invalid JSON in metadata file: {args.from_file}"); return
        except Exception as e: print_error(f"  Could not process metadata file {args.from_file}: {e}"); return

    if not comic_info_data_to_write:
        print_info("No metadata available to tag with. Exiting."); return
    write_comic_info_to_cbz(cbz_file_path, comic_info_data_to_write, overwrite_all=args.overwrite_all)


# This is the main handler function for the 'tag' subparser in comic_tagger_cli.py
def handle_tagging_dispatch(args):
    """
    Dispatches to tag, erase, or check based on flags for a single CBZ file.
    """
    cbz_file_path_abs = os.path.abspath(os.path.expanduser(args.cbz_file_path))
    if not os.path.isfile(cbz_file_path_abs) or not cbz_file_path_abs.lower().endswith(".cbz"):
        print_error(f"Invalid CBZ file path: {cbz_file_path_abs}. Must be an existing .cbz file.")
        return

    if args.check:
        # Call the check functionality (which now lives in inspect_files.py)
        # We need to pass 'args' in a way that handle_check expects, which is args.paths list.
        # So, we create a temporary Namespace-like object or just pass the path.
        class CheckArgs:
            def __init__(self, path):
                self.paths = [path]
        check_args = CheckArgs(cbz_file_path_abs)
        perform_check_on_file(check_args) # from inspect_files import handle_check as perform_check_on_file

    elif args.erase:
        print_header_line(f"Erasing Tags: {os.path.basename(cbz_file_path_abs)}", color=Style.RED)
        print_info(f"  File: {cbz_file_path_abs}")
        if args.issue_id or args.from_file: # These are now part of the same 'args' namespace
            print_info("  --issue-id and --from-file flags are ignored when --erase is used.")
        erase_comic_info_from_cbz(cbz_file_path_abs)

    elif args.issue_id or args.from_file: # This means actual tagging
        _perform_actual_tagging(args, cbz_file_path_abs)
        
    else:
        # This case should ideally be prevented by argparse (mutually exclusive group being required)
        print_error("No tagging action specified. Use --issue-id, --from-file, --erase, or --check.")

# --- XML and Mapping Helper Functions ---

def map_cv_to_comicinfo_dict(cv_issue_data): # cv_issue_data is the 'results' object for a single issue
    """
    Maps comprehensive ComicVine issue data to a dictionary suitable for ComicInfo.xml.
    """
    if not cv_issue_data:
        return {}

    info = {} # This will be our ComicInfo.xml dictionary
    
    # --- Core Issue Fields ---
    if cv_issue_data.get('name'): info['Title'] = cv_issue_data['name']
    if cv_issue_data.get('issue_number'): info['Number'] = cv_issue_data['issue_number']
    
    aliases = cv_issue_data.get('aliases')
    if aliases: # Aliases is usually a newline-separated string from API
        aliases_text = strip_html(aliases) # Clean it up just in case
        if aliases_text:
            info['Notes'] = info.get('Notes', '') + f"\nAliases:\n{aliases_text}".strip()

    if cv_issue_data.get('cover_date'):
        try:
            date_str = cv_issue_data['cover_date']
            parsed_successfully = False
            if date_str: # Ensure date_str is not None or empty
                if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-': # YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
                    actual_date_part = date_str.split(' ')[0]
                    cover_dt = datetime.strptime(actual_date_part, '%Y-%m-%d')
                    info['Year'] = str(cover_dt.year); info['Month'] = str(cover_dt.month); info['Day'] = str(cover_dt.day)
                    parsed_successfully = True
                elif len(date_str) == 7 and date_str[4] == '-': # YYYY-MM
                    cover_dt = datetime.strptime(date_str, '%Y-%m')
                    info['Year'] = str(cover_dt.year); info['Month'] = str(cover_dt.month)
                    parsed_successfully = True
                elif len(date_str) == 4 and date_str.isdigit(): # YYYY
                    info['Year'] = date_str
                    parsed_successfully = True
            if not parsed_successfully and date_str: # If known formats fail but there is a string
                print_info(f"  Could not parse cover_date '{date_str}' into Year/Month/Day with known formats.")
        except (ValueError, TypeError) as e:
            print_info(f"  Warning parsing cover_date '{cv_issue_data.get('cover_date')}': {e}")


    if cv_issue_data.get('store_date'):
        if cv_issue_data.get('store_date') != cv_issue_data.get('cover_date'): # Only add if different
             info['Notes'] = info.get('Notes', '') + f"\nStore Date: {cv_issue_data['store_date']}".strip()

    if cv_issue_data.get('description'): info['Summary'] = strip_html(cv_issue_data['description'])
    if cv_issue_data.get('deck'): 
        current_notes = info.get('Notes', '')
        deck_text = strip_html(cv_issue_data['deck'])
        if deck_text: # Only add deck if it has content after stripping HTML
            info['Notes'] = (current_notes + f"\nDeck (Summary): {deck_text}").strip()

    if cv_issue_data.get('site_detail_url'): info['Web'] = cv_issue_data['site_detail_url']

    # --- Volume Related Info ---
    volume = cv_issue_data.get('volume')
    if volume and isinstance(volume, dict): # Ensure volume is a dict
        if volume.get('name'): info['Series'] = volume['name']
        
        if volume.get('publisher') and isinstance(volume['publisher'], dict) and volume['publisher'].get('name'):
            info['Publisher'] = volume['publisher']['name']
        
        if volume.get('count_of_issues') is not None:
             info['Count'] = str(volume.get('count_of_issues'))
        
        if volume.get('start_year') and 'Year' not in info: # Only if issue itself didn't provide a year
            info['Year'] = str(volume.get('start_year'))
    
    # --- Credits Mapping ---
    person_credits = cv_issue_data.get('person_credits', [])
    person_roles_map = { # (CV role keyword, ComicInfo_Tag)
        'writer': 'Writer', 'penciler': 'Penciller', 'inker': 'Inker',
        'colorist': 'Colorist', 'letterer': 'Letterer', 
        'cover': 'CoverArtist', 'artist': 'Artist', 'editor': 'Editor',
        'plotter': 'Writer', 'scripter': 'Writer' # Map plot/script to Writer
    }
    # More generic roles that might appear if not specific above
    generic_art_roles = ['art', 'colors', 'letters', 'pencils', 'inks'] 

    temp_credits_by_ci_tag = {} # { 'ComicInfoTag': set_of_names, ... }
    
    if isinstance(person_credits, list):
        for person in person_credits:
            name = person.get('name')
            if not name: continue
            
            cv_person_roles_str = (person.get('role') or '').lower()
            roles_assigned_for_person = set()

            # Try specific role mappings first
            for cv_role_keyword, ci_tag in person_roles_map.items():
                if cv_role_keyword in cv_person_roles_str:
                    if ci_tag not in temp_credits_by_ci_tag: temp_credits_by_ci_tag[ci_tag] = set()
                    temp_credits_by_ci_tag[ci_tag].add(name)
                    roles_assigned_for_person.add(ci_tag)
            
            # Fallback for generic art roles if no specific art role was assigned
            # and the role string contains a generic art term
            if not any(art_role in roles_assigned_for_person for art_role in ['Penciller', 'Inker', 'Colorist', 'CoverArtist']):
                for generic_art_term in generic_art_roles:
                    if generic_art_term in cv_person_roles_str:
                        if 'Artist' not in temp_credits_by_ci_tag: temp_credits_by_ci_tag['Artist'] = set()
                        temp_credits_by_ci_tag['Artist'].add(name)
                        break # Added to generic Artist, no need to check other generic art terms for this person

    for ci_tag, names_set in temp_credits_by_ci_tag.items():
        if names_set: info[ci_tag] = ", ".join(sorted(list(names_set)))

    # --- Other Credit Lists ---
    def map_generic_credits_list(cv_key, comic_info_tag):
        items = cv_issue_data.get(cv_key) # API returns list of dicts or null
        if items and isinstance(items, list):
            names = sorted(list(set([item.get('name') for item in items if item.get('name')])))
            if names: info[comic_info_tag] = ", ".join(names)

    map_generic_credits_list('character_credits', 'Characters')
    map_generic_credits_list('team_credits', 'Teams')
    map_generic_credits_list('location_credits', 'Locations')
    map_generic_credits_list('story_arc_credits', 'StoryArc')
    
    # Concepts into Genre, Objects into Notes
    concept_names = []
    concepts = cv_issue_data.get('concept_credits')
    if concepts and isinstance(concepts, list):
        concept_names = sorted(list(set([c.get('name') for c in concepts if c.get('name')])))
    if concept_names:
        existing_genre_str = info.get('Genre', '')
        existing_genre_set = set([g.strip() for g in existing_genre_str.split(',') if g.strip()])
        for cn in concept_names: existing_genre_set.add(cn)
        if existing_genre_set: info['Genre'] = ", ".join(sorted(list(existing_genre_set)))

    object_names = []
    objects = cv_issue_data.get('object_credits')
    if objects and isinstance(objects, list):
        object_names = sorted(list(set([o.get('name') for o in objects if o.get('name')])))
    if object_names:
        info['Notes'] = (info.get('Notes', '') + f"\nObjects: {', '.join(object_names)}").strip()
    
    info.setdefault('LanguageISO', 'en')
    info.setdefault('Format', 'Comic') # A common default

    return {k: v for k, v in info.items() if v is not None and str(v).strip() != ""}


def create_comic_info_xml_element(metadata_dict):
    """Creates an ET.Element for ComicInfo.xml from a dictionary."""
    root = ET.Element("ComicInfo")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")

    tag_order = [
        "Title", "Series", "Number", "Count", "Volume", "AlternateSeries", "AlternateNumber", "AlternateCount",
        "Summary", "Notes", "Year", "Month", "Day",
        "Writer", "Penciller", "Inker", "Colorist", "Letterer", "CoverArtist", "Editor", "Artist",
        "Publisher", "Imprint",
        "Genre", "Web", "PageCount", "LanguageISO", "Format", "BlackAndWhite", "Manga", "Characters", "Teams",
        "Locations", "StoryArc", "SeriesGroup", "AgeRating", "ScanInformation"
    ]
    
    processed_tags = set()
    for tag_name in tag_order:
        if tag_name in metadata_dict and metadata_dict[tag_name] is not None:
            element = ET.SubElement(root, tag_name)
            element.text = str(metadata_dict[tag_name])
            processed_tags.add(tag_name)
            
    for tag_name, value in metadata_dict.items():
        if tag_name not in processed_tags and value is not None:
            element = ET.SubElement(root, tag_name)
            element.text = str(value)
            
    return root

def write_comic_info_to_cbz(cbz_path, comic_info_metadata, overwrite_all=False):
    """
    Writes ComicInfo.xml to a CBZ file.
    If overwrite_all is False, it attempts to merge with existing ComicInfo.xml.
    """
    comic_info_filename = "ComicInfo.xml"
    comic_info_filename_lower = comic_info_filename.lower() # For case-insensitive matching
    temp_zip_path = None 
    temp_fd = -1 # Initialize temp_fd to a value indicating it's not open

    try:
        existing_comic_info_root = None
        found_existing_xml_case_sensitive_name = None

        if not overwrite_all:
            try:
                with zipfile.ZipFile(cbz_path, 'r') as zf_read:
                    # Check for ComicInfo.xml with case-insensitivity
                    for name_in_zip in zf_read.namelist():
                        if name_in_zip.lower() == comic_info_filename_lower:
                            found_existing_xml_case_sensitive_name = name_in_zip
                            break
                    
                    if found_existing_xml_case_sensitive_name:
                        with zf_read.open(found_existing_xml_case_sensitive_name) as xml_file:
                            try:
                                existing_comic_info_root = ET.parse(xml_file).getroot()
                                print_info(f"  Found existing {found_existing_xml_case_sensitive_name}. Merging/updating tags.")
                            except ET.ParseError:
                                print_error(f"  Existing {found_existing_xml_case_sensitive_name} is corrupted. It will be overwritten.")
                                existing_comic_info_root = None 
            except FileNotFoundError: print_error(f"  Source CBZ file not found for reading: {cbz_path}"); return False
            except zipfile.BadZipFile: print_error(f"  Source CBZ file is corrupt: {cbz_path}"); return False
            except Exception as e: print_error(f"  Error reading existing CBZ: {e}"); return False
        
        if existing_comic_info_root and not overwrite_all:
            for tag_name, new_value in comic_info_metadata.items():
                if new_value is None or str(new_value).strip() == "": continue 
                existing_element = existing_comic_info_root.find(tag_name)
                if existing_element is not None: existing_element.text = str(new_value)
                else: ET.SubElement(existing_comic_info_root, tag_name).text = str(new_value)
            final_xml_root = existing_comic_info_root
        else:
            if overwrite_all: print_info(f"  Overwriting existing {comic_info_filename} or creating new.")
            else: print_info(f"  No existing {comic_info_filename} (or corrupted) found. Creating new.")
            final_xml_root = create_comic_info_xml_element(comic_info_metadata)

        # Pretty print XML if Python 3.9+
        if sys.version_info.major == 3 and sys.version_info.minor >= 9:
            ET.indent(final_xml_root, space="\t") # Use tab for indent as per some ComicInfo examples
        
        xml_string_bytes = ET.tostring(final_xml_root, encoding='utf-8', xml_declaration=True, short_empty_elements=False)
        
        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_tag_")
        
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    # Use case-insensitive comparison for the filename to remove/replace
                    if item.filename.lower() != comic_info_filename_lower:
                        zout.writestr(item, zin.read(item.filename))
                # Write the new/updated ComicInfo.xml using the standard filename
                zout.writestr(comic_info_filename, xml_string_bytes) 
        
        os.close(temp_fd); temp_fd = -1
        shutil.move(temp_zip_path, cbz_path); temp_zip_path = None
        print_success(f"  Successfully wrote {comic_info_filename} to {os.path.basename(cbz_path)}")
        return True

    except Exception as e:
        print_error(f"  Failed to write {comic_info_filename} to {os.path.basename(cbz_path)}: {e}")
        return False
    finally:
        if temp_fd != -1 and temp_fd is not None: os.close(temp_fd) # Should be closed if mkstemp succeeded
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)

def erase_comic_info_from_cbz(cbz_path):
    """Removes ComicInfo.xml from a CBZ file."""
    comic_info_filename = "ComicInfo.xml"
    comic_info_filename_lower = comic_info_filename.lower()
    temp_zip_path = None; temp_fd = -1

    xml_existed = False
    try:
        with zipfile.ZipFile(cbz_path, 'r') as zin_check:
            for name_in_zip in zin_check.namelist():
                if name_in_zip.lower() == comic_info_filename_lower:
                    xml_existed = True
                    break
        if not xml_existed:
            print_info(f"  {comic_info_filename} not found in {os.path.basename(cbz_path)}. No action needed.")
            return True
    except Exception as e: print_error(f"  Error checking CBZ {os.path.basename(cbz_path)}: {e}"); return False

    print_info(f"  Attempting to erase {comic_info_filename} from {os.path.basename(cbz_path)}...")
    try:
        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_erase_")
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename.lower() != comic_info_filename_lower:
                        zout.writestr(item, zin.read(item.filename))
        os.close(temp_fd); temp_fd = -1
        shutil.move(temp_zip_path, cbz_path); temp_zip_path = None
        print_success(f"  Successfully erased {comic_info_filename} from {os.path.basename(cbz_path)}.")
        return True
    except Exception as e: print_error(f"  Failed to erase {comic_info_filename} from {os.path.basename(cbz_path)}: {e}"); return False
    finally:
        if temp_fd != -1 and temp_fd is not None: os.close(temp_fd)
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)


# --- Main Handler for 'tag' command ---
def handle_tagging(args):
    cbz_file_path = os.path.abspath(os.path.expanduser(args.cbz_file_path))
    if not os.path.isfile(cbz_file_path) or not cbz_file_path.lower().endswith(".cbz"):
        print_error(f"Invalid CBZ file path: {cbz_file_path}. Must be an existing .cbz file.")
        return

    if args.erase:
        print_header_line(f"Erasing Tags: {os.path.basename(cbz_file_path)}", color=Style.RED)
        print_info(f"  File: {cbz_file_path}")
        if args.issue_id or args.from_file:
            print_info("  --issue-id and --from-file flags are ignored when --erase is used.")
        erase_comic_info_from_cbz(cbz_file_path)
        return

    if not args.issue_id and not args.from_file:
        print_error("Tagging requires a metadata source. Use --issue-id <ID> or --from-file <PATH>.")
        return

    print_header_line(f"Tagging: {os.path.basename(cbz_file_path)}", color=Style.GREEN)
    print_info(f"  File: {cbz_file_path}")
    comic_info_data_to_write = {}

    if args.issue_id:
        print_info(f"Fetching metadata from ComicVine for issue ID: {args.issue_id}...")
        # Ensure fetch_api.py's handle_fetch_comicvine (when called for --get-issue)
        # uses NO field_list to get ALL fields. This is assumed here.
        issue_params = {} # No field_list, make_comicvine_api_request adds api_key & format
        
        cv_api_response = make_comicvine_api_request(f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.issue_id}/", issue_params)
        
        if cv_api_response and cv_api_response.get('results'):
            cv_issue_details = cv_api_response.get('results')
            print_info("  Successfully fetched data from ComicVine.")
            comic_info_data_to_write = map_cv_to_comicinfo_dict(cv_issue_details)
            if not comic_info_data_to_write:
                print_error("  Could not map ComicVine data to ComicInfo format. No data to tag.")
                return
        else:
            print_error(f"  Failed to fetch data for issue ID {args.issue_id} from ComicVine.")
            return
            
    elif args.from_file:
        metadata_file_path = os.path.abspath(os.path.expanduser(args.from_file))
        print_info(f"Loading metadata from file: {metadata_file_path}...")
        if not os.path.isfile(metadata_file_path):
            print_error(f"  Metadata file not found: {metadata_file_path}"); return
        try:
            with open(metadata_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f) 
                if not isinstance(loaded_data, dict):
                    print_error(f"  Metadata file {args.from_file} does not contain a valid JSON object (dictionary).")
                    return
                comic_info_data_to_write = {k: str(v) if v is not None else None for k, v in loaded_data.items()}
                print_info(f"  Successfully loaded metadata from {args.from_file}.")
        except json.JSONDecodeError:
            print_error(f"  Invalid JSON in metadata file: {args.from_file}"); return
        except Exception as e:
            print_error(f"  Could not process metadata file {args.from_file}: {e}"); return

    if not comic_info_data_to_write:
        print_info("No metadata available to tag with. Exiting.")
        return

    write_comic_info_to_cbz(cbz_file_path, comic_info_data_to_write, overwrite_all=args.overwrite_all)