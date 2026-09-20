"""
organizer.py
------------
Handles the actual file operations: scanning, copying, and date stamping.

Output structure
~~~~~~~~~~~~~~~~
<output>/
  YYYY/MM/          ← files from year folders (Photos from YYYY)
  albums/<name>/    ← files from album folders
  unknown_date/     ← files whose date could not be resolved
  suspicious_date/  ← files with a future timestamp (likely corrupt metadata)
"""

import hashlib
import os
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from . import date_resolver

# Media file extensions that will be processed.
MEDIA_EXTENSIONS: frozenset[str] = frozenset({
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".heic", ".heif",
    ".raw", ".cr2", ".nef", ".arw", ".dng",
    # Videos
    ".mp4", ".mov", ".avi", ".mkv", ".wmv",
    ".m4v", ".3gp", ".mts",
    # Motion Photo video components (Pixel/Android "Motion Photo" .jpg+.mp pairs).
    # Google Takeout sometimes ships these with a conflict suffix (.mp~2) or as
    # a separate .cover thumbnail. Previously unhandled -> silently dropped.
    ".mp", ".mp~2", ".cover",
})

# Folder names to skip entirely (case-insensitive).
_SKIP_FOLDERS: frozenset[str] = frozenset({"çöp kutusu", "trash", "bin"})

# Google Takeout localizes the "Photos from YYYY" folder name to the
# language the Google account was set to when the export was made. Each
# pattern must capture the 4-digit year in group 1.
_YEAR_FOLDER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^photos?\s+from\s+(\d{4})$", re.IGNORECASE),                    # English
    re.compile(r"^(\d{4})\s*y[ıi]l[ıi]na\s+ait\s+fotoğraflar$", re.IGNORECASE),  # Turkish
    re.compile(r"^fotos?\s+(?:de|von|from)\s+(\d{4})$", re.IGNORECASE),          # es/pt/de fallback
    # Last resort: a folder name that's just the bare year, nothing else
    # (older Takeout exports and some locales use this).
    re.compile(r"^(\d{4})$"),
)

_NOT_SEEN = object()  # sentinel: "no destination seen yet" vs "seen but unreadable (hash=None)"


class Stats(NamedTuple):
    copied:     int = 0
    skipped:    int = 0
    renamed:    int = 0
    no_date:    int = 0
    suspicious: int = 0
    errors:     int = 0

    def __add__(self, other: "Stats") -> "Stats":
        return Stats(
            self.copied     + other.copied,
            self.skipped    + other.skipped,
            self.renamed    + other.renamed,
            self.no_date    + other.no_date,
            self.suspicious + other.suspicious,
            self.errors     + other.errors,
        )


def _md5(path: Path, chunk: int = 65536) -> str | None:
    """Return the MD5 hex digest of *path*, or None if the file is unreadable."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while data := f.read(chunk):
                h.update(data)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def _set_mtime(path: Path, dt: datetime) -> None:
    """Set the file's modification time to *dt*."""
    try:
        ts = dt.timestamp()
        os.utime(path, (ts, ts))
    except OSError:
        pass


def _safe_copy(
    src: Path,
    dst: Path,
    dt: datetime | None,
    dry_run: bool,
    virtual_seen: dict[Path, str | None] | None = None,
) -> str:
    """
    Copy *src* to *dst* and optionally fix the modification timestamp.

    Returns one of: 'copied', 'skipped', 'renamed', 'error'.

    If *dst* already exists:
    - same MD5  → skip (no copy)
    - different → append _1, _2 … until the name is free, then copy

    When *dry_run* is True no files are written to disk, but duplicate/
    conflict detection is still simulated via *virtual_seen* — a dict
    shared across the whole run that tracks which destination paths
    "would" exist and with which MD5, so dry-run stats match a real run.
    Without *virtual_seen*, dry-run falls back to the old (inaccurate)
    behaviour of always reporting 'copied'.

    If the source file is unreadable (corrupted, locked, permission denied),
    the function returns 'error' and prints a warning — it never raises.
    """
    if dry_run:
        if virtual_seen is None:
            return "copied"

        existing_hash: str | None
        if dst.exists():
            existing_hash = _md5(dst)
        elif dst in virtual_seen:
            existing_hash = virtual_seen[dst]
        else:
            existing_hash = _NOT_SEEN  # type: ignore[assignment]

        if existing_hash is not _NOT_SEEN:
            src_hash = _md5(src)
            if src_hash is None:
                return "error"
            if src_hash == existing_hash:
                return "skipped"
            stem, suffix = dst.stem, dst.suffix
            i = 1
            candidate = dst
            while candidate.exists() or candidate in virtual_seen:
                candidate = dst.parent / f"{stem}_{i}{suffix}"
                i += 1
            virtual_seen[candidate] = src_hash
            return "renamed"

        virtual_seen[dst] = _md5(src)
        return "copied"

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        src_hash = _md5(src)
        dst_hash = _md5(dst)
        # If src is unreadable, treat as error; if dst is unreadable, skip the
        # equality check and fall through to rename (safer than silently skipping).
        if src_hash is None:
            print(f"  ✗ skipped (unreadable): {src.name}", flush=True)
            return "error"
        if src_hash == dst_hash:
            return "skipped"
        stem, suffix = dst.stem, dst.suffix
        i = 1
        while dst.exists():
            dst = dst.parent / f"{stem}_{i}{suffix}"
            i += 1
        try:
            shutil.copy2(src, dst)
        except (PermissionError, OSError) as e:
            print(f"  ✗ skipped (unreadable): {src.name} — {e}", flush=True)
            return "error"
        if dt:
            _set_mtime(dst, dt)
        return "renamed"

    try:
        shutil.copy2(src, dst)
    except (PermissionError, OSError) as e:
        print(f"  ✗ skipped (unreadable): {src.name} — {e}", flush=True)
        return "error"
    if dt:
        _set_mtime(dst, dt)
    return "copied"


def _destination(photo: Path, dst_root: Path, album: str | None,
                 current_year: int) -> tuple[Path, str]:
    """
    Return (destination_path, category) for *photo*.

    category is one of: 'normal', 'no_date', 'suspicious'
    """
    dt = date_resolver.resolve(photo)

    if album is not None:
        return dst_root / "albums" / album / photo.name, "normal"

    if dt is None:
        return dst_root / "unknown_date" / photo.name, "no_date"

    if dt.year > current_year:
        return dst_root / "suspicious_date" / str(dt.year) / photo.name, "suspicious"

    return dst_root / str(dt.year) / f"{dt.month:02d}" / photo.name, "normal"


def count_media(folder: Path) -> int:
    """Count media files under *folder* recursively."""
    return sum(
        1 for f in folder.rglob("*")
        if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS
    )


def classify_folders(
    base: Path,
) -> tuple[dict[int, Path], list[Path]]:
    """
    Split *base*'s immediate subdirectories into:
      - year_folders: mapping {year: path} for "Photos from YYYY" folders
      - album_folders: all other folders (trash folders excluded)
    """
    year_folders: dict[int, Path] = {}
    album_folders: list[Path] = []

    for folder in base.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.lower() in _SKIP_FOLDERS:
            continue
        year = None
        for pattern in _YEAR_FOLDER_PATTERNS:
            m = pattern.match(folder.name.strip())
            if m:
                year = int(m.group(1))
                break
        if year is not None:
            year_folders[year] = folder
        else:
            album_folders.append(folder)

    return year_folders, album_folders


def process_folder(
    src_folder: Path,
    dst_root: Path,
    *,
    album: str | None = None,
    dry_run: bool = False,
    verbose: bool = True,
    virtual_seen: dict[Path, str | None] | None = None,
) -> Stats:
    """
    Process all media files under *src_folder*.

    Parameters
    ----------
    src_folder   : source directory to scan recursively
    dst_root     : root of the output directory
    album        : if set, place files under albums/<album>/
    dry_run      : simulate without writing any files
    verbose      : print a line per file
    virtual_seen : shared dict (pass the SAME dict across every call in a
                   dry-run) used to simulate duplicate/conflict detection
                   without touching disk. Ignored when dry_run is False.
    """
    current_year = datetime.now().year
    counters = {"copied": 0, "skipped": 0, "renamed": 0,
                "no_date": 0, "suspicious": 0, "errors": 0}

    for photo in src_folder.rglob("*"):
        if not photo.is_file():
            continue
        if photo.suffix.lower() not in MEDIA_EXTENSIONS:
            continue

        dt = date_resolver.resolve(photo)
        dst, category = _destination(photo, dst_root, album, current_year)

        result = _safe_copy(photo, dst, dt, dry_run, virtual_seen)

        if category == "no_date":
            counters["no_date"] += 1
        elif category == "suspicious":
            counters["suspicious"] += 1

        if result == "error":
            counters["errors"] += 1
        else:
            counters[result] += 1

        if verbose:
            symbol = {"copied": "✓", "skipped": "=", "renamed": "~", "error": "✗"}.get(result, "?")
            tag = {"no_date": " [no date]", "suspicious": " [suspicious date]"}.get(
                category, ""
            )
            # Error lines are already printed inside _safe_copy with full detail;
            # skip reprinting them here to avoid duplication.
            if result != "error":
                print(f"  {symbol} {photo.name}{tag}", flush=True)

    return Stats(**counters)
