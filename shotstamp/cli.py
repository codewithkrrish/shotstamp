"""Command line entry point — thin on purpose.

Everything interesting lives in exif.py and rename.py so it can be tested
without a shell. This file just parses flags, prints what happened, and
picks the exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import BadPatternError, ShotstampError
from .rename import (
    DEFAULT_EXTENSIONS,
    DEFAULT_PATTERN,
    apply_renames,
    collect_files,
    plan_renames,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shotstamp",
        description=(
            "Rename camera-roll photos by the date they were taken, "
            "so IMG_4829.jpg becomes 2026-11-18_09-41-23.jpg."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="photo files and/or folders to rename",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="descend into subfolders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would happen without renaming anything",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=(
            "strftime pattern for the new name "
            "(default: YYYY-MM-DD_HH-MM-SS style)"
        ),
    )
    parser.add_argument(
        "--extensions",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help=(
            "comma-separated extensions to rename "
            f'(default: {",".join(sorted(DEFAULT_EXTENSIONS))})'
        ),
    )
    parser.add_argument(
        "--no-mtime",
        action="store_true",
        help="don't fall back to the file modified time when EXIF is missing",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only print the summary line",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def parse_extensions(raw: str) -> set[str]:
    extensions = set()
    for piece in raw.split(","):
        piece = piece.strip().lower()
        if not piece:
            continue
        extensions.add(piece if piece.startswith(".") else f".{piece}")
    if not extensions:
        raise BadPatternError("the --extensions list is empty.")
    return extensions


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        extensions = parse_extensions(args.extensions)
    except BadPatternError as exc:
        print(f"shotstamp: {exc}", file=sys.stderr)
        return EXIT_USAGE

    missing = [str(p) for p in args.paths if not p.exists()]
    if missing:
        for path in missing:
            print(f"shotstamp: no such file or folder: {path}", file=sys.stderr)
        return EXIT_USAGE

    try:
        plans = plan_renames(
            collect_files(args.paths, args.recursive, extensions),
            pattern=args.pattern,
            use_mtime=not args.no_mtime,
        )
    except BadPatternError as exc:
        print(f"shotstamp: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not plans:
        print("shotstamp: nothing to rename — no matching photos found.")
        return EXIT_OK

    for plan in plans:
        if args.quiet:
            continue
        if plan.skipped:
            print(f"  skip {plan.source.name} ({plan.skip_reason})")
        elif plan.target is not None:
            verb = "would rename" if args.dry_run else "rename"
            print(
                f"  {verb} {plan.source.name} -> {plan.target.name}"
                f"  [{plan.date_source}]"
            )

    report = apply_renames(plans, dry_run=args.dry_run)
    if args.dry_run:
        summary = (
            f"dry run: {report.renamed} would be renamed, "
            f"{report.skipped} skipped"
        )
    else:
        summary = (
            f"renamed {report.renamed}, skipped {report.skipped}, "
            f"failed {report.failed}"
        )
    print(f"shotstamp: {summary}.")
    for failure in report.failures:
        print(f"shotstamp: failed: {failure}", file=sys.stderr)
    return EXIT_FAILED if report.failed else EXIT_OK


def run() -> None:
    """Console-script entry point: exit with the right code, no traceback."""
    try:
        sys.exit(main())
    except ShotstampError as exc:  # pragma: no cover - safety net
        print(f"shotstamp: {exc}", file=sys.stderr)
        sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    run()
