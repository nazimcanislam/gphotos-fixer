# gphotos-fixer 📸

**A reliable Google Photos Takeout organizer that actually works.**

Google Takeout exports are a mess: inconsistently named JSON sidecars, truncated filenames due to Windows MAX_PATH limits, duplicate copies sharing a single metadata file, and timestamps that end up as today's date. Most existing tools fail silently on these edge cases.

`gphotos-fixer` was built by working through a real 12,000+ file Takeout export and fixing every failure case encountered along the way. It handles what others miss.

---

## Features

- **Organizes by date** → `YYYY/MM/filename` structure
- **Preserves albums** → `albums/<album name>/` folders kept intact
- **Fixes file timestamps** → sets `mtime` from the real capture date
- **Robust JSON matching** — handles all known Takeout sidecar naming variants:
  - `photo.jpg.json`
  - `photo.jpg.supplemental-metadata.json`
  - Truncated variants: `.suppl.json`, `.supplemen.json`, `.supplemental-met.json`, etc.
  - Extension replaced: `photo.json`
  - Extension truncated: `photo.jp.json`
  - Trailing punctuation: `photo_.mp4` → `photo.json`
  - Duplicate copies sharing one JSON: `lp_image (21)(1).jpeg` → `lp_image (21).jpeg.json`
- **Windows MAX_PATH safe** — uses `os.listdir()` instead of `glob()` to avoid path truncation issues
- **Duplicate detection** — MD5 hash check; skips identical files, renames conflicting ones
- **Future-date detection** — files with timestamps beyond the current year go to `suspicious_date/`
- **Dry-run mode** — preview what would happen without writing a single byte
- **Source/output count verification** — warns you if files are missing from the output
- **Optional EXIF fallback** — reads `DateTimeOriginal` via Pillow when JSON is absent
- **Filename pattern fallback** — extracts dates from patterns like `IMG_20230615_143000`
- **Flat mode (`--flat`)** — fix dates in *any* folder of photos/videos, not just a Takeout export. Useful when a file transfer (SD card, cloud sync, etc.) reset your timestamps but left EXIF data intact
- **Cross-platform** — gphotos-fixer is a CLI program that can run on Windows, macOS and Linux.

---

## Requirements

- Python 3.10+
- `Pillow` *(optional)* — enables EXIF date reading

---

## Installation

gphotos-fixer is a Python script, not an installer-based app: there is nothing to "install" in the usual sense. You download the code and run it with Python.

```bash
git clone https://github.com/nazimcanislam/gphotos-fixer.git
cd gphotos-fixer
pip install Pillow
```

`Pillow` is optional but recommended (it enables EXIF date reading). On Windows, use the quick start below if you don't have Git or the commands above don't work.

### Windows quick start (no Git needed)

1. **Install Python 3.10+** from [python.org/downloads](https://www.python.org/downloads/). On the first screen of the installer, tick **"Add python.exe to PATH"**, then click *Install Now*.
2. **Download gphotos-fixer:** on the [GitHub page](https://github.com/nazimcanislam/gphotos-fixer), click **Code → Download ZIP**, then right-click the ZIP and choose **Extract All…**. You will get a folder named `gphotos-fixer-main`.
3. **Open a terminal inside that folder:** open `gphotos-fixer-main` in File Explorer, click the address bar, type `cmd` and press Enter.
4. **Install Pillow** (optional but recommended):
   ```
   python -m pip install Pillow
   ```
5. **Run the tool** in interactive mode:
   ```
   python -m gphotos_fixer
   ```
   It asks for your input and output folders. Paste the paths **without quotation marks**, e.g. `C:\Users\You\Downloads\Takeout\Google Photos`. Tip: Shift + right-click a folder → *Copy as path* adds quotes, so remove them.

If `python` is not recognized, close and reopen the terminal, or try `py -m gphotos_fixer` instead. If it opens the Microsoft Store, Python is not installed or was installed without the PATH option; rerun the installer.

Note: the input folder must be the **`Google Photos`** folder *inside* your extracted Takeout export (the one containing `Photos from 2023`, etc.), not the Takeout root and not a ZIP file.

---

## Usage

### Interactive mode

```bash
python -m gphotos_fixer
```

The tool will ask for your input and output folders, then confirm before starting.

### Non-interactive (CLI)

```bash
python -m gphotos_fixer \
  --input  "/path/to/Takeout/Google Photos" \
  --output "/path/to/Photos_Organized"
```

### Dry run — preview without writing files

```bash
python -m gphotos_fixer \
  --input  "/path/to/Takeout/Google Photos" \
  --output "/path/to/Photos_Organized" \
  --dry-run
```

### Multiple Takeout ZIPs (`takeout-...-001.zip`, `-002.zip`, ...)

Large exports are split into several ZIP files. Don't process them one by one. Extract **all** of them into the **same destination folder** so they merge into a single `Takeout/Google Photos` folder (choose *merge* / *yes to all* if Windows asks about existing folders), then run gphotos-fixer **once** on that merged `Google Photos` folder.

Why: albums, year folders and their JSON metadata files can be spread across different ZIPs, and a ZIP that contains no `Photos from YYYY` folder is rejected by the tool. Merging first keeps every photo next to its metadata.

### Flat mode — fixing a plain folder of photos (not a Takeout export)

If your photos didn't come from Takeout but got their dates scrambled some other way (e.g. moving files from phone storage to an SD card via the Google Files app), `--flat` skips the year/album folder detection entirely and just organizes recursively by whatever date it can resolve from EXIF or the filename:

```bash
python -m gphotos_fixer \
  --input  "/path/to/messed_up_photos" \
  --output "/path/to/fixed" \
  --flat --dry-run
```

### All flags

| Flag | Short | Description |
|------|-------|-------------|
| `--input DIR` | `-i` | Google Photos folder from your Takeout export (or any photo folder in `--flat` mode) |
| `--output DIR` | `-o` | Destination folder |
| `--dry-run` | | Simulate without writing files |
| `--flat` | | Treat `--input` as a plain photo folder instead of a Takeout export |
| `--quiet` | `-q` | Only show the summary, suppress per-file output |
| `--version` | | Print version and exit |
| `--help` | `-h` | Show help |

---

## Output structure

```
Photos_Organized/
├── 2021/
│   ├── 06/
│   │   ├── IMG_20210612_143022.jpg
│   │   └── ...
│   └── 11/
├── 2022/
├── 2023/
├── albums/
│   ├── Cats 🐱/
│   └── Trip to Ankara/
├── unknown_date/       ← files with no recoverable date
└── suspicious_date/    ← files with a future timestamp (corrupt metadata)
```

---

## How date resolution works

For each file, the following sources are tried in order:

1. **Takeout JSON sidecar** — `photoTakenTime` or `creationTime` field
2. **EXIF metadata** — `DateTimeOriginal` (requires Pillow)
3. **Filename patterns** — e.g. `IMG_20230615_143022`, `2023-06-15`, `1702044110343`

If none of these yield a valid date, the file is placed in `unknown_date/`.

---

## Why not just use gpth?

[GooglePhotosTakeoutHelper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) is the most well-known tool for this, but it can fail with certain Takeout structures and gives unhelpful error messages. `gphotos-fixer` is a pure Python alternative with no compiled dependencies, transparent logic, and explicit handling for every edge case we encountered.

---

## Contributing

Issues and PRs are welcome. If you encounter a JSON naming variant or edge case not handled here, please open an issue with an example filename.

---

## Also by the author

If you just rescued your photos from Google Takeout, you might want to compress them next.

**[Shrinkify](https://github.com/nazimcanislam/shrinkify)** is a desktop app (built by the same author) that deduplicates and compresses your media library — videos, images, and more — using hardware-accelerated encoding when available.

The workflow pairs naturally: `gphotos-fixer` organizes your Takeout, Shrinkify cleans up the result.

---

## Update Version

Versions are written in a Python file and docs. Change them in:

- In `gphotos-fixer/__init__.py` file change `__version__` variable like `X.X.X`
- In `docs/src/data/schema.json` file change `softwareVersion` key like `X.X.X`

---

## Made with Claude

This project was built collaboratively between [Nazımcan İslam](https://github.com/nazimcanislam) and [Claude](https://claude.ai) (Anthropic's AI assistant).

The development process was genuinely iterative: a real 12,000+ file Takeout export was used as the test case throughout. Each failure — truncated JSON names, Windows path limits, duplicate copy numbering, corrupt timestamps — was diagnosed from actual output and fixed in real time. The result is a tool shaped by real-world problems rather than assumed ones.

If it rescued your photos, it was a team effort.

---

## License

[MIT](LICENSE)
