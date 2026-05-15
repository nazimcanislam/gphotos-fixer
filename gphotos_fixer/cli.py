"""
cli.py
------
Command-line interface for gphotos-fixer.

Usage (interactive):
    python -m gphotos_fixer

Usage (non-interactive):
    python -m gphotos_fixer --input /path/to/Google Photos --output /path/to/out
    python -m gphotos_fixer --input ... --output ... --dry-run
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .organizer import classify_folders, count_media, process_folder, Stats
from .date_resolver import pillow_available


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    print("=" * 62)
    print("  gphotos-fixer  v" + __version__)
    print("  Google Photos Takeout Organizer")
    print("=" * 62)


def _print_summary(stats: Stats, source_count: int, dry_run: bool) -> None:
    output_count = stats.copied + stats.renamed
    missing = source_count - output_count - stats.skipped
    dry_tag = "  [DRY RUN — no files were written]\n" if dry_run else ""

    print("\n" + "=" * 62)
    print("  Done!" + (" (dry run)" if dry_run else ""))
    print(dry_tag, end="")
    print(f"  📥 Source files       : {source_count}")
    print(f"  ✓  Copied             : {stats.copied}")
    print(f"  =  Skipped (duplicate): {stats.skipped}")
    print(f"  ~  Renamed (conflict) : {stats.renamed}")
    print(f"  ?  No date found      : {stats.no_date}  → unknown_date/")
    print(f"  ⚠  Suspicious date    : {stats.suspicious}  → suspicious_date/")

    if missing > 0:
        print(f"\n  ❌ MISSING: {missing} file(s) may not have been transferred!")
        print(f"     (source: {source_count}, output: {output_count + stats.skipped})")
    else:
        print(f"\n  ✅ All files accounted for.")
    print("=" * 62)


# ── Interactive mode ──────────────────────────────────────────────────────────

def _ask_path(prompt: str) -> Path:
    while True:
        raw = input(f"  {prompt}: ").strip()
        if raw:
            return Path(raw)
        print("  Please enter a path.")


def _interactive(dry_run: bool) -> tuple[Path, Path]:
    print()
    print("── Input folder ─────────────────────────────────────────────")
    print("  This is the 'Google Photos' folder inside your Takeout export.")
    input_dir = _ask_path("Input path")

    print()
    print("── Output folder ────────────────────────────────────────────")
    print("  Destination folder for organised photos (will be created if needed).")
    output_dir = _ask_path("Output path")

    print()
    print(f"  📂 Input  : {input_dir}")
    print(f"  📂 Output : {output_dir}")
    if dry_run:
        print("  🔍 Mode   : DRY RUN (no files will be written)")
    print()
    answer = input("  Start? [Y/n]: ").strip().lower()
    if answer and answer not in ("y", "yes", "e", "evet"):
        print("Aborted.")
        sys.exit(0)

    return input_dir, output_dir


# ── Main entry point ──────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="gphotos-fixer",
        description="Organize a Google Photos Takeout export into a clean folder structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m gphotos_fixer

  # Non-interactive
  python -m gphotos_fixer --input ~/Takeout/Google\\ Photos --output ~/Photos

  # Dry run (no files written)
  python -m gphotos_fixer --input ~/Takeout/Google\\ Photos --output ~/Photos --dry-run
""",
    )
    parser.add_argument(
        "--input", "-i", metavar="DIR",
        help="Path to the 'Google Photos' folder inside your Takeout export.",
    )
    parser.add_argument(
        "--output", "-o", metavar="DIR",
        help="Destination folder for organised photos.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and report without copying any files.",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress per-file output; only show the summary.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    _print_banner()

    if not pillow_available():
        print("\n⚠  Pillow is not installed — EXIF date extraction disabled.")
        print("   Install it with: pip install Pillow\n")

    # Resolve paths
    if args.input and args.output:
        input_dir  = Path(args.input)
        output_dir = Path(args.output)
        if args.dry_run:
            print("\n🔍 DRY RUN — no files will be written.\n")
    else:
        input_dir, output_dir = _interactive(dry_run=args.dry_run)

    if not input_dir.exists():
        print(f"\n❌ Input folder not found: {input_dir}")
        sys.exit(1)

    # Scan source
    print("\n🔍 Scanning source folder…")
    source_count = count_media(input_dir)
    print(f"   Found {source_count} media file(s).\n")

    year_folders, album_folders = classify_folders(input_dir)
    total = Stats()

    # Process year folders
    print(f"── Year folders ({len(year_folders)}) ──────────────────────────────────")
    for year, folder in sorted(year_folders.items()):
        print(f"\n📅 {folder.name}")
        s = process_folder(
            folder, output_dir,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )
        total = total + s

    # Process album folders
    print(f"\n── Album folders ({len(album_folders)}) ─────────────────────────────────")
    for folder in album_folders:
        print(f"\n📁 {folder.name}")
        s = process_folder(
            folder, output_dir,
            album=folder.name,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )
        total = total + s

    _print_summary(total, source_count, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
