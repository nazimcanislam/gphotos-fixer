"""
finder.py
---------
Locates the companion .json metadata file for a given media file.

Google Takeout is notorious for inconsistent JSON naming. Known patterns:

    photo.jpg.json                        standard
    photo.jpg.supplemental-metadata.json  newer exports
    photo.jpg.supplemental-met.json       truncated (Windows MAX_PATH)
    photo.jpg.supplemental-meta.json      truncated
    photo.jpg.supplemen.json              truncated
    photo.jpg.suppl.json                  truncated
    photo.jp.json                         file extension truncated
    photo.json                            extension replaced
    photo_.mp4 → photo.json              trailing underscore in media name
    lp_image (21)(1).jpeg                 duplicate copies share one JSON
      → lp_image (21).jpeg.supplemental-metadata.json

Rather than maintaining an ever-growing list of suffixes, we use
os.listdir() and a prefix-match strategy, which handles all current and
future truncation variants without any changes to this file.

Windows MAX_PATH (260 chars) makes glob() unreliable for long filenames,
so we deliberately avoid it here.
"""

import os
import re
from pathlib import Path


def find_json(photo_path: Path) -> Path | None:
    """
    Return the companion JSON metadata file for *photo_path*, or None.

    Search order:
      1. Exact name prefix match:  photo.jpg → photo.jpg*.json
      2. Extension replaced:       photo.jpg → photo.json
      3. Trailing punctuation:     photo_.mp4 → photo.mp4*.json / photo.json
      4. Trailing copy index:      lp_image (21)(1).jpeg → lp_image (21).jpeg*.json
      5. All copy indices removed: lp_image (3)(1).jpeg → lp_image.jpeg*.json
      6. Truncated extension:      photo.jpg → photo.jp*.json, photo.j*.json
    """
    parent = photo_path.parent
    name   = photo_path.name    # e.g. lp_image (21)(1).jpeg
    stem   = photo_path.stem    # e.g. lp_image (21)(1)
    suffix = photo_path.suffix  # e.g. .jpeg

    try:
        entries = os.listdir(parent)
    except OSError:
        return None

    def first_with_prefix(prefix: str) -> Path | None:
        """Return the first entry whose name starts with *prefix* and ends with .json."""
        for entry in entries:
            if entry.lower().endswith(".json") and entry.startswith(prefix):
                return parent / entry
        return None

    def exact(name_: str) -> Path | None:
        """Return entry if it exists verbatim in the directory."""
        if name_ in entries:
            return parent / name_
        return None

    # ── 1. Full name prefix ───────────────────────────────────────────────────
    result = first_with_prefix(name)
    if result:
        return result

    # ── 2. Extension replaced: photo.jpg → photo.json ────────────────────────
    result = exact(stem + ".json")
    if result:
        return result

    # ── 3. Trailing _ or - in stem: photo_.mp4 → photo.mp4 / photo ──────────
    clean_trail = re.sub(r"[_-]+$", "", stem)
    if clean_trail != stem:
        result = (
            first_with_prefix(clean_trail + suffix)
            or exact(clean_trail + ".json")
        )
        if result:
            return result

    # ── 4. Trailing copy index: lp_image (21)(1) → lp_image (21) ─────────────
    clean_last = re.sub(r"\(\d+\)$", "", stem).strip()
    if clean_last != stem:
        result = first_with_prefix(clean_last + suffix)
        if result:
            return result

    # ── 5. All copy indices removed: lp_image (3)(1) → lp_image ─────────────
    clean_all = re.sub(r"\(\d+\)", "", stem).strip()
    if clean_all != stem:
        result = first_with_prefix(clean_all + suffix)
        if result:
            return result

    # ── 6. Truncated file extension: photo.jpg → photo.jp, photo.j ──────────
    for trim in range(1, len(suffix) - 1):
        result = first_with_prefix(name[:-trim])
        if result:
            return result

    return None
