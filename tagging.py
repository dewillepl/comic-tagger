#!/usr/bin/env python3
# tagging.py

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import zipfile
import shutil
import tempfile
import sys

from config import CV_BASE_URL, CV_ISSUE_PREFIX
from utils import (
    Style, print_error, print_info, print_success,
    strip_html, print_header_line, sanitize_filename
)
from fetch_api import make_comicvine_api_request
# Conditionally import translator to avoid error if it's not present / API key not set
try:
    from translator import translate_text, logger as translator_logger
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print_info("Optional 'translator.py' module not found or import error. Translation feature will be disabled.")
    TRANSLATOR_AVAILABLE = False
    translator_logger = None # Placeholder
    def translate_text(text, target_lang_code=None, source_language_code=None): # Dummy function
        if target_lang_code and translator_logger: # Only log if logger was meant to be available
            translator_logger.warning("Translation called but translator module is not available.")
        return text


# --- Filename Generation (_generate_new_filename - remains the same) ---
# ... (copy from previous full version) ...
def _generate_new_filename(metadata_dict, original_extension=".cbz"):
    series = metadata_dict.get('Series'); volume_num_str = metadata_dict.get('Volume'); number = metadata_dict.get('Number') 
    year = metadata_dict.get('Year'); title = metadata_dict.get('Title'); parts = []
    if series: parts.append(sanitize_filename(series))
    if volume_num_str: parts.append(f"V{sanitize_filename(volume_num_str)}")
    if number:
        try: num_val = float(number); num_str = f"{int(num_val):03}" if num_val == int(num_val) else str(num_val)
        except ValueError: num_str = sanitize_filename(number)
        parts.append(f"#{num_str}")
    if year: parts.append(f"({sanitize_filename(year)})")
    if title and title.lower() != (series or "").lower() and \
       title.lower() != (f"issue #{number}".lower() if number else "") and \
       title.lower() != (f"#{number}".lower() if number else ""):
        sanitized_title = sanitize_filename(title)
        if sanitized_title: parts.append(f"- {sanitized_title}")
    if not parts: return None 
    return f"{' '.join(parts)}{original_extension}"


# --- XML and Mapping Helper Functions ---
def map_cv_to_comicinfo_dict(cv_issue_data, target_lang_code=None): # Added target_lang_code
    """
    Maps comprehensive ComicVine issue data to a dictionary suitable for ComicInfo.xml.
    Optionally translates text fields if target_lang_code is provided.
    """
    if not cv_issue_data: return {}
    info = {}

    def _translate_if_needed(text_field_value, field_name_for_log="text"):
        if target_lang_code and TRANSLATOR_AVAILABLE and text_field_value:
            print_info(f"  Translating '{field_name_for_log}' to '{target_lang_code}'...")
            translated = translate_text(text_field_value, target_language_code=target_lang_code)
            if translated == text_field_value: # Check if translation actually happened or fell back
                 print_info(f"    Translation for '{field_name_for_log}' resulted in original text (fallback or no change).")
            return translated
        return text_field_value

    # --- Core Issue Fields ---
    raw_title = cv_issue_data.get('name')
    if raw_title: info['Title'] = _translate_if_needed(raw_title, "Title")
    
    if cv_issue_data.get('issue_number'): info['Number'] = cv_issue_data.get('issue_number')
    
    raw_aliases = cv_issue_data.get('aliases')
    if raw_aliases:
        aliases_text = strip_html(raw_aliases)
        if aliases_text:
            translated_aliases = _translate_if_needed(aliases_text, "Aliases section")
            info['Notes'] = (info.get('Notes', '') + f"\nAliases:\n{translated_aliases}").strip()

    # ... (Date parsing logic - no translation needed for dates) ...
    if cv_issue_data.get('cover_date'):
        try:
            date_str = cv_issue_data['cover_date']; parsed_successfully = False
            if date_str:
                if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-': actual_date_part = date_str.split(' ')[0]; cover_dt = datetime.strptime(actual_date_part, '%Y-%m-%d'); info['Year'] = str(cover_dt.year); info['Month'] = str(cover_dt.month); info['Day'] = str(cover_dt.day); parsed_successfully = True
                elif len(date_str) == 7 and date_str[4] == '-': cover_dt = datetime.strptime(date_str, '%Y-%m'); info['Year'] = str(cover_dt.year); info['Month'] = str(cover_dt.month); parsed_successfully = True
                elif len(date_str) == 4 and date_str.isdigit(): info['Year'] = date_str; parsed_successfully = True
            if not parsed_successfully and date_str: print_info(f"  Could not parse cover_date '{date_str}' with known formats.")
        except (ValueError, TypeError) as e: print_info(f"  Warning parsing cover_date '{cv_issue_data.get('cover_date')}': {e}")

    if cv_issue_data.get('store_date') and cv_issue_data.get('store_date') != cv_issue_data.get('cover_date'):
         info['Notes'] = (info.get('Notes', '') + f"\nStore Date: {cv_issue_data['store_date']}").strip()

    raw_description = cv_issue_data.get('description')
    if raw_description: 
        cleaned_description = strip_html(raw_description)
        info['Summary'] = _translate_if_needed(cleaned_description, "Summary (Description)")
    
    raw_deck = cv_issue_data.get('deck')
    if raw_deck: 
        cleaned_deck = strip_html(raw_deck)
        translated_deck = _translate_if_needed(cleaned_deck, "Deck")
        if translated_deck: # Only add if content exists
             info['Notes'] = (info.get('Notes', '') + f"\nDeck (Summary): {translated_deck}").strip()


    if cv_issue_data.get('site_detail_url'): info['Web'] = cv_issue_data['site_detail_url']

    # --- Volume Related Info ---
    volume = cv_issue_data.get('volume')
    if volume and isinstance(volume, dict):
        raw_series_name = volume.get('name')
        if raw_series_name: info['Series'] = _translate_if_needed(raw_series_name, "Series Name") # Translate series name
        
        if volume.get('publisher') and isinstance(volume['publisher'], dict) and volume['publisher'].get('name'):
            info['Publisher'] = volume['publisher']['name'] # Publisher names usually not translated
        
        if volume.get('count_of_issues') is not None: info['Count'] = str(volume.get('count_of_issues'))
        if volume.get('start_year') and 'Year' not in info: info['Year'] = str(volume.get('start_year'))
    
    # --- Credits Mapping (Names usually not translated, roles might be if needed) ---
    person_credits = cv_issue_data.get('person_credits', [])
    # ... (person_roles_map and generic_art_roles as before) ...
    person_roles_map = {'writer': 'Writer', 'penciler': 'Penciller', 'inker': 'Inker', 'colorist': 'Colorist', 'letterer': 'Letterer', 'cover': 'CoverArtist', 'artist': 'Artist', 'editor': 'Editor', 'plotter': 'Writer', 'scripter': 'Writer'}
    generic_art_roles = ['art', 'colors', 'letters', 'pencils', 'inks']
    temp_credits_by_ci_tag = {}
    if isinstance(person_credits, list):
        for person in person_credits:
            name = person.get('name')
            if not name: continue
            cv_person_roles_str = (person.get('role') or '').lower(); roles_assigned_for_person = set()
            for cv_role_keyword, ci_tag in person_roles_map.items():
                if cv_role_keyword in cv_person_roles_str:
                    if ci_tag not in temp_credits_by_ci_tag: temp_credits_by_ci_tag[ci_tag] = set()
                    temp_credits_by_ci_tag[ci_tag].add(name); roles_assigned_for_person.add(ci_tag)
            if not any(art_role in roles_assigned_for_person for art_role in ['Penciller', 'Inker', 'Colorist', 'CoverArtist']):
                for generic_art_term in generic_art_roles:
                    if generic_art_term in cv_person_roles_str:
                        if 'Artist' not in temp_credits_by_ci_tag: temp_credits_by_ci_tag['Artist'] = set()
                        temp_credits_by_ci_tag['Artist'].add(name); break
    for ci_tag, names_set in temp_credits_by_ci_tag.items():
        if names_set: info[ci_tag] = ", ".join(sorted(list(names_set)))


    # --- Other Credit Lists (Character names, Team names, etc. - usually not translated) ---
    def map_generic_credits_list(cv_key, comic_info_tag):
        items = cv_issue_data.get(cv_key)
        if items and isinstance(items, list):
            names = sorted(list(set([item.get('name') for item in items if item.get('name')])))
            if names: info[comic_info_tag] = ", ".join(names)
    map_generic_credits_list('character_credits', 'Characters'); map_generic_credits_list('team_credits', 'Teams')
    map_generic_credits_list('location_credits', 'Locations'); map_generic_credits_list('story_arc_credits', 'StoryArc')
    
    # Concepts into Genre (Concept names might be translatable)
    concept_names_orig = []
    concepts = cv_issue_data.get('concept_credits')
    if concepts and isinstance(concepts, list):
        concept_names_orig = sorted(list(set([c.get('name') for c in concepts if c.get('name')])))
    
    if concept_names_orig:
        translated_concept_names = [_translate_if_needed(c_name, f"Concept '{c_name}'") for c_name in concept_names_orig]
        existing_genre_str = info.get('Genre', '')
        existing_genre_set = set([g.strip() for g in existing_genre_str.split(',') if g.strip()])
        for cn in translated_concept_names: existing_genre_set.add(cn) # Add translated concepts
        if existing_genre_set: info['Genre'] = ", ".join(sorted(list(existing_genre_set)))

    # Objects into Notes (Object names might be translatable)
    object_names_orig = []
    objects = cv_issue_data.get('object_credits')
    if objects and isinstance(objects, list):
        object_names_orig = sorted(list(set([o.get('name') for o in objects if o.get('name')])))
    if object_names_orig:
        translated_object_names = [_translate_if_needed(o_name, f"Object '{o_name}'") for o_name in object_names_orig]
        info['Notes'] = (info.get('Notes', '') + f"\nObjects: {', '.join(translated_object_names)}").strip()
    
    info.setdefault('LanguageISO', target_lang_code if target_lang_code and TRANSLATOR_AVAILABLE else 'en')
    info.setdefault('Format', 'Comic')

    return {k: v for k, v in info.items() if v is not None and str(v).strip() != ""}


# --- create_comic_info_xml_element, write_comic_info_to_cbz, erase_comic_info_from_cbz
#     (These functions remain the same as the last full tagging.py version)
# ... (copy them here) ...
def create_comic_info_xml_element(metadata_dict): # ... (same as before)
    root = ET.Element("ComicInfo"); root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance"); root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
    tag_order = ["Title", "Series", "Number", "Count", "Volume", "AlternateSeries", "AlternateNumber", "AlternateCount", "Summary", "Notes", "Year", "Month", "Day", "Writer", "Penciller", "Inker", "Colorist", "Letterer", "CoverArtist", "Editor", "Artist", "Publisher", "Imprint", "Genre", "Web", "PageCount", "LanguageISO", "Format", "BlackAndWhite", "Manga", "Characters", "Teams", "Locations", "StoryArc", "SeriesGroup", "AgeRating", "ScanInformation"]
    processed_tags = set()
    for tag_name in tag_order:
        if tag_name in metadata_dict and metadata_dict[tag_name] is not None: ET.SubElement(root, tag_name).text = str(metadata_dict[tag_name]); processed_tags.add(tag_name)
    for tag_name, value in metadata_dict.items():
        if tag_name not in processed_tags and value is not None: ET.SubElement(root, tag_name).text = str(value)
    return root

def write_comic_info_to_cbz(cbz_path, comic_info_metadata, overwrite_all=False): # ... (same as before)
    comic_info_filename = "ComicInfo.xml"; comic_info_filename_lower = comic_info_filename.lower(); temp_zip_path = None; temp_fd = -1
    try:
        existing_comic_info_root = None; found_existing_xml_name = None
        if not overwrite_all:
            try:
                with zipfile.ZipFile(cbz_path, 'r') as zf_read:
                    for name_in_zip in zf_read.namelist():
                        if name_in_zip.lower() == comic_info_filename_lower: found_existing_xml_name = name_in_zip; break
                    if found_existing_xml_name:
                        with zf_read.open(found_existing_xml_name) as xml_file:
                            try: existing_comic_info_root = ET.parse(xml_file).getroot(); print_info(f"  Found existing {found_existing_xml_name}. Merging tags.")
                            except ET.ParseError: print_error(f"  Existing {found_existing_xml_name} corrupted. Overwriting."); existing_comic_info_root = None 
            except Exception as e: print_error(f"  Error reading existing CBZ for merge: {e}")
        final_xml_root = None
        if existing_comic_info_root and not overwrite_all:
            for tag, val in comic_info_metadata.items():
                if val is None or str(val).strip() == "": continue
                el = existing_comic_info_root.find(tag)
                if el is not None: el.text = str(val)
                else: ET.SubElement(existing_comic_info_root, tag).text = str(val)
            final_xml_root = existing_comic_info_root
        else:
            print_info(f"  {'Overwriting' if overwrite_all and existing_comic_info_root else 'Creating new'} {comic_info_filename}.")
            final_xml_root = create_comic_info_xml_element(comic_info_metadata)
        if sys.version_info.major == 3 and sys.version_info.minor >= 9: ET.indent(final_xml_root, space="\t")
        xml_bytes = ET.tostring(final_xml_root, encoding='utf-8', xml_declaration=True, short_empty_elements=False)
        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_tag_")
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename.lower() != comic_info_filename_lower: zout.writestr(item, zin.read(item.filename))
                zout.writestr(comic_info_filename, xml_bytes) 
        os.close(temp_fd); temp_fd = -1; shutil.move(temp_zip_path, cbz_path); temp_zip_path = None
        print_success(f"  Successfully wrote {comic_info_filename} to {os.path.basename(cbz_path)}"); return True
    except Exception as e: print_error(f"  Failed to write {comic_info_filename} to {os.path.basename(cbz_path)}: {e}"); return False
    finally:
        if temp_fd != -1 and temp_fd is not None: os.close(temp_fd)
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)

def erase_comic_info_from_cbz(cbz_path): # ... (same as before)
    comic_info_filename_lower = "comicinfo.xml"; temp_zip_path = None; temp_fd = -1; xml_existed_in_archive = False
    try:
        with zipfile.ZipFile(cbz_path, 'r') as zin_check:
            for name_in_zip in zin_check.namelist():
                if name_in_zip.lower() == comic_info_filename_lower: xml_existed_in_archive = True; break
        if not xml_existed_in_archive: print_info(f"  ComicInfo.xml not found in {os.path.basename(cbz_path)}. No erase needed."); return True
    except Exception as e: print_error(f"  Error checking CBZ {os.path.basename(cbz_path)}: {e}"); return False
    print_info(f"  Attempting to erase ComicInfo.xml from {os.path.basename(cbz_path)}...")
    try:
        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_erase_")
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename.lower() != comic_info_filename_lower: zout.writestr(item, zin.read(item.filename))
        os.close(temp_fd); temp_fd = -1; shutil.move(temp_zip_path, cbz_path); temp_zip_path = None
        print_success(f"  Successfully erased ComicInfo.xml from {os.path.basename(cbz_path)}."); return True
    except Exception as e: print_error(f"  Failed to erase ComicInfo.xml from {os.path.basename(cbz_path)}: {e}"); return False
    finally:
        if temp_fd != -1 and temp_fd is not None: os.close(temp_fd)
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)


# --- Tagging and Renaming Orchestration ---
def _perform_actual_tagging_and_rename(args, cbz_file_path):
    # print(f"DEBUG >>> Inside _perform_actual_tagging_and_rename. args.rename IS: {getattr(args, 'rename', 'NOT_PRESENT_ON_ARGS')}")
    print_header_line(f"Tagging Operation: {os.path.basename(cbz_file_path)}", color=Style.GREEN)
    print_info(f"  File path: {cbz_file_path}")
    
    target_lang = getattr(args, 'translate', None) # Get target language if --translate is used
    if target_lang and not TRANSLATOR_AVAILABLE:
        print_error("  Translation requested but translator module is not available/configured. Proceeding without translation.")
        target_lang = None # Disable translation for this run
    elif target_lang:
        print_info(f"  Translation to '{target_lang}' requested for applicable fields.")

    comic_info_data_to_write = {}
    if getattr(args, 'issue_id', None) is not None:
        print_info(f"Fetching metadata from ComicVine for issue ID: {args.issue_id}...")
        issue_params = {} 
        cv_api_response = make_comicvine_api_request(f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.issue_id}/", issue_params)
        if cv_api_response and cv_api_response.get('results'):
            cv_issue_details = cv_api_response.get('results')
            print_info("  Successfully fetched data from ComicVine.")
            comic_info_data_to_write = map_cv_to_comicinfo_dict(cv_issue_details, target_lang_code=target_lang) # Pass lang
            if not comic_info_data_to_write: print_error("  Could not map ComicVine data. No data to tag."); return False
        else: print_error(f"  Failed to fetch data for issue ID {args.issue_id}."); return False
    elif getattr(args, 'from_file', None) is not None:
        metadata_file_path = os.path.abspath(os.path.expanduser(args.from_file))
        print_info(f"Loading metadata from file: {metadata_file_path}...")
        if not os.path.isfile(metadata_file_path): print_error(f"  Metadata file not found: {metadata_file_path}"); return False
        try:
            with open(metadata_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f) 
                if not isinstance(loaded_data, dict): print_error(f"  Metadata file {args.from_file} not a valid JSON object."); return False
                # If translating from local file, ensure values are strings before potential translation
                # Translation from local file is more complex: which fields to translate? Assume pre-translated or only specific fields.
                # For now, if --translate is on, it will try to translate *values from the JSON file*.
                temp_data_for_translation = {k: str(v) if v is not None else "" for k, v in loaded_data.items()}
                if target_lang and TRANSLATOR_AVAILABLE:
                    print_info(f"  Applying translation to '{target_lang}' for loaded JSON data (Title, Summary, Notes, Genre)...")
                    for field in ['Title', 'Summary', 'Notes', 'Genre']: # Example fields to translate from local JSON
                        if field in temp_data_for_translation and temp_data_for_translation[field]:
                            temp_data_for_translation[field] = translate_text(temp_data_for_translation[field], target_language_code=target_lang)
                comic_info_data_to_write = {k: str(v) if v is not None else None for k, v in temp_data_for_translation.items()}
                print_info(f"  Successfully loaded metadata from {args.from_file}.")
        except json.JSONDecodeError: print_error(f"  Invalid JSON in metadata file: {args.from_file}"); return False
        except Exception as e: print_error(f"  Could not process metadata file {args.from_file}: {e}"); return False
    else: print_error("  No metadata source (issue_id or from_file) provided for tagging."); return False

    if not comic_info_data_to_write: print_info("No metadata to write. Tagging skipped."); return False
    tagging_successful = write_comic_info_to_cbz(cbz_file_path, comic_info_data_to_write, overwrite_all=getattr(args, 'overwrite_all', False))
    if not tagging_successful: print_error("  Tagging operation failed. File will not be renamed."); return False

    if getattr(args, 'rename', False):
        print_info(f"  Rename requested. Generating new filename...")
        original_dir = os.path.dirname(cbz_file_path); _, original_ext = os.path.splitext(cbz_file_path) 
        # IMPORTANT: Use the *final potentially translated* data for renaming
        new_base_filename_str = _generate_new_filename(comic_info_data_to_write, original_ext) 
        if new_base_filename_str:
            new_file_path = os.path.join(original_dir, new_base_filename_str)
            if os.path.abspath(new_file_path).lower() == os.path.abspath(cbz_file_path).lower():
                print_info(f"  Generated filename is same as original. No rename needed: {new_base_filename_str}")
            elif os.path.exists(new_file_path): print_error(f"  Rename failed: Target '{new_base_filename_str}' already exists in {original_dir}")
            else:
                try:
                    print_info(f"  Attempting to rename '{os.path.basename(cbz_file_path)}' to '{new_base_filename_str}'")
                    shutil.move(cbz_file_path, new_file_path)
                    print_success(f"  File successfully renamed to: {new_base_filename_str}")
                except Exception as e: print_error(f"  Failed to rename file to '{new_base_filename_str}': {e}")
        else: print_info("  Could not generate new filename from metadata. File not renamed.")
    return True

# --- Main Dispatcher for 'tag' command actions ---
def handle_tagging_dispatch(args):
    """Dispatches to tag, erase, or check based on flags for a single CBZ file."""
    cbz_file_path_abs = os.path.abspath(os.path.expanduser(args.cbz_file_path))
    if not os.path.isfile(cbz_file_path_abs) or not cbz_file_path_abs.lower().endswith(".cbz"):
        print_error(f"Invalid CBZ file path: {cbz_file_path_abs}. Must be an existing .cbz file.")
        return

    if getattr(args, 'check', False):
        from inspect_files import handle_check as perform_check_on_file 
        class CheckArgs:
            def __init__(self, path_list): self.paths = path_list # Expects a list
        perform_check_on_file(CheckArgs([cbz_file_path_abs])) 
    elif getattr(args, 'erase', False):
        print_header_line(f"Erasing Tags: {os.path.basename(cbz_file_path_abs)}", color=Style.RED)
        print_info(f"  File: {cbz_file_path_abs}")
        if getattr(args, 'issue_id', None) or getattr(args, 'from_file', None):
            print_info("  --issue-id and --from-file flags are ignored when --erase is used.")
        erase_comic_info_from_cbz(cbz_file_path_abs)
    elif getattr(args, 'issue_id', None) is not None or getattr(args, 'from_file', None) is not None:
        _perform_actual_tagging_and_rename(args, cbz_file_path_abs)
    else:
        print_error("No valid action (tag, erase, check) or metadata source specified for the 'tag' command.")