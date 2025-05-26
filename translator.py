#!/usr/bin/env python3
# translator.py
import json
import hashlib
import logging # For logging translation events
import requests
from pathlib import Path
import time # For potential retries or delays

# --- Configuration ---
# IMPORTANT: Replace with your actual Mistral API Key
MISTRAL_API_KEY = "tuZw0jjNA2XThSZc6Ps8ACcdtetrFztO" 
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
# Using a model known for good balance of quality and speed for translation
MISTRAL_MODEL = "mistral-small-latest" # Or "mistral-large-latest" for higher quality if budget allows

# Cache file will be in the same directory as this script
CACHE_FILE_PATH = Path(__file__).parent / 'translation_cache.json'
TRANSLATION_REQUEST_TIMEOUT = 20 # seconds for Mistral API call
TRANSLATION_RETRY_DELAY = 5 # seconds before retrying a failed translation

# --- Logging Setup ---
# Basic logging configuration. Can be enhanced in main CLI if needed.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__) # Get a logger specific to this module

# --- Cache Management ---
_translation_cache = {}

def load_translation_cache():
    global _translation_cache
    if CACHE_FILE_PATH.exists():
        try:
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                _translation_cache = json.load(f)
            logger.info(f"Translation cache loaded from {CACHE_FILE_PATH}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding translation cache file. Starting with an empty cache.")
            _translation_cache = {}
        except Exception as e:
            logger.error(f"Could not load translation cache: {e}. Starting with an empty cache.")
            _translation_cache = {}
    else:
        logger.info("Translation cache file not found. Starting with an empty cache.")
        _translation_cache = {}

def save_translation_cache():
    global _translation_cache
    try:
        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(_translation_cache, f, ensure_ascii=False, indent=2)
        logger.debug(f"Translation cache saved to {CACHE_FILE_PATH}") # Debug level for successful save
    except Exception as e:
        logger.error(f"Could not save translation cache: {e}")

def _generate_cache_key(text: str, source_lang: str, target_lang: str) -> str:
    """Generates a consistent hash key for caching."""
    # Include model in hash if we might use different models for different tasks later
    # For now, text + langs is sufficient.
    combined = f"{text}|{source_lang}|{target_lang}|{MISTRAL_MODEL}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

# Load cache when module is imported
load_translation_cache()

# --- Translation Function ---
def translate_text(text_to_translate: str, target_language_code: str = 'pl', source_language_code: str = 'en', max_retries=1) -> str:
    """
    Translate `text_to_translate` from `source_language_code` into `target_language_code`
    using the Mistral API, with caching and retries.
    Returns the translated text, or the original text on failure.
    """
    if not text_to_translate or not text_to_translate.strip():
        return text_to_translate # Return empty/whitespace as is

    if MISTRAL_API_KEY == "YOUR_MISTRAL_API_KEY_HERE" or not MISTRAL_API_KEY:
        logger.warning("Mistral API key is not configured in translator.py. Translation disabled.")
        return text_to_translate

    # For simplicity, let's map language codes to full names for the prompt
    lang_map = {
        'pl': 'Polish', 'en': 'English', 'de': 'German', 'fr': 'French', 'es': 'Spanish'
        # Add more as needed
    }
    target_lang_full = lang_map.get(target_language_code.lower(), target_language_code)
    source_lang_full = lang_map.get(source_language_code.lower(), source_language_code)

    cache_key = _generate_cache_key(text_to_translate, source_language_code, target_language_code)
    if cache_key in _translation_cache:
        logger.info(f"Cache hit for translation to {target_lang_full}.")
        return _translation_cache[cache_key]

    logger.info(f"Cache miss. Requesting translation from {source_lang_full} to {target_lang_full} for text snippet: \"{text_to_translate[:50]}...\"")

    # Prompt tailored for better quality translation
    prompt = (
        f"You are an expert translator specializing in comic book and narrative content. "
        f"Translate the following text accurately from {source_lang_full} to {target_lang_full}. "
        f"Preserve the original tone, style, and any specific formatting like emphasis or paragraph breaks if implied by the input. "
        f"If the input text contains chapter titles or list-like structures, maintain that structure in the translation. "
        f"Here is the text:\n\n\"{text_to_translate}\""
    )

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, # Lower temperature for more deterministic, less creative translation
        "max_tokens": 1500, # Adjust based on typical description length
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(MISTRAL_API_URL, json=payload, headers=headers, timeout=TRANSLATION_REQUEST_TIMEOUT)
            response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
            
            result_json = response.json()
            translated_text = result_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

            if not translated_text: # If API returns empty content
                logger.warning(f"Mistral API returned empty content for translation. Attempt {attempt + 1}.")
                if attempt < max_retries: time.sleep(TRANSLATION_RETRY_DELAY); continue
                raise ValueError("Mistral API returned empty content.")

            _translation_cache[cache_key] = translated_text
            save_translation_cache() # Save cache after each successful translation
            logger.info(f"Translation successful to {target_lang_full}. Snippet: \"{translated_text[:50]}...\"")
            return translated_text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Mistral API request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries: time.sleep(TRANSLATION_RETRY_DELAY)
            else: logger.error(f"Translation failed after {max_retries + 1} attempts due to network/request error."); return text_to_translate # Fallback
        except (KeyError, IndexError, ValueError) as e: # Errors in parsing response
            logger.warning(f"Error parsing Mistral API response (attempt {attempt + 1}/{max_retries + 1}): {e}. Response: {response.text[:200] if 'response' in locals() else 'N/A'}")
            if attempt < max_retries: time.sleep(TRANSLATION_RETRY_DELAY)
            else: logger.error(f"Translation failed after {max_retries + 1} attempts due to response parsing error."); return text_to_translate # Fallback
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred during translation (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries: time.sleep(TRANSLATION_RETRY_DELAY)
            else: logger.error(f"Translation failed after {max_retries + 1} attempts due to unexpected error."); return text_to_translate # Fallback
    
    return text_to_translate # Should be unreachable if loop completes, but as a final fallback