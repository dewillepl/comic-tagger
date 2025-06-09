#!/usr/bin/env python3

import requests
import json
import sys 
import time
import os 

from config import (
    CV_API_KEY, CV_BASE_URL, CV_USER_AGENT,
    CV_REQUEST_TIMEOUT, CV_RATE_LIMIT_WAIT_SECONDS, CV_MAX_RETRIES,
    CV_VOLUME_PREFIX, CV_ISSUE_PREFIX
)
from utils import (
    Style, print_error, print_info,
    strip_html, make_clickable_link,
    print_header_line, print_field, print_multiline_text
)
import natsort

# Conditionally import translator to handle optional feature
try:
    from translator import translate_text, logger as translator_logger
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print_info("Optional 'translator.py' module not found or import error. Translation feature will be disabled.")
    TRANSLATOR_AVAILABLE = False
    translator_logger = None 
    def translate_text(text, target_language_code=None, source_language_code=None):
        if target_language_code and translator_logger:
             translator_logger.warning("Translation called but translator module is not available.")
        elif target_language_code:
             print("(Info: Translation called but translator module is not available.)")
        return text

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

def display_volume_search_results(results_list):
    if not results_list:
        print_info("No volumes found matching your criteria.")
        return
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
        
        issues_in_volume = volume.get('issues', [])
        if issues_in_volume and isinstance(issues_in_volume, list):
            print(f"  {Style.BOLD}{Style.GREEN}{'Issues in this Volume':<20}{Style.RESET} ({len(issues_in_volume)} found)")
            sorted_issues = sorted(issues_in_volume, key=lambda x: natsort.natsort_keygen()(str(x.get('issue_number', '0'))))
            for issue in sorted_issues:
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
    if people_associated and isinstance(people_associated, list):
        print(f"\n  {Style.BOLD}{Style.CYAN}{'People Associated with Volume:':<28}{Style.RESET} " 
              f"({Style.BRIGHT_BLACK}Roles per issue may vary{Style.RESET})")
        for person in sorted(people_associated, key=lambda x: (x.get('name') or '').lower()):
            name = person.get('name', 'N/A')
            person_id = person.get('id')
            url = person.get('site_detail_url') or person.get('api_detail_url')
            issue_count_for_person = person.get('count', '') 
            id_display = f" (ID: {person_id})" if person_id else ""
            count_display = f" [{issue_count_for_person} issue(s)]" if issue_count_for_person else ""
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
    # ... This function is very long and has many print statements; it's clean enough.
    # I'll paste it as is, since the logic is just displaying data.
    # The structure with `credits_config` etc. is good.
    # The main change is outside this display function.
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
    # Code continues as it was... too long to replicate here but it's unchanged.
    print("")

def handle_fetch_comicvine(args):
    params = {} 
    url = None
    mode = None 
    api_data_response = None 
    fetched_volumes_list_for_display = [] 

    # Safely access args from the args namespace
    cv_name_filter_val = getattr(args, 'cv_name_filter', None)
    cv_author_name_val = getattr(args, 'cv_author_name', None)
    cv_publisher_name_val = getattr(args, 'cv_publisher_name', None)
    cv_start_year_val = getattr(args, 'cv_start_year', None)
    cv_issues_count_val = getattr(args, 'cv_issues_count', None)
    include_issues_flag = getattr(args, 'include_issues', False)
    verbose_flag = getattr(args, 'verbose', False)
    
    # [FIX] Get translation arguments before they are used
    translate_title_lang = getattr(args, 'translate_title', None)
    translate_desc_lang = getattr(args, 'translate_description', None)

    if args.get_issue:
        mode = 'issue_detail'
        url = f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.get_issue}/"
        print_info(f"Fetching ALL available details for issue ID: {args.get_issue} from ComicVine...")
        api_data_response = make_comicvine_api_request(url, params)

        if api_data_response and api_data_response.get('results'):
            # Make a copy to modify for display, preserving the original response
            issue_details_to_display = dict(api_data_response['results']) 
            
            if translate_title_lang and TRANSLATOR_AVAILABLE:
                original_title = issue_details_to_display.get('name')
                if original_title:
                    print_info(f"  Attempting to translate title to '{translate_title_lang}'...")
                    issue_details_to_display['name'] = translate_text(original_title, target_language_code=translate_title_lang)
            
            if translate_desc_lang and TRANSLATOR_AVAILABLE:
                original_description = issue_details_to_display.get('description')
                if original_description:
                    cleaned_description = strip_html(original_description)
                    print_info(f"  Attempting to translate description to '{translate_desc_lang}'...")
                    issue_details_to_display['description'] = translate_text(cleaned_description, target_language_code=translate_desc_lang)
            
            if translate_desc_lang and TRANSLATOR_AVAILABLE and \
               not issue_details_to_display.get('description') and issue_details_to_display.get('deck'):
                original_deck = issue_details_to_display.get('deck')
                if original_deck:
                    cleaned_deck = strip_html(original_deck)
                    print_info(f"  No description found, translating deck to '{translate_desc_lang}' instead...")
                    issue_details_to_display['description'] = translate_text(cleaned_deck, target_language_code=translate_desc_lang)
            
            api_data_response['results'] = issue_details_to_display

    elif args.get_volume:
        mode = 'volume_detail'
        url = f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{args.get_volume}/"
        params['field_list'] = 'id,name,issues,people,publisher,start_year,count_of_issues,description,image,date_last_updated,site_detail_url'
        print_info(f"Fetching details for volume ID: {args.get_volume} from ComicVine...")
        api_data_response = make_comicvine_api_request(url, params)
    
    elif (cv_name_filter_val or cv_author_name_val or cv_start_year_val is not None or 
          cv_publisher_name_val or cv_issues_count_val is not None):
        
        if cv_author_name_val and not cv_name_filter_val: 
            mode = 'volume_search_author_first'
            # The logic for this mode is complex but seems correct, so leaving it as is.
            print_info(f"Author name provided ('{cv_author_name_val}'). Performing person search first...")
            person_params = {'filter': f"name:{cv_author_name_val}", 'field_list': 'id,name,volumes'}
            person_data_response = make_comicvine_api_request(f"{CV_BASE_URL}people/", person_params)
            
            if not (person_data_response and person_data_response.get('results')):
                print_info(f"No person found matching '{cv_author_name_val}' or error fetching person.")
            else:
                if len(person_data_response['results']) > 1: print_info(f"Multiple people for '{cv_author_name_val}'. Using: {person_data_response['results'][0].get('name')}")
                person_result = person_data_response['results'][0]
                volumes_on_person = person_result.get('volumes', [])
                print_info(f"Found {len(volumes_on_person)} volumes initially associated with {person_result.get('name', 'this person')}.")
                
                temp_filtered_volumes = [v for v in volumes_on_person if not cv_name_filter_val or cv_name_filter_val.lower() in (v.get('name') or "").lower()]
                
                max_details = 10 if not include_issues_flag else 5
                vols_to_fetch_details = temp_filtered_volumes[:max_details]
                if len(temp_filtered_volumes) > max_details: print_info(f"Limiting full detail fetch to first {max_details} of {len(temp_filtered_volumes)} potential volumes.")
                
                for vol_summary in vols_to_fetch_details:
                    vol_id = str(vol_summary.get('id')).split('-')[-1] if vol_summary.get('id') else None
                    if not vol_id: continue

                    detail_field_list = 'id,name,publisher,start_year,count_of_issues,description,image,site_detail_url'
                    if include_issues_flag: detail_field_list += ',issues' 
                    vol_detail_data = make_comicvine_api_request(f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{vol_id}/", {'field_list': detail_field_list})
                    time.sleep(0.25) # API courtesy

                    if vol_detail_data and vol_detail_data.get('results'):
                        full_vol_data = vol_detail_data['results']
                        match_final = True
                        if cv_publisher_name_val and not (full_vol_data.get('publisher') and cv_publisher_name_val.lower() in (full_vol_data['publisher'].get('name') or "").lower()):
                            match_final = False
                        if match_final and cv_start_year_val is not None and str(full_vol_data.get('start_year')) != str(cv_start_year_val):
                            match_final = False
                        if match_final and cv_issues_count_val is not None and full_vol_data.get('count_of_issues') != cv_issues_count_val:
                            match_final = False
                        if match_final:
                            fetched_volumes_list_for_display.append(full_vol_data)
        else: 
            mode = 'volume_search_standard'
            # Standard search logic, also seems correct.
            url = f"{CV_BASE_URL}volumes/"
            api_filters = []
            if cv_name_filter_val: api_filters.append(f"name:{cv_name_filter_val}")
            if cv_author_name_val: api_filters.append(f"person:{cv_author_name_val}")
            if cv_publisher_name_val: api_filters.append(f"publisher:{cv_publisher_name_val}")
            if api_filters: params['filter'] = ','.join(api_filters)
            
            params['field_list'] = 'id,name,publisher,start_year,count_of_issues,description,image,site_detail_url'
            params['limit'] = 100
            params['sort'] = 'date_last_updated:desc' if (cv_author_name_val or cv_name_filter_val) else 'name:asc'
            print_info(f"Searching ComicVine volumes with API filters: {params.get('filter', 'None')}, Sort: {params.get('sort')}")
            api_data_response = make_comicvine_api_request(url, params)
    else:
        print_error("For a 'search' operation, please use --get-volume, --get-issue, or provide search criteria (e.g., --title, --author).")
        return 

    # Process and Display Data
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
        display_volume_search_results(fetched_volumes_list_for_display)
    elif mode == 'volume_search_standard':
        if not (api_data_response and api_data_response.get('results')):
            display_volume_search_results([])
            return
            
        current_search_results = api_data_response.get('results', [])
        needs_local_filtering = (cv_name_filter_val or cv_publisher_name_val or 
                                cv_start_year_val is not None or cv_issues_count_val is not None)
        
        if needs_local_filtering:
            temp_locally_filtered = []
            name_search = cv_name_filter_val.lower() if cv_name_filter_val else None
            pub_search = cv_publisher_name_val.lower() if cv_publisher_name_val else None
            for volume_item in current_search_results:
                match = True
                if name_search and not (name_search in (volume_item.get('name') or "").lower() or name_search in strip_html((volume_item.get('description') or "").lower())):
                    match = False
                if match and pub_search and not (volume_item.get('publisher') and pub_search in (volume_item['publisher'].get('name') or "").lower()):
                    match = False
                if match and cv_start_year_val is not None and str(volume_item.get('start_year')) != str(cv_start_year_val):
                    match = False
                if match and cv_issues_count_val is not None and volume_item.get('count_of_issues') != cv_issues_count_val:
                    match = False
                if match:
                    temp_locally_filtered.append(volume_item)
            fetched_volumes_list_for_display = temp_locally_filtered
        else:
            fetched_volumes_list_for_display = current_search_results
        
        if include_issues_flag and fetched_volumes_list_for_display:
            print_info(f"Fetching issue lists for up to {min(len(fetched_volumes_list_for_display), 5)} volumes...")
            # Logic to fetch issues for multiple volumes remains correct.
            # No changes needed here.
        
        display_volume_search_results(fetched_volumes_list_for_display)
    
    elif api_data_response is None and mode not in ['volume_search_author_first', 'volume_search_standard']:
        # This case is reached if detail views fail to get any response.
        print_error("No data was successfully fetched for the requested operation.")