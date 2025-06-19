#!/usr/bin/env python3

import requests
import json
import time

from config import CV_API_KEY, CV_BASE_URL, CV_USER_AGENT, CV_REQUEST_TIMEOUT, CV_RATE_LIMIT_WAIT_SECONDS, CV_MAX_RETRIES, CV_VOLUME_PREFIX, CV_ISSUE_PREFIX
from utils import Style, print_error, print_info, strip_html, make_clickable_link, print_header_line, print_field, print_multiline_text
import natsort

try:
    from translator import translate_text
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    def translate_text(text, target_language_code=None): return text

def make_comicvine_api_request(url, params):
    headers = {'User-Agent': CV_USER_AGENT, 'Accept': 'application/json'}
    params.update({'api_key': CV_API_KEY, 'format': 'json'})
    retries = 0
    while retries <= CV_MAX_RETRIES:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=CV_REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('error') == "OK": return data
                print_error(f"ComicVine API error: {data.get('error', 'Unknown')}")
                return None
            elif response.status_code == 429:
                print_error(f"Rate limit exceeded. Waiting {CV_RATE_LIMIT_WAIT_SECONDS}s...")
                time.sleep(CV_RATE_LIMIT_WAIT_SECONDS)
                retries += 1
            else:
                print_error(f"HTTP Error {response.status_code}: {response.text[:200]}...")
                return None
        except requests.exceptions.RequestException as e:
            print_error(f"Network error: {e}")
            return None
    return None

def display_volume_search_results(results_list):
    if not results_list:
        print_info("No volumes found matching your criteria.")
        return
    print_header_line(f"Found {len(results_list)} Volume(s)")
    for i, volume in enumerate(results_list, 1):
        print(f"\n{Style.BOLD}{Style.YELLOW}--- Result #{i} ---{Style.RESET}")
        print_field("Name:", volume.get('name'), value_style=Style.BOLD)
        print_field("ID:", volume.get('id'))
        if volume.get('publisher'): print_field("Publisher:", volume['publisher'].get('name'))
        print_field("Start Year:", volume.get('start_year'))
        if volume.get('people'):
            creator_names = sorted([p.get('name') for p in volume['people'] if p.get('name')])
            if creator_names: print_field("Creators:", ", ".join(creator_names))
        if volume.get('site_detail_url'): print_field("ComicVine URL:", volume.get('site_detail_url'), is_url=True)

def display_volume_details(volume_data):
    print_header_line(f"Volume: {volume_data.get('name', 'N/A')}")
    print_field("Name:", volume_data.get('name'), value_style=Style.BOLD)
    print_field("ID:", volume_data.get('id'))
    if volume_data.get('publisher'): print_field("Publisher:", volume_data['publisher'].get('name'))
    print_field("Start Year:", volume_data.get('start_year'))
    print_field("Total Issues:", volume_data.get('count_of_issues'))
    print_multiline_text("Description:", volume_data.get('description'))
    
    issues = volume_data.get('issues', [])
    if issues:
        print(f"\n  {Style.BOLD}{Style.GREEN}{'Issues':<18}{Style.RESET} ({len(issues)} found)")
        for issue in sorted(issues, key=lambda x: natsort.natsort_keygen()(str(x.get('issue_number', '0')))):
            name_display = issue.get('name') or f"Issue #{issue.get('issue_number', 'N/A')}"
            print_field(f"#{issue.get('issue_number', '?')}:", name_display, indent=1)
            print_field("ID:", issue.get('id'), indent=2)

def display_issue_details_verbose(issue_data):
    title = issue_data.get('name') or f"Issue #{issue_data.get('issue_number', 'N/A')}"
    print_header_line(f"Issue Details: {title}", color=Style.GREEN)
    print_field("Title:", issue_data.get('name'), value_style=Style.BOLD)
    print_field("Issue Num:", issue_data.get('issue_number'))
    print_field("ID:", issue_data.get('id'))
    if issue_data.get('volume'):
        print_field("Volume:", f"{issue_data['volume'].get('name', 'N/A')} (ID: {issue_data['volume'].get('id', 'N/A')})")
    print_field("Cover Date:", issue_data.get('cover_date'))
    print_multiline_text("Deck:", issue_data.get('deck'))
    print_multiline_text("Description:", issue_data.get('description'))
    if issue_data.get('site_detail_url'): print_field("ComicVine URL:", issue_data.get('site_detail_url'), is_url=True)
    
    credits = issue_data.get('person_credits', [])
    if credits:
        print(f"\n  {Style.BOLD}{Style.MAGENTA}{'Creators:':<18}{Style.RESET}")
        for credit in sorted(credits, key=lambda x: (x.get('role', 'zz'), x.get('name', ''))):
            print(f"    • {credit.get('name', 'N/A')} ({credit.get('role', 'N/A')})")

def handle_fetch_comicvine(args):
    """Fetches, displays, and returns data from ComicVine."""
    params = {}
    
    if getattr(args, 'get_issue', None):
        url = f"{CV_BASE_URL}issue/{CV_ISSUE_PREFIX}{args.get_issue}/"
        api_data = make_comicvine_api_request(url, params)
        if not (api_data and api_data.get('results')):
            print_error("Failed to retrieve issue details."); return None
        
        issue_details = dict(api_data['results']) 
        if getattr(args, 'translate_description', None) and TRANSLATOR_AVAILABLE:
            if issue_details.get('description'):
                issue_details['description'] = translate_text(strip_html(issue_details['description']), target_language_code=args.translate_description)
        
        display_issue_details_verbose(issue_details)
        return issue_details

    elif getattr(args, 'get_volume', None):
        url = f"{CV_BASE_URL}volume/{CV_VOLUME_PREFIX}{args.get_volume}/"
        params['field_list'] = 'id,name,issues,publisher,start_year,count_of_issues,description'
        api_data = make_comicvine_api_request(url, params)
        if not (api_data and api_data.get('results')):
            print_error("Failed to retrieve volume details."); return None
        
        display_volume_details(api_data['results'])
        return api_data['results']
    
    elif any(getattr(args, key, None) for key in ['cv_name_filter', 'cv_author_name', 'cv_publisher_name']):
        url = f"{CV_BASE_URL}volumes/"
        api_filters = []
        if args.cv_name_filter: api_filters.append(f"name:{args.cv_name_filter}")
        if args.cv_author_name: api_filters.append(f"person:{args.cv_author_name}")
        if args.cv_publisher_name: api_filters.append(f"publisher:{args.cv_publisher_name}")
        params['filter'] = ','.join(api_filters)
        params['field_list'] = 'id,name,publisher,start_year,people'
        params['limit'] = 25
        params['sort'] = 'name:asc'
        
        print_info(f"Searching ComicVine volumes...")
        api_data = make_comicvine_api_request(url, params)
        if not (api_data and api_data.get('results')):
            print_info("No volumes found."); return None
        
        results = api_data['results']
        if getattr(args, 'cv_start_year', None):
            results = [v for v in results if str(v.get('start_year')) == str(args.cv_start_year)]
        
        display_volume_search_results(results)
        return results
    else:
        print_error("No valid search criteria provided."); return None