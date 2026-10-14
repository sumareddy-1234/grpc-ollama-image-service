import json
import logging
from typing import Tuple, Optional

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from config import Config

logger = logging.getLogger(__name__)

def generate_image_from_prompt(prompt: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Call Ollama generate API.

    Returns a tuple ``(ok, image_base64, error_message)``.
    * ``ok`` – ``True`` if a usable image was returned.
    * ``image_base64`` – the first element of the ``images`` list when ``ok``.
    * ``error_message`` – human‑readable description when ``ok`` is ``False``.
    """
    url = f"{Config.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": Config.ollama_model,
        "prompt": prompt,
        "stream": False,
        "images": []
    }
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=Config.ollama_timeout,
        )
    except ConnectionError as e:
        logger.error("Ollama connection error: %s", e)
        return False, None, "Ollama service is not available."
    except Timeout as e:
        logger.error("Ollama request timed out: %s", e)
        return False, None, "Ollama request timed out."
    except RequestException as e:
        logger.error("Ollama request failed: %s", e)
        return False, None, "Failed to communicate with Ollama service."

    # HTTP status handling
    if not response.ok:
        logger.error("Ollama returned HTTP %s", response.status_code)
        return False, None, "Ollama service returned an error."

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Invalid JSON from Ollama: %s", e)
        return False, None, "Malformed response from Ollama service."

    images = data.get("images")
    if not images:
        logger.error("Ollama response missing 'images' field or empty.")
        return False, None, "Ollama response did not contain image data."

    # Take first image
    first = images[0]
    if not isinstance(first, str) or not first:
        logger.error("First image entry is not a non‑empty string.")
        return False, None, "Invalid image data returned by Ollama."

    return True, first, None
