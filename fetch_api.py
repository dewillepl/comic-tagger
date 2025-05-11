#!/usr/bin/env python3

import requests
import json
import sys 
import time
import os 

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
import natsort

# --- API Request Function (make_comicvine_api_request - remains the same) ---
# ... (copy from previous version) ...
def make_comicvine_api_request(url, params):
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


# --- Display Functions (display_volume_search_results, display_volume_details, etc. - remain the same) ---
# ... (copy from previous version) ...
def display_volume_search_results(results_list): # Used for displaying list of volumes
    if not results_list: print_info("No volumes found matching your criteria."); return
    print_header_line(f"Found {len(results_list)} Volume(s)")
    for i, volume in enumerate(results_list):
        print(f"\n{Style.BOLD}{Style.YELLOW}--- Result {i+1} ---{Style.RESET}")
        print_field("Name:", volume.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
        print_field("ID:", volume.get('id'), value_color=Style.WHITE)
        # The volume objects from /people/ endpoint might not have publisher directly.
        # This display function needs to be robust to missing fields.
        if volume.get('publisher') and isinstance(volume['publisher'], dict): 
            print_field("Publisher:", volume['publisher'].get('name'), value_color=Style.WHITE)
        else: # If publisher is a string (might happen if we construct summary objects)
            print_field("Publisher:", volume.get('publisher'), value_color=Style.WHITE)

        print_field("Start Year:", volume.get('start_year'), value_color=Style.WHITE)
        print_field("Issues:", volume.get('count_of_issues'), value_color=Style.WHITE)
        print_multiline_text("Description:", volume.get('description')) # Might be null for summary
        if volume.get('site_detail_url'): print_field("ComicVine URL:", volume.get('site_detail_url'), is_url=True)
        if volume.get('image') and isinstance(volume.get('image'), dict) and volume['image'].get('thumb_url'): 
            print_field("Cover (thumb):", volume['image']['thumb_url'], is_url=True)

def display_volume_details(volume_data):
    # ... (as in previous full fetch_api.py) ...
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

    # Display people associated with this specific volume (from volume detail endpoint)
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
    # ... (as in previous full fetch_api.py) ...
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
    # ... (as in previous full fetch_api.py - the very comprehensive one) ...
    issue_api_name = issue_data.get('name')
    issue_title_display = issue_api_name if issue_api_name else f"Issue #{issue_data.get('issue_number', 'N/A')}"
    if not issue_api_name and issue_data.get('volume') and issue_data.get('volume', {}).get('name'):
        issue_title_display = f"{issue_data.get('volume', {}).get('name')} #{issue_data.get('issue_number', 'N/A')}"
    print_header_line(f"Issue (Verbose): {issue_title_display}", color=Style.GREEN)
    print_field("Title:", issue_data.get('name'), value_style=Style.BOLD, value_color=Style.WHITE) # ... (rest of this function)
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
                url = credit_item.get('site_detail_url') or credit_item.get('api_detail_url')
                id_display = f" (ID: {item_id})" if item_id else ""; display_text = f"{name}{role_str}{id_display}"
                if url: print_field(" •", make_clickable_link(url, display_text), indent=1, label_color=Style.GREEN, label_width=3)
                else: print_field(" •", display_text, indent=1, value_color=Style.WHITE, label_color=Style.GREEN, label_width=3)
    appearance_death_fields = {
        'first_appearance_characters': "First Appearance: Characters", 'first_appearance_concepts':   "First Appearance: Concepts",
        'first_appearance_locations':  "First Appearance: Locations", 'first_appearance_objects':    "First Appearance: Objects",
        'first_appearance_storyarcs':  "First Appearance: Story Arcs", 'first_appearance_teams':      "First Appearance: Teams",
        'character_died_in':           "Character Deaths In Issue", 'team_disbanded_in':           "Team Disbanded In Issue"
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


# --- Main Handler for 'search' command (renamed from handle_fetch_comicvine) ---
def handle_fetch_comicvine(args):
    params = {} 
    url = None
    mode = None 
    needs_post_filtering = False # For local filtering of /volumes/ search

    # --- Mode 1: Get specific volume by ID ---
    if args.get_volume:
        mode = 'volume_detail' # More specific mode name
        url = f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{args.get_volume}/"
        # Request 'people' for the volume detail view
        params['field_list'] = 'id,name,issues,people,publisher(id|name|site_detail_url),start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
        print_info(f"Fetching details for volume ID: {args.get_volume} from ComicVine...")
    
    # --- Mode 2: Get specific issue by ID ---
    elif args.get_issue:
        mode = 'issue_detail' # More specific mode name
        url = f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.get_issue}/"
        # No 'field_list' in params for --get-issue. Fetches all default fields.
        print_info(f"Fetching ALL available details for issue ID: {args.get_issue} from ComicVine...")

    # --- Mode 3: Criteria-based volume search (this is the complex one) ---
    elif (args.cv_series_name or args.cv_title_desc or args.cv_author_name or 
          args.cv_start_year is not None or args.cv_publisher_name or args.cv_issues_count is not None):
        
        mode = 'volume_search' # More specific mode name
        
        # ** NEW TWO-STEP LOGIC FOR AUTHOR SEARCH **
        if args.cv_author_name and not (args.cv_series_name or args.cv_title_desc): 
            # If author is the primary/only significant text filter, search people first
            print_info(f"Author name provided ('{args.cv_author_name}'). Performing person search first for better accuracy...")
            person_params = {'filter': f"name:{args.cv_author_name}", 'field_list': 'id,name,volumes'}
            person_data = make_comicvine_api_request(f"{CV_BASE_URL}people/", person_params)
            
            volume_summaries_from_person = []
            if person_data and person_data.get('results'):
                if len(person_data['results']) == 0:
                    print_info(f"No person found matching '{args.cv_author_name}'.")
                    display_volume_search_results([]) # Display empty results
                    return
                
                # For simplicity, taking the first person match if multiple. Could be refined.
                if len(person_data['results']) > 1:
                    print_info(f"Multiple people found for '{args.cv_author_name}'. Using first result: {person_data['results'][0].get('name')}")
                
                person_result = person_data['results'][0]
                volumes_on_person = person_result.get('volumes', []) # This is a list of volume summaries
                
                print_info(f"Found {len(volumes_on_person)} volumes associated with {person_result.get('name', 'this person')}.")
                
                # These volume summaries from /people/ are basic (id, name, api_detail_url, site_detail_url usually)
                # We need to apply other local filters (publisher, year, issue_count)
                # And potentially fetch full details if we want to display them richly.
                # This can get slow if an author has many volumes.
                
                # Stage 1: Filter these basic volume summaries by other criteria
                temp_filtered_volumes = []
                for vol_summary in volumes_on_person:
                    match = True
                    # Local filter by publisher (if publisher name is in vol_summary or we fetch it)
                    # The vol_summary from /people/ endpoint does NOT contain publisher, start_year etc.
                    # So, these filters can only be applied if we fetch full details for each volume.
                    # This demonstrates the complexity. For now, let's only filter by name part IF series/title also given.
                    if args.cv_series_name and args.cv_series_name.lower() not in (vol_summary.get('name') or "").lower():
                        match = False
                    elif args.cv_title_desc and args.cv_title_desc.lower() not in (vol_summary.get('name') or "").lower(): # Basic name check for title
                        match = False
                    
                    # To apply year, publisher, num_issues, we MUST fetch full volume details.
                    # This is where it gets slow for prolific authors.
                    # Let's fetch full details for up to, say, 10-20 matching volumes to keep it manageable.
                    if match:
                        temp_filtered_volumes.append(vol_summary)

                # Stage 2: Fetch full details for the preliminarily filtered volumes and apply final filters
                final_volume_results = []
                max_vols_to_fully_fetch = 20 # Limit to avoid too many API calls
                vols_to_fetch_details_for = temp_filtered_volumes[:max_vols_to_fully_fetch]

                if len(temp_filtered_volumes) > max_vols_to_fully_fetch:
                    print_info(f"Author has many volumes. Fetching full details for the first {max_vols_to_fully_fetch} potential matches to apply all filters.")

                for vol_summary in vols_to_fetch_details_for:
                    vol_id_for_detail = vol_summary.get('id')
                    if not vol_id_for_detail: continue

                    # Construct the numeric part of the ID for the URL
                    numeric_vol_id = str(vol_id_for_detail).split('-')[-1] # Assuming ID is like "4050-XXXXX"

                    print_info(f"  Fetching full details for volume: {vol_summary.get('name')} (ID: {numeric_vol_id})...")
                    detail_params = {'field_list': 'id,name,publisher,start_year,count_of_issues,description,image,site_detail_url'} # Standard list for display
                    vol_detail_data = make_comicvine_api_request(f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{numeric_vol_id}/", detail_params)
                    time.sleep(0.2) # Small delay between these detail calls

                    if vol_detail_data and vol_detail_data.get('results'):
                        full_vol_data = vol_detail_data['results']
                        match_final = True
                        # Now apply publisher, year, num_issues filters
                        if args.cv_publisher_name:
                            pub_data = full_vol_data.get('publisher')
                            if not (pub_data and isinstance(pub_data, dict) and args.cv_publisher_name.lower() in (pub_data.get('name') or "").lower()):
                                match_final = False
                        if match_final and args.cv_start_year is not None:
                            vol_year_str = full_vol_data.get('start_year')
                            try:
                                if vol_year_str is None or str(vol_year_str).strip() == "" or int(vol_year_str) != args.cv_start_year: match_final = False
                            except (ValueError, TypeError): match_final = False
                        if match_final and args.cv_issues_count is not None:
                            if (full_vol_data.get('count_of_issues') is None or full_vol_data.get('count_of_issues') != args.cv_issues_count): match_final = False
                        
                        if match_final:
                            final_volume_results.append(full_vol_data)
                
                display_volume_search_results(final_volume_results)
                return # End of author-first search path

        # ** ELSE: Standard volume search (author not primary, or not given) **
        url = f"{CV_BASE_URL}volumes/"
        api_filters = []
        api_name_filter_value = args.cv_series_name if args.cv_series_name else args.cv_title_desc
        if api_name_filter_value: api_filters.append(f"name:{api_name_filter_value}")
        
        # Add author to filter if specified (will be broad, as discussed)
        if args.cv_author_name: 
            api_filters.append(f"person:{args.cv_author_name}")
            print_info(f"API filter: Including volumes associated with person '{args.cv_author_name}'. This can be broad.")
        if args.cv_publisher_name: api_filters.append(f"publisher:{args.cv_publisher_name}")

        if api_filters: params['filter'] = ','.join(api_filters)
        else: print_info("Performing a broad volume search (no specific criteria given to API).")

        params['field_list'] = 'id,name,publisher,start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
        params['limit'] = 100
        params['sort'] = 'date_last_updated:desc' if (args.cv_author_name or api_name_filter_value) else 'name:asc'
        
        print_info(f"Searching ComicVine volumes with API filters: {params.get('filter', 'None')}, Sort: {params.get('sort')}")
        
        # needs_post_filtering for this standard path (author is not locally post-filtered here)
        needs_post_filtering = (args.cv_series_name or args.cv_title_desc or args.cv_publisher_name or 
                                args.cv_start_year is not None or args.cv_issues_count is not None)
        
        if needs_post_filtering or args.cv_author_name: 
            active_post_filters_display = [] # For the info message
            if args.cv_series_name: active_post_filters_display.append("Series (local contains)")
            # ... (build active_post_filters_display as before, including "Author (API filtered)" if cv_author_name)
            if args.cv_title_desc: active_post_filters_display.append("Title/Desc (local contains)")
            if args.cv_publisher_name: active_post_filters_display.append("Publisher (local contains)")
            if args.cv_start_year is not None: active_post_filters_display.append("Year (local exact)")
            if args.cv_issues_count is not None: active_post_filters_display.append("Issues (local exact)")
            if args.cv_author_name: active_post_filters_display.append(f"Author '{args.cv_author_name}' (API filtered only for this search path)")
            if active_post_filters_display: 
                print_info(f"API results for standard search will be refined locally by: {', '.join(active_post_filters_display)}.")
    else:
        print_error("For a volume search, please provide at least one search criterion "
                    "(e.g., --series, --title, --year, etc.), or use --get-volume/--get-issue for specific items.")
        return 

    if not url: 
        print_error("Internal error: Could not determine API endpoint for fetch operation.")
        return 

    # Make the API request (this will be skipped if author-first search already returned)
    data = make_comicvine_api_request(url, params)

    if data:
        if mode == 'volume_search': # Standard volume search path
            search_results_list = data.get('results', []) 
            if needs_post_filtering: # Local filtering (excluding author)
                filtered_results_for_search = []
                # ... (the local post-filtering loop as in the previous version, WITHOUT author check)
                series_search_term = args.cv_series_name.lower() if args.cv_series_name else None
                title_desc_search_term = args.cv_title_desc.lower() if args.cv_title_desc else None
                publisher_search_term = args.cv_publisher_name.lower() if args.cv_publisher_name else None
                for volume_item in search_results_list:
                    match = True
                    if series_search_term and series_search_term not in (volume_item.get('name') or "").lower(): match = False
                    if match and title_desc_search_term:
                        vol_name_lower = (volume_item.get('name') or "").lower(); vol_desc_lower = (volume_item.get('description') or "").lower()
                        vol_desc_text = strip_html(vol_desc_lower) 
                        if not (title_desc_search_term in vol_name_lower or title_desc_search_term in vol_desc_text): match = False
                    if match and publisher_search_term:
                        pub_data = volume_item.get('publisher')
                        if not (pub_data and isinstance(pub_data, dict) and publisher_search_term in (pub_data.get('name') or "").lower()): match = False
                    if match and args.cv_start_year is not None:
                        vol_year_str = volume_item.get('start_year')
                        try:
                            if vol_year_str is None or str(vol_year_str).strip() == "" or int(vol_year_str) != args.cv_start_year: match = False
                        except (ValueError, TypeError): match = False
                    if match and args.cv_issues_count is not None:
                         if (volume_item.get('count_of_issues') is None or volume_item.get('count_of_issues') != args.cv_issues_count): match = False
                    if match: filtered_results_for_search.append(volume_item)
                display_volume_search_results(filtered_results_for_search) 
            else: # No local post-filtering was needed for this standard search path
                display_volume_search_results(search_results_list) 

        elif mode == 'volume_detail': # Changed from 'volume'
            display_volume_details(data.get('results', {})) 
        elif mode == 'issue_detail': # Changed from 'issue'
            if args.verbose: 
                display_issue_details_verbose(data.get('results', {}))
            else:
                display_issue_details_summary(data.get('results', {}))
    else: 
        # If data is None and it wasn't an author-first search that already handled its display
        if not (mode == 'volume_search' and args.cv_author_name and not (args.cv_series_name or args.cv_title_desc)):
            print_error("Failed to retrieve any data from ComicVine API for the request.")