"""Planning and applying renames.

Two phases, deliberately separate: first work out every new name (so a
collision in file #200 can't leave files #1-199 half-renamed), then apply
them. ``--dry-run`` just stops after phase one and prints the plan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .errors import BadPatternError
from .exif import read_exif_datetime

DEFAULT_PATTERN = "%Y-%m-%d_%H-%M-%S"

# The extensions shotstamp looks at unless told otherwise.
DEFAULT_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff"})


@dataclass
class RenamePlan:
    """One file's fate: where it goes, why, or why it's being skipped."""

    source: Path
    target: Path | None = None
    taken_at: datetime | None = None
    date_source: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class RenameReport:
    """What actually happened, for the summary line and the exit code."""

    renamed: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


def validate_pattern(pattern: str) -> None:
    """Reject patterns that can't be a filename, before touching anything."""
    if not pattern or pattern.strip() == "":
        raise BadPatternError("the --pattern is empty.")
    if "/" in pattern or "\\" in pattern or "\x00" in pattern:
        raise BadPatternError(
            "the --pattern must not contain / or \\ — it becomes a filename."
        )
    try:
        sample = datetime(2026, 11, 19, 9, 8, 7).strftime(pattern)
    except ValueError as exc:
        raise BadPatternError(f"the --pattern is not a valid date format: {exc}") from exc
    if not sample:
        raise BadPatternError("the --pattern formats to an empty name.")
    # strftime silently leaves unknown directives (like %Q) untouched, so
    # a "%" followed by a letter in the output means a typo in the pattern.
    for index, char in enumerate(sample):
        if char == "%" and index + 1 < len(sample) and sample[index + 1].isalpha():
            raise BadPatternError(
                f"the --pattern contains an unknown date directive: %{sample[index + 1]}"
            )


def photo_datetime(path: Path, use_mtime: bool = True) -> tuple[datetime, str] | None:
    """When a photo was taken: EXIF first, file modified time as fallback."""
    exif = read_exif_datetime(path)
    if exif is not None:
        return exif
    if use_mtime:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None
        return mtime, "file modified time"
    return None


def collect_files(paths: list[Path], recursive: bool, extensions: set[str]) -> list[Path]:
    """Expand the given files and folders into a sorted list of photos.

    Folders contribute their files (direct children, or everything below
    them with --recursive). Unknown paths are reported by the caller, not
    silently dropped, so a typo doesn't look like an empty folder.
    """
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in extensions:
                found.append(path)
        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            for entry in sorted(iterator):
                if entry.is_file() and entry.suffix.lower() in extensions:
                    found.append(entry)
    return found


def plan_renames(
    files: list[Path], pattern: str, use_mtime: bool = True
) -> list[RenamePlan]:
    """Work out the new name for every file, resolving collisions up front.

    Two burst shots in the same second get ``-2``, ``-3`` and so on. A file
    that already has the right name is left alone — running shotstamp twice
    over the same folder is a no-op, not a mess.
    """
    validate_pattern(pattern)
    plans: list[RenamePlan] = []
    claimed: set[str] = set()
    for source in files:
        stamp = photo_datetime(source, use_mtime=use_mtime)
        if stamp is None:
            plans.append(
                RenamePlan(
                    source=source,
                    skipped=True,
                    skip_reason="no EXIF date and no usable file time",
                )
            )
            continue
        taken_at, date_source = stamp
        base = taken_at.strftime(pattern)
        suffix = source.suffix.lower()
        candidate = f"{base}{suffix}"
        serial = 2
        while candidate.lower() in claimed or (
            (source.parent / candidate).exists()
            and (source.parent / candidate).resolve() != source.resolve()
        ):
            candidate = f"{base}-{serial}{suffix}"
            serial += 1
        claimed.add(candidate.lower())
        target = source.parent / candidate
        if target.resolve() == source.resolve():
            plans.append(
                RenamePlan(
                    source=source,
                    taken_at=taken_at,
                    date_source=date_source,
                    skipped=True,
                    skip_reason="already named that",
                )
            )
        else:
            plans.append(
                RenamePlan(
                    source=source,
                    target=target,
                    taken_at=taken_at,
                    date_source=date_source,
                )
            )
    return plans


def apply_renames(plans: list[RenamePlan], dry_run: bool) -> RenameReport:
    """Carry out the plan (or just print it, with --dry-run)."""
    report = RenameReport()
    for plan in plans:
        if plan.skipped or plan.target is None:
            report.skipped += 1
            continue
        if dry_run:
            report.renamed += 1  # "would rename", counted the same way
            continue
        try:
            # os.rename is atomic on one filesystem — a crash mid-rename
            # can't leave a half-written file behind.
            os.rename(plan.source, plan.target)
        except OSError as exc:
            report.failed += 1
            report.failures.append(f"{plan.source.name}: {exc.strerror or exc}")
        else:
            report.renamed += 1
    return report
