"""Tests for the EXIF reader — real files, hand-built in conftest.py."""

from datetime import datetime
from pathlib import Path

from conftest import EXIF_DATE, EXIF_DATE_2, make_jpeg, make_png
from shotstamp.exif import read_exif_datetime


def test_reads_datetime_original(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.jpg")
    result = read_exif_datetime(photo)
    assert result is not None
    taken, source = result
    assert taken == datetime(2026, 11, 18, 9, 41, 23)
    assert source == "EXIF DateTimeOriginal"


def test_reads_big_endian_tiff(tmp_path: Path) -> None:
    # Some cameras write Motorola byte order; the parser must handle both.
    photo = make_jpeg(tmp_path / "IMG_4830.jpg", big_endian=True)
    result = read_exif_datetime(photo)
    assert result is not None
    assert result[0] == datetime(2026, 11, 18, 9, 41, 23)


def test_reads_png_exif_chunk(tmp_path: Path) -> None:
    photo = make_png(tmp_path / "shot.png", exif_date=EXIF_DATE_2)
    result = read_exif_datetime(photo)
    assert result is not None
    assert result[0] == datetime(2025, 3, 2, 18, 5, 44)


def test_no_exif_returns_none(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "screenshot.jpg", exif_date=None)
    assert read_exif_datetime(photo) is None


def test_png_without_exif_returns_none(tmp_path: Path) -> None:
    photo = make_png(tmp_path / "plain.png", exif_date=None)
    assert read_exif_datetime(photo) is None


def test_not_a_photo_returns_none(tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a photo at all")
    assert read_exif_datetime(text) is None


def test_empty_file_returns_none(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jpg"
    empty.write_bytes(b"")
    assert read_exif_datetime(empty) is None


def test_truncated_jpeg_returns_none(tmp_path: Path) -> None:
    # SOI marker, then a segment header claiming more bytes than exist.
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"\xff\xd8\xff\xe1\x10\x00Exif")
    assert read_exif_datetime(broken) is None


def test_corrupt_tiff_magic_returns_none(tmp_path: Path) -> None:
    # Valid JPEG + APP1, but the TIFF magic number is wrong.
    import struct

    bad_tiff = b"II" + struct.pack("<H", 41) + struct.pack("<I", 8) + b"\x00" * 8
    app1 = b"Exif\x00\x00" + bad_tiff
    segment = b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    photo = tmp_path / "bad.jpg"
    photo.write_bytes(b"\xff\xd8" + segment + b"\xff\xd9")
    assert read_exif_datetime(photo) is None


def test_garbage_exif_date_is_ignored(tmp_path: Path) -> None:
    # A camera that wrote "0000:00:00 00:00:00" shouldn't rename to year 0.
    photo = make_jpeg(tmp_path / "weird.jpg", exif_date="0000:00:00 00:00:00")
    assert read_exif_datetime(photo) is None


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_exif_datetime(tmp_path / "does-not-exist.jpg") is None
