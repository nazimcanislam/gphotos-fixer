"""
date_resolver.py
----------------
Resolves the original capture date of a media file.

Priority order:
  1. Google Takeout companion JSON  (most reliable)
  2. EXIF metadata                  (requires Pillow)
  3. Filename pattern matching      (best-effort fallback)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .finder import find_json

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False

# Filename patterns tried in order of specificity.
_FILENAME_PATTERNS = [
    # 2023_06_15_14_30_00  or  2023-06-15-14-30-00
    re.compile(r"(\d{4})[_-](\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{2})"),
    # 2023_06_15  or  2023-06-15
    re.compile(r"(\d{4})[_-](\d{2})[_-](\d{2})"),
    # IMG_20230615_143000  or  VID_20230615_143000
    re.compile(r"(?:IMG|VID)[_-](\d{8})[_-](\d{6})"),
    # 20230615_143000
    re.compile(r"(\d{8})[_-](\d{6})"),
    # 20230615
    re.compile(r"(\d{8})"),
]


def from_json(json_path: Path) -> datetime | None:
    """Extract the capture timestamp from a Takeout JSON sidecar."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
        ts = (
            data.get("photoTakenTime")
            or data.get("creationTime")
            or {}
        ).get("timestamp")
        if ts:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        pass
    return None


def from_exif(photo_path: Path) -> datetime | None:
    """Extract DateTimeOriginal (or fallback fields) from EXIF data."""
    if not _PILLOW_AVAILABLE:
        return None
    try:
        img = Image.open(photo_path)
        exif = img._getexif()
        if not exif:
            return None
        for tag_id, val in exif.items():
            if TAGS.get(tag_id) in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def from_filename(filename: str) -> datetime | None:
    """Guess a date from common timestamp patterns embedded in filenames."""
    for pattern in _FILENAME_PATTERNS:
        m = pattern.search(filename)
        if not m:
            continue
        g = m.groups()
        try:
            if len(g) >= 6:
                return datetime(int(g[0]), int(g[1]), int(g[2]),
                                int(g[3]), int(g[4]), int(g[5]))
            if len(g) == 2 and len(g[0]) == 8:
                d, t = g[0], g[1]
                return datetime(int(d[:4]), int(d[4:6]), int(d[6:8]),
                                int(t[:2]), int(t[2:4]), int(t[4:6]))
            if len(g) == 1 and len(g[0]) == 8:
                d = g[0]
                return datetime(int(d[:4]), int(d[4:6]), int(d[6:8]))
            if len(g) >= 3:
                return datetime(int(g[0]), int(g[1]), int(g[2]))
        except (ValueError, IndexError):
            continue
    return None


def resolve(photo_path: Path) -> datetime | None:
    """
    Return the best available capture date for *photo_path*.
    Returns None if no date can be determined.
    """
    json_path = find_json(photo_path)
    if json_path:
        dt = from_json(json_path)
        if dt:
            return dt

    dt = from_exif(photo_path)
    if dt:
        return dt

    return from_filename(photo_path.name)


def pillow_available() -> bool:
    return _PILLOW_AVAILABLE
