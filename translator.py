#!/usr/bin/env python3

import json
import hashlib
import logging
import requests
from pathlib import Path
import time

from models import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL

CACHE_FILE_PATH = Path(__file__).parent / 'translation_cache.json'
TRANSLATION_REQUEST_TIMEOUT = 20
TRANSLATION_RETRY_DELAY = 5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.debug(f"Translation cache saved to {CACHE_FILE_PATH}")
    except Exception as e:
        logger.error(f"Could not save translation cache: {e}")

def _generate_cache_key(text: str, source_lang: str, target_lang: str) -> str:
    combined = f"{text}|{source_lang}|{target_lang}|{OPENROUTER_MODEL}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

load_translation_cache()

def translate_text(text_to_translate: str, target_language_code: str = 'pl', source_language_code: str = 'en', max_retries=1) -> str:
    if not text_to_translate or not text_to_translate.strip():
        return text_to_translate

    if not (OPENROUTER_API_KEY and OPENROUTER_API_KEY.startswith("sk-or-")):
        logger.warning("OpenRouter API key is not configured! Translation disabled.")
        return text_to_translate

    lang_map = {
        'pl': 'Polish', 'en': 'English', 'de': 'German', 'fr': 'French', 'es': 'Spanish'
    }
    target_lang_full = lang_map.get(target_language_code.lower(), target_language_code)
    source_lang_full = lang_map.get(source_language_code.lower(), source_language_code)

    cache_key = _generate_cache_key(text_to_translate, source_language_code, target_language_code)
    if cache_key in _translation_cache:
        logger.info(f"Cache hit for translation to {target_lang_full}.")
        return _translation_cache[cache_key]

    logger.info(f"Cache miss. Requesting translation from {source_lang_full} to {target_lang_full} for text snippet: \"{text_to_translate[:50]}...\"")

    prompt = (
        f"You are an expert translator specializing in comic book and narrative content. "
        f"Translate ONLY the following Description text, from {source_lang_full} to {target_lang_full}, preserving the original tone, style, and formatting. "
        f"DO NOT add any summaries, explanations, notes, or comments. "
        f"Return ONLY the translated Description text, nothing else. "
        f"Here is the Description text:\n\n\"{text_to_translate}\""
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=TRANSLATION_REQUEST_TIMEOUT)
            response.raise_for_status()
            result_json = response.json()
            translated_text = result_json.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if not translated_text:
                logger.warning(f"API returned empty content for translation. Attempt {attempt + 1}.")
                if attempt < max_retries:
                    time.sleep(TRANSLATION_RETRY_DELAY)
                    continue
                raise ValueError("API returned empty content.")
            _translation_cache[cache_key] = translated_text
            save_translation_cache()
            logger.info(f"Translation successful to {target_lang_full}. Snippet: \"{translated_text[:50]}...\"")
            return translated_text
        except requests.exceptions.RequestException as e:
            logger.warning(f"API request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(TRANSLATION_RETRY_DELAY)
            else:
                logger.error(f"Translation failed after {max_retries + 1} attempts due to network/request error.")
                return text_to_translate
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"Error parsing API response (attempt {attempt + 1}/{max_retries + 1}): {e}. Response: {response.text[:200] if 'response' in locals() else 'N/A'}")
            if attempt < max_retries:
                time.sleep(TRANSLATION_RETRY_DELAY)
            else:
                logger.error(f"Translation failed after {max_retries + 1} attempts due to response parsing error.")
                return text_to_translate
        except Exception as e:
            logger.error(f"An unexpected error occurred during translation (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(TRANSLATION_RETRY_DELAY)
            else:
                logger.error(f"Translation failed after {max_retries + 1} attempts due to unexpected error.")
                return text_to_translate
    return text_to_translate