import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "complaint")
    safe = safe.strip("._")
    if not safe:
        safe = "complaint"
    return safe


def save_uploaded_image(uploaded_file, target_dir: str | Path) -> str:
    """Save an uploaded image to a safe local path and return the relative path."""
    return save_image_bytes(uploaded_file.getvalue(), uploaded_file.name, target_dir)


def save_image_bytes(image_bytes: bytes, original_name: str, target_dir: str | Path) -> str:
    """Save image bytes using a safe, unique filename and return the local path."""
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    extension = Path(original_name).suffix.lower()
    safe_base = sanitize_filename(Path(original_name).stem)
    unique_name = f"{safe_base}_{uuid.uuid4().hex[:8]}{extension or '.png'}"
    local_path = target_path / unique_name

    with local_path.open("wb") as file:
        file.write(image_bytes)

    return str(local_path)


def validate_image(uploaded_file, max_size_mb: int = 8) -> tuple[bool, str]:
    if uploaded_file is None:
        return False, "Please select an image file."

    file_name = getattr(uploaded_file, "name", "")
    extension = Path(file_name).suffix.lower()
    mime_type = getattr(uploaded_file, "type", "")

    if extension not in ALLOWED_EXTENSIONS:
        return False, "Only JPG, JPEG, PNG, and WEBP files are allowed."

    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False, "The uploaded file type is not recognized as a valid image."

    file_size_bytes = uploaded_file.getbuffer().nbytes
    max_bytes = max_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        return False, f"Image is too large. Maximum allowed size is {max_size_mb} MB."

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        return False, "The selected file is not a valid image."

    uploaded_file.seek(0)
    return True, ""
