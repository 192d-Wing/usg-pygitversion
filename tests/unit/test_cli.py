# SPDX-License-Identifier: MIT
"""Tests for the Phase 0 CLI surface."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pygitversion import __version__
from pygitversion.cli.main import main, translate_dotnet_style


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["/version"], ["--version"]),
        (["/?"], ["--help"]),
        (["/verbosity", "Quiet"], ["--verbosity", "Quiet"]),
        (["/l", "out.log"], ["--log-file", "out.log"]),
        # Absolute POSIX paths must survive untouched.
        (["/home/me/repo"], ["/home/me/repo"]),
        (["--version"], ["--version"]),
        (["/b", "main", "--nofetch"], ["--branch", "main", "--nofetch"]),
    ],
)
def test_translate_dotnet_style(argv: list[str], expected: list[str]) -> None:
    assert translate_dotnet_style(argv) == expected


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["/version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_help_exits_zero() -> None:
    assert main(["/?"]) == 0


def test_bad_verbosity_is_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--verbosity", "loud"])
    assert exc.value.code == 2


def test_unported_path_fails_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    # Phase 0: calculation is not wired; the CLI must fail with exit 1 and a
    # one-line message, no traceback (SI-11).
    assert main([]) == 1
    err = capsys.readouterr().err
    assert "Phase 3" in err
    assert "Traceback" not in err


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pygitversion", "/version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == __version__
