import os
import io
import base64
import uuid
from pathlib import Path
from typing import Tuple
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def _sanitize_request_id(request_id: str) -> str:
    """Return a safe filename component derived from request_id.
    Removes path separators and other unsafe characters. If the result is empty
    or would resolve outside the output directory, a UUID is used instead.
    """
    # Keep alphanumerics, hyphen and underscore only
    safe = "".join(ch for ch in request_id if ch.isalnum() or ch in "_- ")
    if not safe:
        safe = uuid.uuid4().hex
    return safe

def save_image(base64_data: str, request_id: str, output_dir: str) -> Tuple[bool, str]:
    """Decode ``base64_data`` and write it as a PNG file.

    Returns a tuple ``(success, path_or_error)`` where ``path_or_error`` is the
    relative path to the saved image on success or an error description on failure.
    """
    try:
        raw_bytes = base64.b64decode(base64_data, validate=True)
    except Exception as e:
        logger.error("Base64 decoding failed: %s", e)
        return False, "Invalid Base64 image data."

    # Validate that the bytes form a real image if possible
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.load()
    except Exception as e:
        logger.warning("Image validation skipped or failed: %s", e)
        # Continue anyway; save raw bytes

    safe_id = _sanitize_request_id(request_id)
    filename = f"{safe_id}.png"
    output_path = Path(output_dir) / filename
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically
        temp_path = output_path.with_suffix('.tmp')
        with open(temp_path, "wb") as f:
            f.write(raw_bytes)
        os.replace(temp_path, output_path)
    except Exception as e:
        logger.error("Failed to write image file: %s", e)
        return False, "Failed to save image"

    # Return relative path using forward slashes
    rel_path = os.path.relpath(output_path, start=os.getcwd()).replace("\\", "/")
    return True, rel_path
