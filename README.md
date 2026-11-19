# shotstamp

Rename your camera-roll photos by the date they were actually taken.

```
IMG_4829.jpg  ->  2026-11-18_09-41-23.jpg
DSC_0041.jpg  ->  2026-11-18_09-41-23-2.jpg
screenshot.png -> 2026-11-18_09-41-23-3.png
```

## Why I built this

Every phone dump I have is a folder full of `IMG_4829.jpg` and `DSC_0041.jpg`.
Sorting by name is useless, sorting by file date breaks the moment you copy
files around, and the one piece of information that actually matters — when
the photo was taken — is sitting right there in the EXIF data, ignored.

I tried the usual answers first. ExifTool does the job but it's a 20 MB Perl
install for a one-line rename, and the shell one-liners floating around on
forums all assume your files are JPEGs from one camera and never collide.
So I wrote the small tool I actually wanted: point it at a folder, preview
with `--dry-run`, rename. Nothing else.

## Install

```bash
pip install git+https://github.com/codewithkrrish/shotstamp.git
```

Python 3.9 or newer. Zero dependencies — the EXIF reader is hand-written
against the standard library, so there's nothing else to install.

## Usage

Always preview first:

```bash
shotstamp ~/Pictures/phone-dump --dry-run
```

```
  would rename IMG_4829.jpg -> 2026-11-18_09-41-23.jpg  [EXIF DateTimeOriginal]
  would rename DSC_0041.jpg -> 2026-11-18_09-41-23-2.jpg  [EXIF DateTimeOriginal]
  skip screenshot.png (no EXIF date and no usable file time)
shotstamp: dry run: 2 would be renamed, 1 skipped.
```

Happy with it? Run it for real:

```bash
shotstamp ~/Pictures/phone-dump
shotstamp ~/Pictures/phone-dump -r        # include subfolders
```

### Options

| Flag | What it does |
| --- | --- |
| `-r`, `--recursive` | Descend into subfolders |
| `--dry-run` | Show what would happen, rename nothing |
| `--pattern FORMAT` | strftime pattern for the new name (default `%Y-%m-%d_%H-%M-%S`) |
| `--extensions LIST` | Comma-separated extensions (default `jpg,jpeg,png,tif,tiff`) |
| `--no-mtime` | Don't fall back to the file modified time when EXIF is missing |
| `-q`, `--quiet` | Only print the summary line |

### How names are decided

1. **EXIF first.** `DateTimeOriginal` if it's there, then
   `DateTimeDigitized`, then plain `DateTime`. This is the moment the
   shutter fired — the date that matters.
2. **File modified time as fallback.** Screenshots and downloads usually
   have no EXIF date; their modified time is the next best thing. Use
   `--no-mtime` to skip those files instead.
3. **Collisions get a number.** Three burst shots in the same second become
   `...-23.jpg`, `...-23-2.jpg`, `...-23-3.jpg`. Nothing is ever
   overwritten.
4. **Running it twice is safe.** A file that already has the right name is
   left alone.

### Custom patterns

```bash
shotstamp photos/ --pattern "%Y%m%d_%H%M%S"     # 20261118_094123.jpg
shotstamp photos/ --pattern "%Y-%m-%d"           # date only; bursts get -2, -3
```

The pattern must not contain `/` or `\` — it becomes a filename, and
shotstamp refuses anything that would escape the folder.

## Project structure

```
shotstamp/
  shotstamp/
    __init__.py   version
    cli.py        flags, output, exit codes — thin on purpose
    exif.py       hand-rolled EXIF reader (JPEG APP1, PNG eXIf, TIFF)
    rename.py     planning, collision handling, applying renames
    errors.py     the exceptions the CLI turns into plain sentences
  tests/
    conftest.py   builds tiny real JPEGs/PNGs with chosen EXIF dates
    test_exif.py  parser: both byte orders, corrupt files, bad dates
    test_rename.py
    test_cli.py
```

## Limitations — the honest part

- **No HEIC, no video.** iPhone `.heic` files and `.mp4`/`.mov` clips are
  skipped. Their date metadata lives in a different container format and
  I didn't want to half-support it.
- **No timezone handling.** The EXIF timestamp is used exactly as the
  camera wrote it. If your camera clock was set to the wrong zone, the
  names will be too.
- **It trusts the camera.** A camera with its clock set to 2019 will stamp
  2019. Garbage in, garbage out — check `--dry-run` output first.
- **The EXIF parser is deliberately small.** It reads the date tags and
  nothing else. Exotic files with broken TIFF structures are treated as
  "no date" and fall back to modified time instead of crashing.

## Tests

```bash
pip install pytest
python -m pytest
```

33 tests: EXIF parsing (both byte orders, PNG, corrupt and truncated
files), collision numbering, dry-run safety, mtime fallback, CLI exit
codes. The test JPEGs are built byte by byte in `conftest.py`, so the
parser is tested against real files, not a mock.

## License

MIT — see [LICENSE](LICENSE).

## Author

Built by [Krrish](https://github.com/codewithkrrish) — I rename my own
camera rolls with it.
