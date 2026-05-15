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
})

# Folder names to skip entirely (case-insensitive).
_SKIP_FOLDERS: frozenset[str] = frozenset({"çöp kutusu", "trash", "bin"})

_YEAR_FOLDER_RE = re.compile(r"photos?\s+from\s+(\d{4})", re.IGNORECASE)


class Stats(NamedTuple):
    copied:     int = 0
    skipped:    int = 0
    renamed:    int = 0
    no_date:    int = 0
    suspicious: int = 0

    def __add__(self, other: "Stats") -> "Stats":
        return Stats(
            self.copied     + other.copied,
            self.skipped    + other.skipped,
            self.renamed    + other.renamed,
            self.no_date    + other.no_date,
            self.suspicious + other.suspicious,
        )


def _md5(path: Path, chunk: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()


def _set_mtime(path: Path, dt: datetime) -> None:
    """Set the file's modification time to *dt*."""
    try:
        ts = dt.timestamp()
        os.utime(path, (ts, ts))
    except OSError:
        pass


def _safe_copy(src: Path, dst: Path, dt: datetime | None, dry_run: bool) -> str:
    """
    Copy *src* to *dst* and optionally fix the modification timestamp.

    Returns one of: 'copied', 'skipped', 'renamed'.

    If *dst* already exists:
    - same MD5  → skip (no copy)
    - different → append _1, _2 … until the name is free, then copy

    When *dry_run* is True no files are written and the function always
    returns 'copied' (simulating what would happen).
    """
    if dry_run:
        return "copied"

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if _md5(src) == _md5(dst):
            return "skipped"
        stem, suffix = dst.stem, dst.suffix
        i = 1
        while dst.exists():
            dst = dst.parent / f"{stem}_{i}{suffix}"
            i += 1
        shutil.copy2(src, dst)
        if dt:
            _set_mtime(dst, dt)
        return "renamed"

    shutil.copy2(src, dst)
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
        m = _YEAR_FOLDER_RE.match(folder.name)
        if m:
            year_folders[int(m.group(1))] = folder
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
) -> Stats:
    """
    Process all media files under *src_folder*.

    Parameters
    ----------
    src_folder : source directory to scan recursively
    dst_root   : root of the output directory
    album      : if set, place files under albums/<album>/
    dry_run    : simulate without writing any files
    verbose    : print a line per file
    """
    current_year = datetime.now().year
    counters = {"copied": 0, "skipped": 0, "renamed": 0,
                "no_date": 0, "suspicious": 0}

    for photo in src_folder.rglob("*"):
        if not photo.is_file():
            continue
        if photo.suffix.lower() not in MEDIA_EXTENSIONS:
            continue

        dt = date_resolver.resolve(photo)
        dst, category = _destination(photo, dst_root, album, current_year)

        result = _safe_copy(photo, dst, dt, dry_run)

        if category == "no_date":
            counters["no_date"] += 1
        elif category == "suspicious":
            counters["suspicious"] += 1

        counters[result] += 1

        if verbose:
            symbol = {"copied": "✓", "skipped": "=", "renamed": "~"}.get(result, "?")
            tag = {"no_date": " [no date]", "suspicious": " [suspicious date]"}.get(
                category, ""
            )
            print(f"  {symbol} {photo.name}{tag}", flush=True)

    return Stats(**counters)
