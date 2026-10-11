"""
date_resolver.py
----------------
Resolves the original capture date of a media file.

Priority order:
  1. Google Takeout companion JSON  (most reliable)
  2. EXIF metadata                  (requires Pillow; images only)
  3. Video container metadata       (MP4/MOV/M4V/3GP 'mvhd' box; no dependency)
  4. Filename pattern matching      (best-effort fallback)
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


# ISO Base Media File Format family (MP4, MOV, M4V, 3GP) all share the same
# box/atom structure, so a single hand-rolled parser covers all of them
# without any external dependency (no ffprobe/mutagen required).
_ISO_BMFF_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".3gp"})

# QuickTime/ISO-BMFF timestamps are seconds since 1904-01-01 UTC.
# Offset to convert to the Unix epoch (1970-01-01 UTC).
_QT_EPOCH_OFFSET = 2082844800


def from_video_metadata(video_path: Path) -> datetime | None:
    """
    Read the creation time embedded in an MP4/MOV/M4V/3GP container's
    'mvhd' box (inside 'moov'). This is the camera/recording app's own
    timestamp, independent of EXIF (which Pillow can't read from video
    files at all) and independent of the filename.

    Returns None — never raises — if the box isn't found, the file isn't
    a recognized ISO-BMFF container, or the embedded timestamp is zero
    (many recording apps never set it).
    """
    if video_path.suffix.lower() not in _ISO_BMFF_VIDEO_EXTENSIONS:
        return None
    try:
        with open(video_path, "rb") as f:
            moov_end = None
            # Walk top-level boxes looking for 'moov'.
            while True:
                header = f.read(8)
                if len(header) < 8:
                    return None
                size = int.from_bytes(header[0:4], "big")
                box_type = header[4:8]
                if size == 1:
                    largesize = f.read(8)
                    if len(largesize) < 8:
                        return None
                    size = int.from_bytes(largesize, "big")
                    header_len = 16
                elif size == 0:
                    size = None  # extends to EOF
                    header_len = 8
                else:
                    header_len = 8

                if not box_type.isalnum():
                    return None  # not a real box stream, bail out safely

                if box_type == b"moov":
                    moov_end = f.tell() + (size - header_len if size else -1)
                    break

                if size is None:
                    return None  # moov never found before EOF-extending box
                f.seek(f.tell() + (size - header_len))

            # Now inside 'moov'; find the direct child 'mvhd' box.
            while moov_end is None or f.tell() < moov_end:
                header = f.read(8)
                if len(header) < 8:
                    return None
                size = int.from_bytes(header[0:4], "big")
                box_type = header[4:8]
                if size < 8 or not box_type.isalnum():
                    return None

                if box_type == b"mvhd":
                    version = f.read(1)
                    if not version:
                        return None
                    f.read(3)  # flags
                    if version == b"\x00":
                        creation = f.read(4)
                        if len(creation) < 4:
                            return None
                        creation_time = int.from_bytes(creation, "big")
                    else:
                        creation = f.read(8)
                        if len(creation) < 8:
                            return None
                        creation_time = int.from_bytes(creation, "big")
                    if not creation_time:
                        return None  # never set by the recording app
                    unix_ts = creation_time - _QT_EPOCH_OFFSET
                    if unix_ts <= 0:
                        return None
                    return datetime.fromtimestamp(unix_ts, tz=timezone.utc)

                f.seek(f.tell() + (size - 8))
    except Exception:
        return None
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

    dt = from_video_metadata(photo_path)
    if dt:
        return dt

    return from_filename(photo_path.name)


def pillow_available() -> bool:
    return _PILLOW_AVAILABLE
