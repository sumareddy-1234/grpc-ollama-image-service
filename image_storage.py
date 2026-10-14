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
    if not request_id:
        return uuid.uuid4().hex

    # Keep alphanumerics, hyphen, and underscore
    safe = "".join(ch for ch in request_id if ch.isalnum() or ch in "_-")
    safe = safe.strip("._-")
    if not safe:
        safe = uuid.uuid4().hex
    return safe

def save_image(base64_data: str, request_id: str, output_dir: str) -> Tuple[bool, str]:
    """Decode ``base64_data``, validate image integrity, and write it atomically as a PNG.

    Returns a tuple ``(success, path_or_error)`` where ``path_or_error`` is the
    relative path to the saved image on success or an error description on failure.
    """
    if not base64_data or not isinstance(base64_data, str):
        return False, "Invalid Base64 image data."

    try:
        raw_bytes = base64.b64decode(base64_data, validate=True)
    except Exception as e:
        logger.error("Base64 decoding failed: %s", e)
        return False, "Invalid Base64 image data."

    if not raw_bytes:
        return False, "Invalid Base64 image data."

    # Validate that the bytes represent a genuine, readable image
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            if not img.format:
                raise ValueError("Could not identify image format.")
    except Exception as e:
        logger.error("Image validation failed: %s", e)
        return False, "Invalid image data."

    safe_id = _sanitize_request_id(request_id)
    filename = f"{safe_id}.png"
    output_path = Path(output_dir) / filename
    temp_path = output_path.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically: write to temp file then atomic replace
        with open(temp_path, "wb") as f:
            f.write(raw_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, output_path)
    except Exception as e:
        logger.error("Failed to write image file: %s", e)
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False, "Failed to save image"

    # Return relative path using forward slashes
    rel_path = os.path.relpath(output_path, start=os.getcwd()).replace("\\", "/")
    return True, rel_path
