"""Tests for rename planning and applying."""

import os
from datetime import datetime
from pathlib import Path

import pytest
from conftest import make_jpeg
from shotstamp.errors import BadPatternError
from shotstamp.rename import (
    apply_renames,
    collect_files,
    photo_datetime,
    plan_renames,
    validate_pattern,
)


def _set_mtime(path: Path, when: datetime) -> None:
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def test_plan_uses_exif_date(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.jpg")
    (plan,) = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    assert plan.target is not None
    assert plan.target.name == "2026-11-18_09-41-23.jpg"
    assert plan.date_source == "EXIF DateTimeOriginal"
    assert not plan.skipped


def test_plan_falls_back_to_mtime(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "screenshot.jpg", exif_date=None)
    _set_mtime(photo, datetime(2024, 1, 5, 12, 0, 0))
    (plan,) = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    assert plan.target is not None
    assert plan.target.name == "2024-01-05_12-00-00.jpg"
    assert plan.date_source == "file modified time"


def test_no_mtime_fallback_skips_the_file(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "screenshot.jpg", exif_date=None)
    (plan,) = plan_renames([photo], "%Y-%m-%d_%H-%M-%S", use_mtime=False)
    assert plan.skipped
    assert "no EXIF date" in plan.skip_reason


def test_burst_shots_get_numbered_suffixes(tmp_path: Path) -> None:
    # Three photos, same second: -2 and -3 keep them distinct.
    photos = [make_jpeg(tmp_path / f"DSC_{n}.jpg") for n in (1, 2, 3)]
    plans = plan_renames(photos, "%Y-%m-%d_%H-%M-%S")
    names = [p.target.name for p in plans if p.target is not None]
    assert names == [
        "2026-11-18_09-41-23.jpg",
        "2026-11-18_09-41-23-2.jpg",
        "2026-11-18_09-41-23-3.jpg",
    ]


def test_existing_file_on_disk_forces_a_suffix(tmp_path: Path) -> None:
    make_jpeg(tmp_path / "2026-11-18_09-41-23.jpg")
    newcomer = make_jpeg(tmp_path / "IMG_9999.jpg")
    plans = plan_renames([newcomer], "%Y-%m-%d_%H-%M-%S")
    assert plans[0].target is not None
    assert plans[0].target.name == "2026-11-18_09-41-23-2.jpg"


def test_already_named_file_is_skipped(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "2026-11-18_09-41-23.jpg")
    (plan,) = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    assert plan.skipped
    assert plan.skip_reason == "already named that"


def test_apply_actually_renames(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.jpg")
    plans = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    report = apply_renames(plans, dry_run=False)
    assert report.renamed == 1
    assert (tmp_path / "2026-11-18_09-41-23.jpg").exists()
    assert not photo.exists()


def test_dry_run_touches_nothing(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.jpg")
    plans = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    report = apply_renames(plans, dry_run=True)
    assert report.renamed == 1  # counted as "would rename"
    assert photo.exists()
    assert not (tmp_path / "2026-11-18_09-41-23.jpg").exists()


def test_custom_pattern(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.jpg")
    (plan,) = plan_renames([photo], "%Y%m%d_%H%M%S")
    assert plan.target is not None
    assert plan.target.name == "20261118_094123.jpg"


def test_bad_patterns_are_rejected() -> None:
    with pytest.raises(BadPatternError):
        validate_pattern("")
    with pytest.raises(BadPatternError):
        validate_pattern("%Y/%m/%d")
    with pytest.raises(BadPatternError):
        validate_pattern("%Q %Y")  # not a real strftime directive


def test_collect_files_filters_extensions(tmp_path: Path) -> None:
    make_jpeg(tmp_path / "a.jpg")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "clip.mp4").write_bytes(b"fake video")
    found = collect_files([tmp_path], recursive=False, extensions={".jpg"})
    assert [p.name for p in found] == ["a.jpg"]


def test_collect_files_recursive(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    make_jpeg(tmp_path / "top.jpg")
    make_jpeg(sub / "nested.jpg")
    flat = collect_files([tmp_path], recursive=False, extensions={".jpg"})
    deep = collect_files([tmp_path], recursive=True, extensions={".jpg"})
    assert [p.name for p in flat] == ["top.jpg"]
    assert sorted(p.name for p in deep) == ["nested.jpg", "top.jpg"]


def test_photo_datetime_missing_file(tmp_path: Path) -> None:
    assert photo_datetime(tmp_path / "gone.jpg") is None


def test_extension_is_lowercased(tmp_path: Path) -> None:
    photo = make_jpeg(tmp_path / "IMG_4829.JPG")
    (plan,) = plan_renames([photo], "%Y-%m-%d_%H-%M-%S")
    assert plan.target is not None
    assert plan.target.name == "2026-11-18_09-41-23.jpg"
