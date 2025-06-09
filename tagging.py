#!/usr/bin/env python3

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

try:
    from translator import translate_text, logger as translator_logger
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print_info("Optional 'translator.py' module not found or import error. Translation feature will be disabled.")
    TRANSLATOR_AVAILABLE = False
    translator_logger = None
    def translate_text(text, target_lang_code=None, source_language_code=None):
        if target_lang_code and translator_logger:
            translator_logger.warning("Translation called but translator module is not available.")
        return text

def _generate_new_filename(metadata_dict, original_extension=".cbz"):
    series = metadata_dict.get('Series')
    volume_num_str = metadata_dict.get('Volume')
    number = metadata_dict.get('Number')
    year = metadata_dict.get('Year')
    title = metadata_dict.get('Title')
    parts = []

    if series: parts.append(sanitize_filename(series))
    if volume_num_str: parts.append(f"V{sanitize_filename(volume_num_str)}")
    if number:
        try:
            num_val = float(number)
            num_str = f"{int(num_val):03}" if num_val == int(num_val) else str(num_val)
        except ValueError:
            num_str = sanitize_filename(number)
        parts.append(f"#{num_str}")
    if year: parts.append(f"({sanitize_filename(str(year))})")
    if title and title.lower() != (series or "").lower() and \
       title.lower() != (f"issue #{number}".lower() if number else "") and \
       title.lower() != (f"#{number}".lower() if number else ""):
        sanitized_title = sanitize_filename(title)
        if sanitized_title: parts.append(f"- {sanitized_title}")
    
    if not parts: return None
    return f"{' '.join(parts)}{original_extension}"

def map_cv_to_comicinfo_dict(cv_issue_data, target_lang_code=None):
    """
    Maps ComicVine data to a ComicInfo dictionary.
    Translation is limited to description-related fields.
    """
    if not cv_issue_data: return {}
    info = {}

    def _translate_if_needed(text_field_value, field_name_for_log="text"):
        # This helper is now only called for specific fields
        if target_lang_code and TRANSLATOR_AVAILABLE and text_field_value:
            print_info(f"  Translating '{field_name_for_log}' to '{target_lang_code}'...")
            return translate_text(text_field_value, target_language_code=target_lang_code)
        return text_field_value

    # --- Fields that are NEVER translated ---
    info['Title'] = cv_issue_data.get('name')
    if cv_issue_data.get('issue_number'): info['Number'] = cv_issue_data.get('issue_number')
    if cv_issue_data.get('site_detail_url'): info['Web'] = cv_issue_data['site_detail_url']
    if cv_issue_data.get('aliases'): info['Notes'] = (info.get('Notes', '') + f"\nAliases:\n{strip_html(cv_issue_data['aliases'])}").strip()

    # Date parsing logic
    if cv_issue_data.get('cover_date'):
        try:
            date_str = cv_issue_data['cover_date']
            parsed_successfully = False
            if date_str:
                if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
                    actual_date_part = date_str.split(' ')[0]
                    cover_dt = datetime.strptime(actual_date_part, '%Y-%m-%d')
                    info['Year'], info['Month'], info['Day'] = str(cover_dt.year), str(cover_dt.month), str(cover_dt.day)
                    parsed_successfully = True
                elif len(date_str) == 7 and date_str[4] == '-':
                    cover_dt = datetime.strptime(date_str, '%Y-%m')
                    info['Year'], info['Month'] = str(cover_dt.year), str(cover_dt.month)
                    parsed_successfully = True
                elif len(date_str) == 4 and date_str.isdigit():
                    info['Year'] = date_str
                    parsed_successfully = True
            if not parsed_successfully and date_str: print_info(f"  Could not parse cover_date '{date_str}'")
        except (ValueError, TypeError) as e: print_info(f"  Warning parsing cover_date: {e}")

    if cv_issue_data.get('store_date') and cv_issue_data.get('store_date') != cv_issue_data.get('cover_date'):
         info['Notes'] = (info.get('Notes', '') + f"\nStore Date: {cv_issue_data['store_date']}").strip()

    # --- Fields that CAN be translated ---
    raw_description = cv_issue_data.get('description')
    if raw_description: 
        cleaned_description = strip_html(raw_description)
        info['Summary'] = _translate_if_needed(cleaned_description, "Summary (Description)")
    
    raw_deck = cv_issue_data.get('deck')
    if raw_deck: 
        cleaned_deck = strip_html(raw_deck)
        # We translate the deck and add it to notes, as it's a secondary description
        translated_deck = _translate_if_needed(cleaned_deck, "Deck")
        if translated_deck:
             info['Notes'] = (info.get('Notes', '') + f"\nDeck (Summary): {translated_deck}").strip()

    # --- Volume and Publisher (NOT translated) ---
    volume = cv_issue_data.get('volume')
    if volume and isinstance(volume, dict):
        info['Series'] = volume.get('name') # No translation
        if volume.get('publisher') and isinstance(volume['publisher'], dict):
            info['Publisher'] = volume['publisher'].get('name') # No translation
        if volume.get('count_of_issues') is not None: info['Count'] = str(volume.get('count_of_issues'))
        if volume.get('start_year') and 'Year' not in info: info['Year'] = str(volume.get('start_year'))
    
    # --- Credits (Names are NOT translated) ---
    person_credits = cv_issue_data.get('person_credits', [])
    person_roles_map = {'writer': 'Writer', 'penciler': 'Penciller', 'inker': 'Inker', 'colorist': 'Colorist', 'letterer': 'Letterer', 'cover': 'CoverArtist', 'artist': 'Artist', 'editor': 'Editor', 'plotter': 'Writer', 'scripter': 'Writer'}
    generic_art_roles = ['art', 'colors', 'letters', 'pencils', 'inks']
    temp_credits_by_ci_tag = {}
    if isinstance(person_credits, list):
        for person in person_credits:
            name = person.get('name')
            if not name: continue
            cv_person_roles_str = (person.get('role') or '').lower()
            roles_assigned = set()
            for cv_role, ci_tag in person_roles_map.items():
                if cv_role in cv_person_roles_str:
                    if ci_tag not in temp_credits_by_ci_tag: temp_credits_by_ci_tag[ci_tag] = set()
                    temp_credits_by_ci_tag[ci_tag].add(name)
                    roles_assigned.add(ci_tag)
            if not any(art_role in roles_assigned for art_role in ['Penciller', 'Inker', 'Colorist', 'CoverArtist']):
                for art_term in generic_art_roles:
                    if art_term in cv_person_roles_str:
                        if 'Artist' not in temp_credits_by_ci_tag: temp_credits_by_ci_tag['Artist'] = set()
                        temp_credits_by_ci_tag['Artist'].add(name)
                        break
    for ci_tag, names_set in temp_credits_by_ci_tag.items():
        if names_set: info[ci_tag] = ", ".join(sorted(list(names_set)))

    def map_generic_credits_list(cv_key, comic_info_tag):
        items = cv_issue_data.get(cv_key)
        if items and isinstance(items, list):
            names = sorted(list(set([item.get('name') for item in items if item.get('name')])))
            if names: info[comic_info_tag] = ", ".join(names)
    
    # Credits like Characters, Teams, Concepts, Objects are NOT translated
    map_generic_credits_list('character_credits', 'Characters')
    map_generic_credits_list('team_credits', 'Teams')
    map_generic_credits_list('location_credits', 'Locations')
    map_generic_credits_list('story_arc_credits', 'StoryArc')
    
    concepts = cv_issue_data.get('concept_credits')
    if concepts and isinstance(concepts, list):
        concept_names = sorted(list(set([c.get('name') for c in concepts if c.get('name')])))
        if concept_names:
            existing_genre = set([g.strip() for g in info.get('Genre', '').split(',') if g.strip()])
            for cn in concept_names: existing_genre.add(cn)
            info['Genre'] = ", ".join(sorted(list(existing_genre)))

    objects = cv_issue_data.get('object_credits')
    if objects and isinstance(objects, list):
        object_names = sorted(list(set([o.get('name') for o in objects if o.get('name')])))
        if object_names:
            info['Notes'] = (info.get('Notes', '') + f"\nObjects: {', '.join(object_names)}").strip()
    
    info.setdefault('LanguageISO', target_lang_code if target_lang_code and TRANSLATOR_AVAILABLE else 'en')
    info.setdefault('Format', 'Comic')

    return {k: v for k, v in info.items() if v is not None and str(v).strip() != ""}

# Reszta pliku tagging.py pozostaje bez zmian.
# ... (create_comic_info_xml_element, write_comic_info_to_cbz, etc.)

def create_comic_info_xml_element(metadata_dict):
    root = ET.Element("ComicInfo")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
    tag_order = [
        "Title", "Series", "Number", "Count", "Volume", "AlternateSeries", "AlternateNumber", "AlternateCount", 
        "Summary", "Notes", "Year", "Month", "Day", "Writer", "Penciller", "Inker", "Colorist", "Letterer", 
        "CoverArtist", "Editor", "Artist", "Publisher", "Imprint", "Genre", "Web", "PageCount", "LanguageISO", 
        "Format", "BlackAndWhite", "Manga", "Characters", "Teams", "Locations", "StoryArc", "SeriesGroup", 
        "AgeRating", "ScanInformation"
    ]
    processed_tags = set()
    for tag_name in tag_order:
        if tag_name in metadata_dict and metadata_dict[tag_name] is not None:
            ET.SubElement(root, tag_name).text = str(metadata_dict[tag_name])
            processed_tags.add(tag_name)
    for tag_name, value in metadata_dict.items():
        if tag_name not in processed_tags and value is not None:
            ET.SubElement(root, tag_name).text = str(value)
    return root

def write_comic_info_to_cbz(cbz_path, comic_info_metadata, overwrite_all=False):
    comic_info_filename = "ComicInfo.xml"
    temp_zip_path = None
    temp_fd = -1
    try:
        existing_comic_info_root = None
        if not overwrite_all:
            try:
                with zipfile.ZipFile(cbz_path, 'r') as zf_read:
                    if comic_info_filename in zf_read.namelist():
                        with zf_read.open(comic_info_filename) as xml_file:
                            try:
                                existing_comic_info_root = ET.parse(xml_file).getroot()
                                print_info(f"  Found existing {comic_info_filename}. Merging tags.")
                            except ET.ParseError:
                                print_error(f"  Existing {comic_info_filename} is corrupted. Overwriting.")
            except Exception as e:
                print_error(f"  Error reading existing CBZ for merge: {e}")
        
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

        if sys.version_info.major == 3 and sys.version_info.minor >= 9:
            ET.indent(final_xml_root, space="\t")
        xml_bytes = ET.tostring(final_xml_root, encoding='utf-8', xml_declaration=True, short_empty_elements=False)

        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_tag_")
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            compression_level = zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=compression_level) as zout:
                for item in zin.infolist():
                    if item.filename.lower() != comic_info_filename.lower():
                        zout.writestr(item, zin.read(item.filename))
                zout.writestr(comic_info_filename, xml_bytes) 
        
        os.close(temp_fd)
        temp_fd = -1
        shutil.move(temp_zip_path, cbz_path)
        temp_zip_path = None
        
        print_success(f"  Successfully wrote {comic_info_filename} to {os.path.basename(cbz_path)}")
        return True, cbz_path
    except Exception as e:
        print_error(f"  Failed to write {comic_info_filename} to {os.path.basename(cbz_path)}: {e}")
        return False, cbz_path
    finally:
        if temp_fd != -1 and temp_fd is not None: os.close(temp_fd)
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)

def erase_comic_info_from_cbz(cbz_path):
    comic_info_filename_lower = "comicinfo.xml"
    temp_zip_path = None
    temp_fd = -1
    xml_existed = False
    try:
        with zipfile.ZipFile(cbz_path, 'r') as zin_check:
            if any(name.lower() == comic_info_filename_lower for name in zin_check.namelist()):
                xml_existed = True
        if not xml_existed:
            print_info(f"  ComicInfo.xml not found in {os.path.basename(cbz_path)}. No erase needed.")
            return True
    except Exception as e:
        print_error(f"  Error checking CBZ {os.path.basename(cbz_path)}: {e}")
        return False
    
    print_info(f"  Attempting to erase ComicInfo.xml from {os.path.basename(cbz_path)}...")
    try:
        temp_fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="cbz_erase_")
        with zipfile.ZipFile(cbz_path, 'r') as zin:
            compression_level = zin.infolist()[0].compress_type if zin.infolist() else zipfile.ZIP_DEFLATED
            with zipfile.ZipFile(temp_zip_path, 'w', zin.compression, compresslevel=compression_level) as zout:
                for item in zin.infolist():
                    if item.filename.lower() != comic_info_filename_lower:
                        zout.writestr(item, zin.read(item.filename))
        
        os.close(temp_fd); temp_fd = -1
        shutil.move(temp_zip_path, cbz_path); temp_zip_path = None
        print_success(f"  Successfully erased ComicInfo.xml from {os.path.basename(cbz_path)}.")
        return True
    except Exception as e:
        print_error(f"  Failed to erase ComicInfo.xml from {os.path.basename(cbz_path)}: {e}")
        return False
    finally:
        if temp_fd != -1: os.close(temp_fd)
        if temp_zip_path and os.path.exists(temp_zip_path): os.remove(temp_zip_path)

def _perform_actual_tagging_and_rename(args, cbz_file_path):
    print_header_line(f"Tagging Operation: {os.path.basename(cbz_file_path)}", color=Style.GREEN)
    print_info(f"  File path: {cbz_file_path}")
    
    target_lang = getattr(args, 'translate', None)
    if target_lang and not TRANSLATOR_AVAILABLE:
        print_error("  Translation requested but translator module is not available/configured. Proceeding without translation.")
        target_lang = None
    elif target_lang:
        print_info(f"  Translation to '{target_lang}' requested for description.")

    comic_info_data_to_write = {}
    if getattr(args, 'issue_id', None) is not None:
        print_info(f"Fetching metadata from ComicVine for issue ID: {args.issue_id}...")
        cv_api_response = make_comicvine_api_request(f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.issue_id}/", {})
        if cv_api_response and cv_api_response.get('results'):
            print_info("  Successfully fetched data from ComicVine.")
            comic_info_data_to_write = map_cv_to_comicinfo_dict(cv_api_response.get('results'), target_lang_code=target_lang)
            if not comic_info_data_to_write:
                print_error("  Could not map ComicVine data. No data to tag.")
                return False, cbz_file_path
        else:
            print_error(f"  Failed to fetch data for issue ID {args.issue_id}.")
            return False, cbz_file_path
    elif getattr(args, 'from_file', None) is not None:
        # This part remains the same, assuming local JSON files are manually managed.
        # ...
        pass
    else:
        print_error("  No metadata source provided for tagging.")
        return False, cbz_file_path

    if not comic_info_data_to_write:
        print_info("No metadata to write. Tagging skipped.")
        return False, cbz_file_path
    
    tagging_successful, final_cbz_path = write_comic_info_to_cbz(cbz_file_path, comic_info_data_to_write, overwrite_all=getattr(args, 'overwrite_all', False))
    if not tagging_successful:
        print_error("  Tagging operation failed. File will not be renamed.")
        return False, final_cbz_path

    if getattr(args, 'rename', False):
        print_info("  Rename requested. Generating new filename...")
        original_dir = os.path.dirname(final_cbz_path)
        _, original_ext = os.path.splitext(final_cbz_path)
        new_base_filename = _generate_new_filename(comic_info_data_to_write, original_ext) 
        if new_base_filename:
            new_file_path = os.path.join(original_dir, new_base_filename)
            if os.path.abspath(new_file_path).lower() == os.path.abspath(final_cbz_path).lower():
                print_info("  Generated filename is the same as the original. No rename needed.")
            elif os.path.exists(new_file_path):
                print_error(f"  Rename failed: Target '{new_base_filename}' already exists.")
            else:
                try:
                    print_info(f"  Attempting to rename '{os.path.basename(final_cbz_path)}' to '{new_base_filename}'")
                    shutil.move(final_cbz_path, new_file_path)
                    print_success(f"  File successfully renamed to: {new_base_filename}")
                    return True, new_file_path # Return success and NEW path
                except Exception as e:
                    print_error(f"  Failed to rename file: {e}")
                    return True, final_cbz_path # Tagging was success, rename failed, return original path
        else:
            print_info("  Could not generate new filename. File not renamed.")
    
    return True, final_cbz_path # Return success and the (possibly unchanged) file path

def handle_tagging_dispatch(args):
    cbz_file_path_abs = os.path.abspath(os.path.expanduser(args.cbz_file_path))
    if not os.path.isfile(cbz_file_path_abs):
        print_error(f"Invalid CBZ file path: {cbz_file_path_abs}.")
        return False, args.cbz_file_path

    if getattr(args, 'erase', False):
        print_header_line(f"Erasing Tags: {os.path.basename(cbz_file_path_abs)}", color=Style.RED)
        success = erase_comic_info_from_cbz(cbz_file_path_abs)
        return success, cbz_file_path_abs # Path does not change on erase
    elif getattr(args, 'issue_id', None) is not None or getattr(args, 'from_file', None) is not None:
        return _perform_actual_tagging_and_rename(args, cbz_file_path_abs)
    else:
        print_error("No valid action specified for the 'tag' command.")
        return False, cbz_file_path_abs