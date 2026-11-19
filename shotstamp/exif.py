"""A tiny EXIF reader, standard library only.

I only need one thing out of a photo: when it was taken. Pulling in Pillow
for that one tag felt like overkill, so this parses the TIFF structure inside
a JPEG APP1 segment by hand. It understands exactly the tags it needs and
gives up quietly (returns None) on anything it doesn't recognise, instead of
crashing on some camera's weird maker note.

Supported inputs: JPEG (APP1 Exif), PNG (eXIf chunk), and bare TIFF files.
The date comes from DateTimeOriginal first, then DateTimeDigitized, then the
plain DateTime tag — in that order, because "when the shutter fired" is the
one that matters for sorting a camera roll.
"""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

# EXIF tag numbers, straight from the TIFF spec.
TAG_EXIF_IFD = 0x8769
TAG_DATETIME = 0x0132  # IFD0: file last modified (weakest signal)
TAG_DATETIME_ORIGINAL = 0x9003  # Exif IFD: when the photo was taken
TAG_DATETIME_DIGITIZED = 0x9004  # Exif IFD: when it was digitised

# TIFF field type -> size in bytes. Only the ones we ever read.
_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}

_EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# How far into a file we bother looking for an EXIF segment. EXIF lives at
# the top of a JPEG; if it isn't in the first 64 KiB it isn't there.
_MAX_SCAN_BYTES = 64 * 1024


def read_exif_datetime(path: Path) -> tuple[datetime, str] | None:
    """Return (when the photo was taken, which tag it came from), or None.

    Returns None when the file has no readable EXIF date — that is a normal
    outcome for screenshots and downloads, not an error.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(_MAX_SCAN_BYTES)
    except OSError:
        return None
    if head[:2] == b"\xff\xd8":
        return _from_jpeg(head)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return _from_png(head)
    if head[:2] in (b"II", b"MM"):
        return _from_tiff(head)
    return None


def _parse_exif_date(raw: str) -> datetime | None:
    """Parse an EXIF date string like ``2026:11:18 09:41:23``."""
    raw = raw.strip("\x00 ").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, _EXIF_DATE_FORMAT)
    except ValueError:
        return None


def _from_jpeg(data: bytes) -> tuple[datetime, str] | None:
    """Walk JPEG segments until the APP1 Exif block, then parse its TIFF."""
    offset = 2  # skip the SOI marker
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        if marker == 0xDA:  # SOS: image data starts here, EXIF is behind us
            return None
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            offset += 2  # standalone marker, no length field
            continue
        (length,) = struct.unpack_from(">H", data, offset + 2)
        if length < 2 or offset + 2 + length > len(data):
            return None
        segment = data[offset + 4 : offset + 2 + length]
        if marker == 0xE1 and segment[:6] == b"Exif\x00\x00":
            return _from_tiff(segment[6:])
        offset += 2 + length
    return None


def _from_png(data: bytes) -> tuple[datetime, str] | None:
    """Find the eXIf chunk in a PNG and parse the TIFF it carries."""
    offset = 8  # skip the PNG signature
    while offset + 8 <= len(data):
        (length,) = struct.unpack_from(">I", data, offset)
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + length
        if chunk_end > len(data):
            return None
        if chunk_type == b"eXIf":
            return _from_tiff(data[chunk_start:chunk_end])
        if chunk_type == b"IEND":
            return None
        offset = chunk_end + 4  # skip the CRC too
    return None


def _from_tiff(tiff: bytes) -> tuple[datetime, str] | None:
    """Parse a TIFF header and return the best date tag it holds."""
    if len(tiff) < 8:
        return None
    order = tiff[:2]
    if order == b"II":
        prefix = "<"
    elif order == b"MM":
        prefix = ">"
    else:
        return None
    (magic,) = struct.unpack_from(prefix + "H", tiff, 2)
    if magic != 42:
        return None
    (ifd_offset,) = struct.unpack_from(prefix + "I", tiff, 4)
    found: dict[int, str] = {}
    _read_ifd(tiff, ifd_offset, prefix, found, depth=0)
    for tag, label in (
        (TAG_DATETIME_ORIGINAL, "EXIF DateTimeOriginal"),
        (TAG_DATETIME_DIGITIZED, "EXIF DateTimeDigitized"),
        (TAG_DATETIME, "EXIF DateTime"),
    ):
        raw = found.get(tag)
        if raw is None:
            continue
        parsed = _parse_exif_date(raw)
        if parsed is not None:
            return parsed, label
    return None


def _read_ifd(
    tiff: bytes, offset: int, prefix: str, found: dict[int, str], depth: int
) -> None:
    """Read one IFD, collecting the date tags we care about.

    ``depth`` stops at one level of Exif-IFD nesting — real files never nest
    deeper, and a corrupt offset pointing back at itself shouldn't loop us.
    """
    if depth > 1 or offset < 0 or offset + 2 > len(tiff):
        return
    (count,) = struct.unpack_from(prefix + "H", tiff, offset)
    cursor = offset + 2
    for _ in range(count):
        if cursor + 12 > len(tiff):
            return
        tag, field_type, value_count = struct.unpack_from(
            prefix + "HHI", tiff, cursor
        )
        type_size = _TYPE_SIZES.get(field_type)
        if type_size is None:
            cursor += 12
            continue
        total_bytes = type_size * value_count
        if total_bytes <= 4:
            value_start = cursor + 8
        else:
            (value_start,) = struct.unpack_from(prefix + "I", tiff, cursor + 8)
        if tag == TAG_EXIF_IFD and field_type == 4 and value_count == 1:
            (sub_offset,) = struct.unpack_from(prefix + "I", tiff, cursor + 8)
            _read_ifd(tiff, sub_offset, prefix, found, depth + 1)
        elif tag in (TAG_DATETIME, TAG_DATETIME_ORIGINAL, TAG_DATETIME_DIGITIZED):
            if field_type == 2 and 0 <= value_start < len(tiff):
                raw = tiff[value_start : value_start + value_count]
                found[tag] = raw.split(b"\x00", 1)[0].decode("ascii", "replace")
        cursor += 12
