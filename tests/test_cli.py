"""End-to-end CLI tests — main() called the way the console script does."""

from pathlib import Path

import pytest
from conftest import make_jpeg
from shotstamp.cli import EXIT_OK, EXIT_USAGE, main


def test_cli_dry_run_lists_renames(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    make_jpeg(tmp_path / "IMG_4829.jpg")
    code = main([str(tmp_path), "--dry-run"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "would rename IMG_4829.jpg -> 2026-11-18_09-41-23.jpg" in out
    assert "dry run: 1 would be renamed" in out
    assert (tmp_path / "IMG_4829.jpg").exists()


def test_cli_renames_for_real(tmp_path: Path) -> None:
    make_jpeg(tmp_path / "IMG_4829.jpg")
    code = main([str(tmp_path)])
    assert code == EXIT_OK
    assert (tmp_path / "2026-11-18_09-41-23.jpg").exists()


def test_cli_missing_path_is_usage_error(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = main([str(tmp_path / "nope")])
    assert code == EXIT_USAGE
    assert "no such file or folder" in capsys.readouterr().err


def test_cli_bad_pattern_is_usage_error(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    make_jpeg(tmp_path / "IMG_4829.jpg")
    code = main([str(tmp_path), "--pattern", "%Y/%m"])
    assert code == EXIT_USAGE
    assert "must not contain" in capsys.readouterr().err


def test_cli_empty_folder_is_ok(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = main([str(tmp_path)])
    assert code == EXIT_OK
    assert "nothing to rename" in capsys.readouterr().out


def test_cli_help_renders(capsys: pytest.CaptureFixture[str]) -> None:
    # --help used to crash: argparse %-formats help text, and the pattern
    # example contained %Y. Guard against that coming back.
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "strftime pattern" in capsys.readouterr().out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "shotstamp 1.0.0" in capsys.readouterr().out


def test_cli_quiet_only_prints_summary(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    make_jpeg(tmp_path / "IMG_4829.jpg")
    code = main([str(tmp_path), "--quiet"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "IMG_4829.jpg" not in out
    assert "renamed 1" in out
