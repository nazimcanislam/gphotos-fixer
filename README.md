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

---

## Requirements

- Python 3.10+
- `Pillow` *(optional)* — enables EXIF date reading

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/gphotos-fixer.git
cd gphotos-fixer
pip install Pillow   # optional but recommended
```

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

### All flags

| Flag | Short | Description |
|------|-------|-------------|
| `--input DIR` | `-i` | Google Photos folder from your Takeout export |
| `--output DIR` | `-o` | Destination folder |
| `--dry-run` | | Simulate without writing files |
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

## Made with Claude

This project was built collaboratively between [Nazımcan İslam](https://github.com/YOUR_USERNAME) and [Claude](https://claude.ai) (Anthropic's AI assistant).

The development process was genuinely iterative: a real 12,000+ file Takeout export was used as the test case throughout. Each failure — truncated JSON names, Windows path limits, duplicate copy numbering, corrupt timestamps — was diagnosed from actual output and fixed in real time. The result is a tool shaped by real-world problems rather than assumed ones.

If it rescued your photos, it was a team effort.

---

## License

[MIT](LICENSE)
