#!/usr/bin/env python3

import requests
import json
import sys 
import time
import os 

# Import configurations and utilities
from config import (
    CV_API_KEY, CV_BASE_URL, CV_USER_AGENT,
    CV_REQUEST_TIMEOUT, CV_RATE_LIMIT_WAIT_SECONDS, CV_MAX_RETRIES,
    CV_VOLUME_PREFIX, CV_ISSUE_PREFIX, CV_PERSON_PREFIX,
    CV_CHARACTER_PREFIX, CV_TEAM_PREFIX, CV_LOCATION_PREFIX,
    CV_STORY_ARC_PREFIX, CV_CONCEPT_PREFIX, CV_OBJECT_PREFIX
)
from utils import (
    Style, print_error, print_info,
    strip_html, make_clickable_link,
    print_header_line, print_field, print_multiline_text
)
import natsort # For sorting issues within a volume

# --- API Request Function ---
def make_comicvine_api_request(url, params):
    """
    Makes a request to the Comic Vine API, handling common errors and rate limiting.
    """
    headers = {'User-Agent': CV_USER_AGENT, 'Accept': 'application/json'}
    params['api_key'] = CV_API_KEY 
    params['format'] = 'json'  

    retries = 0
    while retries <= CV_MAX_RETRIES:
        try:
            logged_params = {k: v for k, v in params.items() if k != 'api_key'}
            request_details = f"URL: {url}, Params: {logged_params}"
            
            response = requests.get(url, headers=headers, params=params, timeout=CV_REQUEST_TIMEOUT)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('error') == "OK":
                        return data
                    else:
                        cv_status_code = data.get('status_code')
                        error_message = data.get('error', 'Unknown API error')
                        if cv_status_code == 101:
                            print_error(f"ComicVine API: Object not found. ({error_message}). {request_details}")
                        elif "Invalid API Key" in error_message:
                            print_error(f"ComicVine API: Invalid API Key. Please check your configuration. {request_details}")
                        else:
                            print_error(f"ComicVine API returned an error: {error_message} (Status: {cv_status_code}). {request_details}")
                        return None
                except json.JSONDecodeError:
                    print_error(f"Failed to decode JSON response from ComicVine. {request_details}. Response text: {response.text[:200]}...")
                    return None
                except Exception as e:
                    print_error(f"Unexpected error processing ComicVine response: {e}. {request_details}")
                    return None
            elif response.status_code == 401:
                print_error(f"ComicVine API Unauthorized (401). Check your CV_API_KEY. {request_details}")
                return None
            elif response.status_code == 404:
                print_error(f"ComicVine API Resource not found (404). {request_details}")
                return None
            elif response.status_code == 429:
                print_error(f"ComicVine API Rate limit exceeded (429). Waiting {CV_RATE_LIMIT_WAIT_SECONDS}s before retry ({retries + 1}/{CV_MAX_RETRIES})... {request_details}")
                if retries < CV_MAX_RETRIES:
                    time.sleep(CV_RATE_LIMIT_WAIT_SECONDS)
                    retries += 1
                    continue
                else:
                    print_error("Maximum retries reached for ComicVine API rate limiting.")
                    return None
            else:
                print_error(f"Received unexpected HTTP status code {response.status_code} from ComicVine. {request_details}")
                print_error(f"Response: {response.text[:200]}...")
                return None
        except requests.exceptions.Timeout:
            print_error(f"ComicVine API Request timed out after {CV_REQUEST_TIMEOUT} seconds. {request_details}")
            return None
        except requests.exceptions.RequestException as e:
            print_error(f"Network error during ComicVine API request: {e}. {request_details}")
            return None
        except Exception as e:
             print_error(f"An unexpected error occurred during the ComicVine API request: {e}. {request_details}")
             return None

    print_error("ComicVine API request failed after multiple attempts.")
    return None

# --- Display Functions for Fetched Data ---

def display_volume_search_results(results_list):
    if not results_list: print_info("No volumes found matching your criteria."); return
    print_header_line(f"Found {len(results_list)} Volume(s)")
    for i, volume in enumerate(results_list):
        print(f"\n{Style.BOLD}{Style.YELLOW}--- Result {i+1} ---{Style.RESET}")
        print_field("Name:", volume.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
        print_field("ID:", volume.get('id'), value_color=Style.WHITE)
        if volume.get('publisher') and isinstance(volume['publisher'], dict): 
            print_field("Publisher:", volume['publisher'].get('name'), value_color=Style.WHITE)
        elif isinstance(volume.get('publisher'), str):
             print_field("Publisher:", volume.get('publisher'), value_color=Style.WHITE)
        print_field("Start Year:", volume.get('start_year'), value_color=Style.WHITE)
        print_field("Total Issues:", volume.get('count_of_issues'), value_color=Style.WHITE)
        if volume.get('description'):
            print_multiline_text("Description:", volume.get('description'))
        if volume.get('site_detail_url'): print_field("ComicVine URL:", volume.get('site_detail_url'), is_url=True)
        if volume.get('image') and isinstance(volume.get('image'), dict) and volume['image'].get('thumb_url'): 
            print_field("Cover (thumb):", volume['image']['thumb_url'], is_url=True)
        issues_in_volume = volume.get('issues', []) # For --include-issues
        if issues_in_volume and isinstance(issues_in_volume, list):
            print(f"  {Style.BOLD}{Style.GREEN}{'Issues in this Volume':<20}{Style.RESET} ({len(issues_in_volume)} found)")
            for issue in sorted(issues_in_volume, key=lambda x: natsort.natsort_keygen()(str(x.get('issue_number', '0')))):
                name_display = issue.get('name') if issue.get('name') else f"Issue #{issue.get('issue_number', 'N/A')}"
                print_field(f"#{issue.get('issue_number', '?')}:", name_display, indent=1, value_color=Style.WHITE)
                print_field("ID:", issue.get('id'), indent=2, value_color=Style.WHITE)
                if issue.get('site_detail_url'): 
                    print_field("URL:", issue.get('site_detail_url'), is_url=True, indent=2)
                elif issue.get('api_detail_url'):
                    print_field("API URL:", issue.get('api_detail_url'), is_url=True, indent=2)

def display_volume_details(volume_data):
    print_header_line(f"Volume: {volume_data.get('name', 'N/A')}")
    print_field("Name:", volume_data.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
    print_field("ID:", volume_data.get('id'), value_color=Style.WHITE)
    if volume_data.get('publisher') and isinstance(volume_data['publisher'], dict): 
        print_field("Publisher:", volume_data['publisher'].get('name'), value_color=Style.WHITE)
    print_field("Start Year:", volume_data.get('start_year'), value_color=Style.WHITE)
    print_field("Total Issues:", volume_data.get('count_of_issues'), value_color=Style.WHITE)
    print_multiline_text("Description:", volume_data.get('description'))
    print_field("Last Updated:", volume_data.get('date_last_updated'), value_color=Style.WHITE)
    if volume_data.get('site_detail_url'): print_field("ComicVine URL:", volume_data.get('site_detail_url'), is_url=True)
    if volume_data.get('image') and isinstance(volume_data.get('image'), dict) and volume_data['image'].get('small_url'): 
        print_field("Cover (small):", volume_data['image']['small_url'], is_url=True)

    people_associated = volume_data.get('people')
    if people_associated and isinstance(people_associated, list) and len(people_associated) > 0:
        print(f"\n  {Style.BOLD}{Style.CYAN}{'People Associated with Volume:':<28}{Style.RESET} " 
              f"({Style.BRIGHT_BLACK}Roles per issue may vary{Style.RESET})")
        for person in sorted(people_associated, key=lambda x: (x.get('name') or '').lower()):
            name = person.get('name', 'N/A'); person_id = person.get('id')
            url = person.get('site_detail_url') or person.get('api_detail_url')
            issue_count_for_person = person.get('count', '') 
            id_display = f" (ID: {person_id})" if person_id else ""; count_display = f" [{issue_count_for_person} issue(s)]" if issue_count_for_person else ""
            display_text = f"{name}{id_display}{count_display}"
            if url: print_field("  •", make_clickable_link(url, display_text), indent=1, label_color=Style.CYAN, label_width=3)
            else: print_field("  •", display_text, indent=1, value_color=Style.WHITE, label_color=Style.CYAN, label_width=3)

    issues = volume_data.get('issues', [])
    if issues:
        print(f"\n  {Style.BOLD}{Style.GREEN}{'Issues':<18}{Style.RESET} ({len(issues)} found)")
        for issue in sorted(issues, key=lambda x: natsort.natsort_keygen()(str(x.get('issue_number', '0')))):
            name_display = issue.get('name') if issue.get('name') else f"Issue #{issue.get('issue_number', 'N/A')}"
            print_field(f"#{issue.get('issue_number', '?')}:", name_display, indent=1, value_color=Style.WHITE)
            print_field("ID:", issue.get('id'), indent=2, value_color=Style.WHITE)
            if issue.get('site_detail_url'): print_field("URL:", issue.get('site_detail_url'), is_url=True, indent=2)

def display_issue_details_summary(issue_data):
    issue_api_name = issue_data.get('name')
    issue_title_display = issue_api_name if issue_api_name else f"Issue #{issue_data.get('issue_number', 'N/A')}"
    if not issue_api_name and issue_data.get('volume') and issue_data.get('volume', {}).get('name'):
        issue_title_display = f"{issue_data.get('volume', {}).get('name')} #{issue_data.get('issue_number', 'N/A')}"

    print_header_line(f"Issue Summary: {issue_title_display}", color=Style.GREEN)
    print_field("Title:", issue_data.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
    print_field("Issue Num:", issue_data.get('issue_number'), value_color=Style.WHITE)
    print_field("ID:", issue_data.get('id'), value_color=Style.WHITE)
    volume_info = issue_data.get('volume')
    if volume_info:
        vol_display_name = f"{volume_info.get('name', 'N/A')} (ID: {volume_info.get('id', 'N/A')})"
        print_field("Volume:", vol_display_name, value_color=Style.WHITE)
        if volume_info.get('site_detail_url'): print_field("  Vol URL:", volume_info.get('site_detail_url'), is_url=True, label_color=Style.BRIGHT_BLACK)
    print_field("Cover Date:", issue_data.get('cover_date'), value_color=Style.WHITE)
    print_multiline_text("Description:", issue_data.get('description'), indent=0)
    if issue_data.get('site_detail_url'): print_field("ComicVine URL:", issue_data.get('site_detail_url'), is_url=True)
    person_credits = issue_data.get('person_credits', [])
    if person_credits:
        writers = [p.get('name') for p in person_credits if p.get('name') and 'writer' in (p.get('role') or '').lower()]
        artists = [p.get('name') for p in person_credits if p.get('name') and any(role_part in (p.get('role') or '').lower() for role_part in ['penciler', 'artist', 'inker', 'cover'])]
        if writers: print_field("Writer(s):", ", ".join(sorted(list(set(writers)))), value_color=Style.WHITE)
        if artists: print_field("Artist(s):", ", ".join(sorted(list(set(artists)))), value_color=Style.WHITE)
    print(f"\n{Style.BRIGHT_BLACK}Info: For full details, use the --verbose flag.{Style.RESET}")

def display_issue_details_verbose(issue_data):
    issue_api_name = issue_data.get('name')
    issue_title_display = issue_api_name if issue_api_name else f"Issue #{issue_data.get('issue_number', 'N/A')}"
    if not issue_api_name and issue_data.get('volume') and issue_data.get('volume', {}).get('name'):
        issue_title_display = f"{issue_data.get('volume', {}).get('name')} #{issue_data.get('issue_number', 'N/A')}"
    print_header_line(f"Issue (Verbose): {issue_title_display}", color=Style.GREEN)
    print_field("Title:", issue_data.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
    print_field("Issue Num:", issue_data.get('issue_number'), value_color=Style.WHITE)
    print_field("ID:", issue_data.get('id'), value_color=Style.WHITE)
    aliases = issue_data.get('aliases')
    if aliases:
        aliases_display = "\n".join(aliases) if isinstance(aliases, list) else (aliases if isinstance(aliases, str) else None)
        if aliases_display: print_multiline_text("Aliases:", aliases_display) 
    if issue_data.get('site_detail_url'): print_field("ComicVine URL:", issue_data.get('site_detail_url'), is_url=True)
    if issue_data.get('api_detail_url'): print_field("API Detail URL:", issue_data.get('api_detail_url'), is_url=True)
    volume_info = issue_data.get('volume')
    if volume_info:
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Volume Information:':<20}{Style.RESET}")
        vol_display_name = f"{volume_info.get('name', 'N/A')} (ID: {volume_info.get('id', 'N/A')})"
        print_field("Name:", vol_display_name, indent=1, value_color=Style.WHITE)
        if volume_info.get('site_detail_url'): print_field("URL:", volume_info.get('site_detail_url'), is_url=True, indent=1)
        elif volume_info.get('id'):
             vol_id_only_url = f"https://comicvine.gamespot.com/volume/{CV_VOLUME_PREFIX}{volume_info.get('id')}/"
             print_field("URL:", vol_id_only_url, is_url=True, indent=1, url_text=f"View Volume {volume_info.get('id')}")
        if volume_info.get('publisher') and isinstance(volume_info['publisher'], dict):
            print_field("Publisher:", volume_info['publisher'].get('name'), indent=1, value_color=Style.WHITE)
        if volume_info.get('start_year'): print_field("Start Year:", volume_info.get('start_year'), indent=1, value_color=Style.WHITE)
    print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Dates:':<20}{Style.RESET}")
    print_field("Cover Date:", issue_data.get('cover_date'), indent=1, value_color=Style.WHITE)
    print_field("Store Date:", issue_data.get('store_date'), indent=1, value_color=Style.WHITE)
    print_field("Date Added:", issue_data.get('date_added'), indent=1, value_color=Style.WHITE)
    print_field("Last Updated:", issue_data.get('date_last_updated'), indent=1, value_color=Style.WHITE)
    if issue_data.get('deck'): print_multiline_text("Deck (Summary):", issue_data.get('deck'), indent=0)
    print_multiline_text("Description:", issue_data.get('description'), indent=0)
    if 'has_staff_review' in issue_data:
        review_status = "Yes" if issue_data.get('has_staff_review') else "No"
        print_field("Has Staff Review:", review_status, value_color=Style.WHITE if issue_data.get('has_staff_review') else Style.BRIGHT_BLACK)
    image_obj = issue_data.get('image')
    if image_obj:
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Cover Image URLs:':<20}{Style.RESET}")
        image_sizes = [("Icon", "icon_url"), ("Tiny", "tiny_url"), ("Thumb", "thumb_url"),("Small", "small_url"), ("Medium", "medium_url"), ("Screen", "screen_url"),("Super", "super_url"), ("Screen Large", "screen_large_url"), ("Original", "original_url")]
        for name, key in image_sizes:
            if image_obj.get(key): print_field(f"{name}:", image_obj.get(key), indent=1, is_url=True, url_text=f"View {name.lower()}")
    assoc_images = issue_data.get('associated_images') 
    if assoc_images and isinstance(assoc_images, list) and len(assoc_images) > 0:
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Associated Images:':<20}{Style.RESET}")
        for idx, img_data in enumerate(assoc_images):
            img_url = img_data.get('original_url'); caption = img_data.get('caption'); tags = img_data.get('image_tags')
            if not img_url: continue
            display_text_parts = [caption if caption else f"Image {idx+1}"]
            if tags and tags.lower() != "all images": display_text_parts.append(f"({Style.BRIGHT_BLACK}Tags: {tags}{Style.RESET})")
            print_field(f"Image {idx+1}:", img_url, indent=1, is_url=True, url_text=" ".join(display_text_parts))
    credits_config = {
        'person_credits':      {'title': 'People / Creators', 'prefix': CV_PERSON_PREFIX, 'site_path_segment': 'person'}, 
        'character_credits':   {'title': 'Characters',        'prefix': CV_CHARACTER_PREFIX, 'site_path_segment': 'character'},
        'team_credits':        {'title': 'Teams',             'prefix': CV_TEAM_PREFIX, 'site_path_segment': 'team'}, 
        'location_credits':    {'title': 'Locations',         'prefix': CV_LOCATION_PREFIX, 'site_path_segment': 'location'},
        'concept_credits':     {'title': 'Concepts',          'prefix': CV_CONCEPT_PREFIX, 'site_path_segment': 'concept'}, 
        'object_credits':      {'title': 'Objects',           'prefix': CV_OBJECT_PREFIX, 'site_path_segment': 'object'},
        'story_arc_credits':   {'title': 'Story Arcs',        'prefix': CV_STORY_ARC_PREFIX, 'site_path_segment': 'story-arc'}
    }
    for credit_key, config_val in credits_config.items():
        credits_list = issue_data.get(credit_key)
        if credits_list and isinstance(credits_list, list) and len(credits_list) > 0:
            print(f"\n  {Style.BOLD}{Style.GREEN}{config_val['title']+':':<20}{Style.RESET}")
            sorter_key = (lambda x: ((x.get('role') or '').lower(), (x.get('name') or '').lower())) if credit_key == 'person_credits' else (lambda x: (x.get('name') or '').lower())
            for credit_item in sorted(credits_list, key=sorter_key):
                name = credit_item.get('name', 'N/A'); item_id = credit_item.get('id'); role_str = ""
                if credit_key == 'person_credits' and credit_item.get('role'):
                    roles = [r.strip().capitalize() for r in credit_item.get('role').split(',') if r.strip()]
                    role_str = f" ({Style.YELLOW}{', '.join(roles)}{Style.GREEN})"
                url = credit_item.get('site_detail_url') or credit_item.get('api_detail_url'); id_display = f" (ID: {item_id})" if item_id else ""; display_text = f"{name}{role_str}{id_display}"
                if url: print_field(" •", make_clickable_link(url, display_text), indent=1, label_color=Style.GREEN, label_width=3)
                else: print_field(" •", display_text, indent=1, value_color=Style.WHITE, label_color=Style.GREEN, label_width=3)
    appearance_death_fields = {
        'first_appearance_characters': "FA: Characters", 'first_appearance_concepts':   "FA: Concepts", 
        'first_appearance_locations':  "FA: Locations", 'first_appearance_objects':    "FA: Objects",
        'first_appearance_storyarcs':  "FA: Story Arcs", 'first_appearance_teams':      "FA: Teams", 
        'character_died_in':           "Deaths: Characters", 'team_disbanded_in':           "Disbanded: Teams"
    }
    for field_key, display_title in appearance_death_fields.items():
        data_list = issue_data.get(field_key)
        if data_list and isinstance(data_list, list) and len(data_list) > 0:
            print(f"\n  {Style.BOLD}{Style.MAGENTA}{display_title+':':<20}{Style.RESET}")
            for item in data_list:
                if isinstance(item, dict):
                    name = item.get('name', 'N/A'); item_id = item.get('id'); url = item.get('site_detail_url') or item.get('api_detail_url')
                    id_display = f" (ID: {item_id})" if item_id else ""; display_text = f"{name}{id_display}"
                    if url: print_field("  •", make_clickable_link(url, display_text), indent=1, label_color=Style.MAGENTA, label_width=3)
                    else: print_field("  •", display_text, indent=1, value_color=Style.WHITE, label_color=Style.MAGENTA, label_width=3)
                elif isinstance(item, str): print_field("  •", item, indent=1, value_color=Style.WHITE, label_color=Style.MAGENTA, label_width=3)
    print("")


# --- Main Handler for 'search' command ---
def handle_fetch_comicvine(args):
    params = {} 
    url = None
    mode = None 
    api_data_response = None 
    fetched_volumes_list_for_display = [] 

    # Safely access optional args from the args namespace
    cv_name_filter_val = getattr(args, 'cv_name_filter', None)
    cv_author_name_val = getattr(args, 'cv_author_name', None)
    cv_publisher_name_val = getattr(args, 'cv_publisher_name', None)
    cv_start_year_val = getattr(args, 'cv_start_year', None)
    cv_issues_count_val = getattr(args, 'cv_issues_count', None)
    include_issues_flag = getattr(args, 'include_issues', False)
    verbose_flag = getattr(args, 'verbose', False)

    # --- Determine Mode and Fetch Initial Data if applicable ---
    if args.get_volume:
        mode = 'volume_detail'
        url = f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{args.get_volume}/"
        params['field_list'] = 'id,name,issues,people,publisher(id|name|site_detail_url),start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
        print_info(f"Fetching details for volume ID: {args.get_volume} from ComicVine...")
        api_data_response = make_comicvine_api_request(url, params)
    
    elif args.get_issue:
        mode = 'issue_detail'
        url = f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.get_issue}/"
        # No 'field_list' for --get-issue to fetch all fields
        print_info(f"Fetching ALL available details for issue ID: {args.get_issue} from ComicVine...")
        api_data_response = make_comicvine_api_request(url, params)

    elif (cv_name_filter_val or cv_author_name_val or cv_start_year_val is not None or 
          cv_publisher_name_val or cv_issues_count_val is not None):
        
        if cv_author_name_val and not cv_name_filter_val: 
            mode = 'volume_search_author_first'
            print_info(f"Author name provided ('{cv_author_name_val}'). Performing person search first...")
            person_params = {'filter': f"name:{cv_author_name_val}", 'field_list': 'id,name,volumes'}
            person_data_response = make_comicvine_api_request(f"{CV_BASE_URL}people/", person_params)
            
            if not (person_data_response and person_data_response.get('results')):
                print_info(f"No person found matching '{cv_author_name_val}' or error fetching person.")
                # fetched_volumes_list_for_display remains empty
            else:
                if len(person_data_response['results']) > 1: print_info(f"Multiple people for '{cv_author_name_val}'. Using: {person_data_response['results'][0].get('name')}")
                person_result = person_data_response['results'][0]; volumes_on_person = person_result.get('volumes', [])
                print_info(f"Found {len(volumes_on_person)} volumes initially associated with {person_result.get('name', 'this person')}.")
                temp_filtered_volumes_summaries = []
                for vol_summary in volumes_on_person:
                    match = True 
                    if cv_name_filter_val and cv_name_filter_val.lower() not in (vol_summary.get('name') or "").lower(): match = False
                    if match: temp_filtered_volumes_summaries.append(vol_summary)
                
                max_details_fetch = 10 if not include_issues_flag else 5
                if include_issues_flag: print_info(f"Fetching issues for up to {max_details_fetch} volumes...")
                vols_to_fetch_details_for = temp_filtered_volumes_summaries[:max_details_fetch]
                if len(temp_filtered_volumes_summaries) > max_details_fetch: print_info(f"Limiting full detail fetch to first {max_details_fetch} of {len(temp_filtered_volumes_summaries)} potential volumes.")
                
                for vol_summary in vols_to_fetch_details_for:
                    vol_id_for_detail = vol_summary.get('id'); numeric_vol_id = str(vol_id_for_detail).split('-')[-1] if vol_id_for_detail else None
                    if not numeric_vol_id: continue
                    print_info(f"  Fetching details for volume: {vol_summary.get('name')} (ID: {numeric_vol_id})...")
                    detail_field_list = 'id,name,publisher,start_year,count_of_issues,description,image,site_detail_url'
                    if include_issues_flag: detail_field_list += ',issues' 
                    vol_detail_data = make_comicvine_api_request(f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{numeric_vol_id}/", {'field_list': detail_field_list})
                    time.sleep(0.25) # API courtesy
                    if vol_detail_data and vol_detail_data.get('results'):
                        full_vol_data = vol_detail_data['results']; match_final = True
                        if cv_publisher_name_val:
                            pub_data = full_vol_data.get('publisher')
                            if not (pub_data and isinstance(pub_data, dict) and cv_publisher_name_val.lower() in (pub_data.get('name') or "").lower()): match_final = False
                        if match_final and cv_start_year_val is not None and (str(full_vol_data.get('start_year')) != str(cv_start_year_val)): match_final = False
                        if match_final and cv_issues_count_val is not None and (full_vol_data.get('count_of_issues') != cv_issues_count_val): match_final = False
                        if match_final: fetched_volumes_list_for_display.append(full_vol_data)
        else: 
            mode = 'volume_search_standard'
            url = f"{CV_BASE_URL}volumes/"
            api_filters = []
            if cv_name_filter_val: api_filters.append(f"name:{cv_name_filter_val}")
            if cv_author_name_val: 
                api_filters.append(f"person:{cv_author_name_val}")
                print_info(f"API filter: Including volumes associated with person '{cv_author_name_val}'. This can be broad.")
            if cv_publisher_name_val: api_filters.append(f"publisher:{cv_publisher_name_val}")

            if api_filters: params['filter'] = ','.join(api_filters)
            else: print_info("Performing a broad volume search (no specific criteria given to API).")
            params['field_list'] = 'id,name,publisher,start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
            params['limit'] = 100
            params['sort'] = 'date_last_updated:desc' if (cv_author_name_val or cv_name_filter_val) else 'name:asc'
            print_info(f"Searching ComicVine volumes with API filters: {params.get('filter', 'None')}, Sort: {params.get('sort')}")
            
            api_data_response = make_comicvine_api_request(url, params) # Fetch data for this mode
    else:
        print_error("For a 'search' operation, please use --get-volume, --get-issue, or provide search criteria (e.g., --title, --author).")
        return 

    # --- Process and Display Data ---
    if mode == 'volume_detail':
        if api_data_response and api_data_response.get('results'):
            display_volume_details(api_data_response.get('results', {}))
        else:
            print_error("Failed to retrieve volume details.")
    elif mode == 'issue_detail':
        if api_data_response and api_data_response.get('results'):
            if verbose_flag: 
                display_issue_details_verbose(api_data_response.get('results', {}))
            else:
                display_issue_details_summary(api_data_response.get('results', {}))
        else:
            print_error("Failed to retrieve issue details.")
    elif mode == 'volume_search_author_first':
        if not fetched_volumes_list_for_display: 
             print_info("No volumes matched all criteria after author-first search and filtering.")
        display_volume_search_results(fetched_volumes_list_for_display)
    elif mode == 'volume_search_standard':
        if not (api_data_response and api_data_response.get('results')):
            print_info("No volumes found from API search.")
            display_volume_search_results([]) # Pass empty list to display function
            return # Added return
            
        current_search_results = api_data_response.get('results', [])
        
        needs_local_filtering = (cv_name_filter_val or cv_publisher_name_val or 
                                cv_start_year_val is not None or cv_issues_count_val is not None)

        if needs_local_filtering or cv_author_name_val: # For info message
            active_post_filters_display = []
            if cv_name_filter_val: active_post_filters_display.append("Title/Name (local contains)")
            if cv_publisher_name_val: active_post_filters_display.append("Publisher (local contains)")
            if cv_start_year_val is not None: active_post_filters_display.append("Year (local exact)")
            if cv_issues_count_val is not None: active_post_filters_display.append("Issues (local exact)")
            if cv_author_name_val: active_post_filters_display.append(f"Author '{cv_author_name_val}' (API filtered only)")
            if active_post_filters_display: 
                print_info(f"API results for standard search will be refined locally by: {', '.join(active_post_filters_display)}.")

        if needs_local_filtering:
            temp_locally_filtered = []
            name_search_term = cv_name_filter_val.lower() if cv_name_filter_val else None
            publisher_search_term = cv_publisher_name_val.lower() if cv_publisher_name_val else None
            for volume_item in current_search_results:
                match = True
                if name_search_term:
                    vol_name_lower = (volume_item.get('name') or "").lower()
                    vol_desc_text = strip_html((volume_item.get('description') or "").lower())
                    if not (name_search_term in vol_name_lower or name_search_term in vol_desc_text):
                        match = False
                if match and publisher_search_term:
                    pub_data = volume_item.get('publisher')
                    if not (pub_data and isinstance(pub_data, dict) and publisher_search_term in (pub_data.get('name') or "").lower()):
                        match = False
                if match and cv_start_year_val is not None:
                    vol_year_str = volume_item.get('start_year')
                    try:
                        if vol_year_str is None or str(vol_year_str).strip() == "" or int(vol_year_str) != cv_start_year_val: match = False
                    except (ValueError, TypeError): match = False
                if match and cv_issues_count_val is not None:
                     if (volume_item.get('count_of_issues') is None or volume_item.get('count_of_issues') != cv_issues_count_val): match = False
                if match: temp_locally_filtered.append(volume_item)
            fetched_volumes_list_for_display = temp_locally_filtered
        else:
            fetched_volumes_list_for_display = current_search_results # No local filtering, use as is
        
        if include_issues_flag and fetched_volumes_list_for_display:
            print_info(f"Fetching issue lists for up to {min(len(fetched_volumes_list_for_display), 5)} displayed volumes (due to --include-issues)...")
            volumes_to_get_issues_for = fetched_volumes_list_for_display[:5] 
            temp_volumes_with_issues = []
            for vol_summary_item in volumes_to_get_issues_for:
                vol_id_for_issues = vol_summary_item.get('id'); numeric_vol_id_for_issues = str(vol_id_for_issues).split('-')[-1] if vol_id_for_issues else None
                if not numeric_vol_id_for_issues: temp_volumes_with_issues.append(vol_summary_item); continue
                print_info(f"  Fetching issues for volume: {vol_summary_item.get('name')} (ID: {numeric_vol_id_for_issues})...")
                issues_data_resp = make_comicvine_api_request(f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{numeric_vol_id_for_issues}/", {'field_list': 'issues'})
                time.sleep(0.25)
                updated_vol_summary = dict(vol_summary_item) 
                if issues_data_resp and issues_data_resp.get('results') and issues_data_resp['results'].get('issues'):
                    updated_vol_summary['issues'] = issues_data_resp['results']['issues']
                else: updated_vol_summary['issues'] = []
                temp_volumes_with_issues.append(updated_vol_summary)
            fetched_volumes_list_for_display = temp_volumes_with_issues
        
        display_volume_search_results(fetched_volumes_list_for_display)
    
    # This final 'else' implies api_data_response was None for detail views, or some other unhandled case
    # Error messages should have been printed by make_comicvine_api_request or earlier logic.
    elif api_data_response is None and mode not in ['volume_search_author_first', 'volume_search_standard']:
        # This case should ideally not be reached if error handling within modes is complete
        print_error("No data was successfully fetched for the requested operation.")