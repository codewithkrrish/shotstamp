"""Shared helpers: build tiny, valid JPEGs with a chosen EXIF date.

These are real files — a SOI marker, one APP1 segment carrying a TIFF
header, then EOI — so the EXIF reader is tested against actual bytes, not
a mocked parser.
"""

from __future__ import annotations

import struct
from pathlib import Path

EXIF_DATE = "2026:11:18 09:41:23"
EXIF_DATE_2 = "2025:03:02 18:05:44"


def _tiff(exif_date: str | None, big_endian: bool = False) -> bytes:
    """A minimal TIFF header holding one DateTimeOriginal tag."""
    prefix = ">" if big_endian else "<"
    order = b"MM" if big_endian else b"II"
    header = order + struct.pack(prefix + "H", 42) + struct.pack(prefix + "I", 8)

    if exif_date is None:
        # IFD0 with zero entries — valid TIFF, no date anywhere.
        return header + struct.pack(prefix + "H", 0) + struct.pack(prefix + "I", 0)

    date_bytes = exif_date.encode("ascii") + b"\x00"
    # Layout: header (8) + IFD0 (2 + 12 + 4) + Exif IFD (2 + 12 + 4) + string.
    exif_ifd_offset = 8 + 18
    string_offset = exif_ifd_offset + 18
    ifd0 = (
        struct.pack(prefix + "H", 1)
        + struct.pack(prefix + "HHI", 0x8769, 4, 1)
        + struct.pack(prefix + "I", exif_ifd_offset)
        + struct.pack(prefix + "I", 0)
    )
    exif_ifd = (
        struct.pack(prefix + "H", 1)
        + struct.pack(prefix + "HHI", 0x9003, 2, len(date_bytes))
        + struct.pack(prefix + "I", string_offset)
        + struct.pack(prefix + "I", 0)
    )
    return header + ifd0 + exif_ifd + date_bytes


def make_jpeg(path: Path, exif_date: str | None = EXIF_DATE, big_endian: bool = False) -> Path:
    """Write a minimal JPEG with (or without) an EXIF DateTimeOriginal."""
    app1 = b"Exif\x00\x00" + _tiff(exif_date, big_endian)
    segment = b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    path.write_bytes(b"\xff\xd8" + segment + b"\xff\xd9")
    return path


def make_png(path: Path, exif_date: str | None = EXIF_DATE) -> Path:
    """Write a minimal PNG carrying its EXIF in an eXIf chunk."""
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if exif_date is not None:
        png += chunk(b"eXIf", _tiff(exif_date))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    return path
