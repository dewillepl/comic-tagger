#!/usr/bin/env python3

import os

# --- ComicVine API Configuration ---
CV_API_KEY = "9ebffd40260fe62f4834da15df4f5a652f6309e6" # Your actual API key
CV_BASE_URL = "https://comicvine.gamespot.com/api/"

# User Agent: Can be overridden by CV_FETCHER_USER_AGENT environment variable
# The comic_tagger_cli.py will check os.environ.get('CV_FETCHER_USER_AGENT') and can pass it
# or this module can read it directly if preferred.
# For simplicity and direct use by modules that need it (like fetch_api.py):
DEFAULT_CV_USER_AGENT = "Python-Comic-Tagger/Modular-1.1"
CV_USER_AGENT = os.environ.get('CV_FETCHER_USER_AGENT', DEFAULT_CV_USER_AGENT)

CV_REQUEST_TIMEOUT = 30  # seconds
CV_RATE_LIMIT_WAIT_SECONDS = 5
CV_MAX_RETRIES = 3

# --- ComicVine Resource Prefixes ---
# These are identifiers used in API URLs for specific resource types
CV_VOLUME_PREFIX = "4050-" # e.g., /api/volume/4050-XXXXX/
CV_ISSUE_PREFIX = "4000-"   # e.g., /api/issue/4000-XXXXX/
CV_PERSON_PREFIX = "4040-"  # e.g., /api/person/4040-XXXXX/ (for creators)
CV_CHARACTER_PREFIX = "4005-" # e.g., /api/character/4005-XXXXX/
CV_TEAM_PREFIX = "4060-"      # e.g., /api/team/4060-XXXXX/ (often 4005- is also seen for teams in practice)
CV_LOCATION_PREFIX = "4020-"  # e.g., /api/location/4020-XXXXX/ (often 4005- is also seen for locations)
CV_STORY_ARC_PREFIX = "4045-" # e.g., /api/story_arc/4045-XXXXX/
CV_PUBLISHER_PREFIX = "4010-" # e.g., /api/publisher/4010-XXXXX/

# ADD THESE LINES:
CV_CONCEPT_PREFIX = "4015-"  # Standard prefix for concepts
CV_OBJECT_PREFIX = "4025-"   # Standard prefix for objects (though less common in issue credits) 
                             # Sometimes 4005- is also used for objects by CV.
                             # Check API docs if specific object links are needed.

# You can add other application-wide configurations here if needed later.
# For example:
# DEFAULT_OUTPUT_DIR_NAME = "converted"
# LOG_LEVEL = "INFO"