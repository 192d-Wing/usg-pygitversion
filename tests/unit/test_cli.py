# SPDX-License-Identifier: MIT
"""Tests for the CLI entry point (help, version, error reporting, module invocation)."""

from __future__ import annotations

import subprocess
import sys

import pytest
from usg_pygitversion import __version__
from usg_pygitversion.cli.main import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["/version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


@pytest.mark.parametrize("flag", ["/?", "-h", "--help", "?", "/help"])
def test_help_exits_zero_and_shows_banner(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([flag]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"GitVersion {__version__}\n\n")
    assert "/showvariable" in out
    assert "/output env" in out


def test_bad_verbosity_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--verbosity", "loud"]) == 1
    assert "Could not parse Verbosity value 'loud'" in capsys.readouterr().err


def test_not_a_repository_fails_cleanly(
    tmp_path: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("An error occurred:\n")
    assert "Traceback" not in err


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "usg_pygitversion", "/version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == __version__
