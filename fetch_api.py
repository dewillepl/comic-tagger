#!/usr/bin/env python3

import requests
import json
import sys # For sys.exit (though ideally CLI manages final exit)
import time
import os # For os.path.basename

# Import configurations and utilities
from config import (
    CV_API_KEY, CV_BASE_URL, CV_USER_AGENT,
    CV_REQUEST_TIMEOUT, CV_RATE_LIMIT_WAIT_SECONDS, CV_MAX_RETRIES,
    CV_VOLUME_PREFIX, CV_ISSUE_PREFIX, CV_PERSON_PREFIX,
    CV_CHARACTER_PREFIX, CV_TEAM_PREFIX, CV_LOCATION_PREFIX,
    CV_STORY_ARC_PREFIX, CV_CONCEPT_PREFIX, CV_OBJECT_PREFIX
)
from utils import (
    Style, print_error, print_info, # print_success is not directly used in this module currently
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
    params['api_key'] = CV_API_KEY # Ensure API key is always in params for this function
    params['format'] = 'json'  # Ensure format is always json

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

# --- Display Functions for Fetched Data (using utils) ---

def display_volume_search_results(results_list):
    if not results_list: print_info("No volumes found matching your criteria."); return
    print_header_line(f"Found {len(results_list)} Volume(s)")
    for i, volume in enumerate(results_list):
        print(f"\n{Style.BOLD}{Style.YELLOW}--- Result {i+1} ---{Style.RESET}")
        print_field("Name:", volume.get('name'), value_style=Style.BOLD, value_color=Style.WHITE)
        print_field("ID:", volume.get('id'), value_color=Style.WHITE)
        if volume.get('publisher') and isinstance(volume['publisher'], dict): 
            print_field("Publisher:", volume['publisher'].get('name'), value_color=Style.WHITE)
        print_field("Start Year:", volume.get('start_year'), value_color=Style.WHITE)
        print_field("Issues:", volume.get('count_of_issues'), value_color=Style.WHITE)
        print_multiline_text("Description:", volume.get('description'))
        if volume.get('site_detail_url'): print_field("ComicVine URL:", volume.get('site_detail_url'), is_url=True)
        if volume.get('image') and volume['image'].get('thumb_url'): print_field("Cover (thumb):", volume['image']['thumb_url'], is_url=True)

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
    if volume_data.get('image') and volume_data['image'].get('small_url'): print_field("Cover (small):", volume_data['image']['small_url'], is_url=True)

    issues = volume_data.get('issues', [])
    if issues:
        print(f"\n  {Style.BOLD}{Style.GREEN}{'Issues':<18}{Style.RESET} ({len(issues)} found)")
        for issue in sorted(issues, key=lambda x: natsort.natsort_keygen()(str(x.get('issue_number', '0')))): # Ensure issue_number is str for natsort
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
    print(f"\n{Style.BRIGHT_BLACK}Info: For full details, use the --verbose flag.{Style.RESET}") # Changed from print_info to plain print

def display_issue_details_verbose(issue_data):
    """Pretty prints ALL available details for a single issue (verbose mode)."""
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
            img_url = img_data.get('original_url')
            if not img_url: continue
            caption = img_data.get('caption'); tags = img_data.get('image_tags')
            display_text_parts = [caption if caption else f"Image {idx+1}"]
            if tags and tags.lower() != "all images": display_text_parts.append(f"({Style.BRIGHT_BLACK}Tags: {tags}{Style.RESET})")
            display_text_final = " ".join(display_text_parts)
            print_field(f"Image {idx+1}:", img_url, indent=1, is_url=True, url_text=display_text_final)

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
            if credit_key == 'person_credits':
                credits_list_sorted = sorted(credits_list, key=lambda x: ((x.get('role') or '').lower(), (x.get('name') or '').lower()))
            else:
                credits_list_sorted = sorted(credits_list, key=lambda x: (x.get('name') or '').lower())
            for credit_item in credits_list_sorted:
                name = credit_item.get('name', 'N/A'); item_id = credit_item.get('id')
                role_str = ""
                if credit_key == 'person_credits' and credit_item.get('role'):
                    roles = [r.strip().capitalize() for r in credit_item.get('role').split(',') if r.strip()]
                    role_str = f" ({Style.YELLOW}{', '.join(roles)}{Style.GREEN})"
                url = credit_item.get('site_detail_url') or credit_item.get('api_detail_url')
                id_display = f" (ID: {item_id})" if item_id else ""
                display_text = f"{name}{role_str}{id_display}"
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
            print(f"\n  {Style.BOLD}{Style.MAGENTA}{display_title+':':<20}{Style.RESET}") # Changed label_width to fit ':'.
            for item in data_list:
                if isinstance(item, dict):
                    name = item.get('name', 'N/A'); item_id = item.get('id'); url = item.get('site_detail_url') or item.get('api_detail_url')
                    id_display = f" (ID: {item_id})" if item_id else ""; display_text = f"{name}{id_display}"
                    if url: print_field("  •", make_clickable_link(url, display_text), indent=1, label_color=Style.MAGENTA, label_width=3)
                    else: print_field("  •", display_text, indent=1, value_color=Style.WHITE, label_color=Style.MAGENTA, label_width=3)
                elif isinstance(item, str):
                    print_field("  •", item, indent=1, value_color=Style.WHITE, label_color=Style.MAGENTA, label_width=3)
    print("")


# --- Main Handler for 'fetch' command ---
def handle_fetch_comicvine(args):
    params = {} 
    url = None
    mode = None 
    needs_post_filtering = False

    if args.get_volume:
        mode = 'volume'
        url = f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{args.get_volume}/"
        params['field_list'] = 'id,name,issues,publisher(id|name|site_detail_url),start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
        print_info(f"Fetching details for volume ID: {args.get_volume} from ComicVine...")
    
    elif args.get_issue:
        mode = 'issue'
        url = f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.get_issue}/"
        # No 'field_list' in params means API should return all fields by default
        print_info(f"Fetching ALL available details for issue ID: {args.get_issue} from ComicVine...")

    elif args.search_volumes:
        mode = 'searching'
        url = f"{CV_BASE_URL}volumes/"
        api_filters = []
        api_name_filter_value = args.cv_series_name if args.cv_series_name else args.cv_title_desc
        if api_name_filter_value: api_filters.append(f"name:{api_name_filter_value}")
        if args.cv_author_name: api_filters.append(f"person:{args.cv_author_name}"); print_info("Using --author uses the 'person' ComicVine API filter.")
        if args.cv_publisher_name: api_filters.append(f"publisher:{args.cv_publisher_name}")
        if api_filters: params['filter'] = ','.join(api_filters)
        else: print_info("Warning: Searching volumes without any API filters. This might be slow or return many results.")
        params['field_list'] = 'id,name,publisher,start_year,count_of_issues,description,image,date_last_updated,api_detail_url,site_detail_url'
        params['limit'] = 100; params['sort'] = 'name:asc'
        print_info(f"Searching ComicVine volumes with API filters: {params.get('filter', 'None')}...")
        needs_post_filtering = (args.cv_series_name or args.cv_title_desc or args.cv_publisher_name or args.cv_start_year or args.cv_issues_count is not None)
        if needs_post_filtering:
            active_post_filters = [f for f, c in [("Series (contains)", args.cv_series_name), ("Title/Desc (contains)", args.cv_title_desc), ("Publisher (contains)", args.cv_publisher_name), ("Year (exact)", args.cv_start_year), ("Issues (exact)", args.cv_issues_count is not None)] if c]
            if active_post_filters: print_info(f"Applying local post-filtering for: {', '.join(active_post_filters)}...")
    
    if not url: 
        # This should ideally be caught by argparse if a mode is required.
        print_error("Internal error: Could not determine API endpoint for fetch operation.")
        return # Return instead of sys.exit to let CLI handle exit

    data = make_comicvine_api_request(url, params)

    if data:
        if mode == 'searching':
            search_results_list = data.get('results', []) 
            if needs_post_filtering:
                filtered_results_for_search = []
                series_search_term = args.cv_series_name.lower() if args.cv_series_name else None
                title_desc_search_term = args.cv_title_desc.lower() if args.cv_title_desc else None
                publisher_search_term = args.cv_publisher_name.lower() if args.cv_publisher_name else None
                for volume in search_results_list: 
                    match = True
                    if series_search_term and series_search_term not in (volume.get('name') or "").lower(): match = False
                    if match and title_desc_search_term:
                        vol_name_lower = (volume.get('name') or "").lower(); vol_desc_lower = (volume.get('description') or "").lower()
                        vol_desc_text = strip_html(vol_desc_lower) 
                        if not (title_desc_search_term in vol_name_lower or title_desc_search_term in vol_desc_text): match = False
                    if match and publisher_search_term:
                        pub_data = volume.get('publisher')
                        if not (pub_data and isinstance(pub_data, dict) and publisher_search_term in (pub_data.get('name') or "").lower()): match = False
                    if match and args.cv_start_year:
                        vol_year_str = volume.get('start_year')
                        try:
                            if vol_year_str is None or str(vol_year_str).strip() == "" or int(vol_year_str) != args.cv_start_year: match = False
                        except (ValueError, TypeError): match = False
                    if match and args.cv_issues_count is not None and (volume.get('count_of_issues') is None or volume.get('count_of_issues') != args.cv_issues_count): match = False
                    if match: filtered_results_for_search.append(volume)
                display_volume_search_results(filtered_results_for_search) 
            else:
                display_volume_search_results(search_results_list) 
        elif mode == 'volume': 
            display_volume_details(data.get('results', {})) 
        elif mode == 'issue': 
            if args.verbose: 
                display_issue_details_verbose(data.get('results', {}))
            else:
                display_issue_details_summary(data.get('results', {}))
    else: 
        print_error("Failed to retrieve any data from ComicVine API for the request.")
        # No explicit sys.exit here; let the CLI main loop handle final exit status if needed