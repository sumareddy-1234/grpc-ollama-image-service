"""
Client module for AUTOMATIC1111 Stable Diffusion WebUI API.
Communicates with the /sdapi/v1/txt2img endpoint.
"""
import json
import logging
from typing import Tuple, Optional

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from config import Config

logger = logging.getLogger(__name__)

def generate_image_from_prompt(prompt: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Call AUTOMATIC1111 txt2img API.

    Returns a tuple ``(ok, image_base64, error_message)``.
    * ``ok`` - True if a usable image was returned.
    * ``image_base64`` - the first element of the ``images`` list when ``ok``.
    * ``error_message`` - human-readable description when ``ok`` is False.
    """
    url = f"{Config.sd_base_url.rstrip('/')}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "steps": Config.sd_steps,
        "width": Config.sd_width,
        "height": Config.sd_height,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=Config.sd_timeout,
        )
    except (ConnectionError, Timeout) as e:
        logger.error("Image generation service connection/timeout error: %s", e)
        return False, None, "Image generation service is not available."
    except RequestException as e:
        logger.error("Image generation service request failed: %s", e)
        return False, None, "Image generation service is not available."

    # HTTP status handling
    if not response.ok:
        logger.error("Image generation service returned HTTP %s", response.status_code)
        return False, None, "Image generation service returned an error."

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Invalid JSON from image generation service: %s", e)
        return False, None, "Malformed response from image generation service."

    images = data.get("images")
    if not images or not isinstance(images, list) or len(images) == 0:
        logger.error("Image generation response missing 'images' field or empty.")
        return False, None, "Image generation response did not contain image data."

    first = images[0]
    if not isinstance(first, str) or not first.strip():
        logger.error("First image entry is not a non-empty string.")
        return False, None, "Invalid image data returned by image generation service."

    # Strip data URI header if present
    if first.startswith("data:image"):
        first = first.split(",", 1)[-1].strip()

    return True, first, None
