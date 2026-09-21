# SPDX-License-Identifier: MIT
"""Tests for the generic environment export (PLAN.md 7.4 for section 7.5)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pygitversion import export_env
from pygitversion.buildagents.envexport import EnvExporter, Shell
from pygitversion.errors import GitVersionError

from tests.unit.test_output import sample


def test_export_env_populates_mapping_with_every_variable() -> None:
    target: dict[str, str] = {}
    export_env(sample(), target)
    assert target["GitVersion_FullSemVer"] == "1.2.4-1"
    assert target["GitVersion_BuildMetaData"] == ""
    assert len(target) == 28
    export_env(sample(), target, prefix="APP_")
    assert target["APP_Major"] == "1"


def test_invalid_prefix_is_rejected() -> None:
    with pytest.raises(GitVersionError, match="invalid environment variable prefix"):
        EnvExporter("bad prefix")


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_sh_output_is_eval_safe_with_metacharacters(tmp_path: Path) -> None:
    variables = sample()
    hostile = "it's; $(touch " + str(tmp_path / "pwned") + ') `id` "x"'
    variables.values["BranchName"] = hostile  # type: ignore[index]
    script = "\n".join(EnvExporter().shell_lines(variables, Shell.SH))
    result = subprocess.run(
        ["sh", "-c", 'eval "$SCRIPT"; printf %s "$GitVersion_BranchName"'],
        env={**os.environ, "SCRIPT": script},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert result.stdout == hostile
    assert not (tmp_path / "pwned").exists()


def test_powershell_and_cmd_quoting() -> None:
    variables = sample()
    variables.values["BranchName"] = "it's 100%"  # type: ignore[index]
    ps = EnvExporter().shell_lines(variables, Shell.POWERSHELL)
    assert "$env:GitVersion_BranchName = 'it''s 100%'" in ps
    cmd = EnvExporter().shell_lines(variables, Shell.CMD)
    assert 'set "GitVersion_BranchName=it\'s 100%%"' in cmd
    variables.values["BranchName"] = 'has "quote"'  # type: ignore[index]
    with pytest.raises(GitVersionError, match=r"cmd\.exe"):
        EnvExporter().shell_lines(variables, Shell.CMD)


def test_env_file_lines_skip_empty_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "env"
    path.write_text("EXISTING=1\n")
    EnvExporter().append_env_file(path, sample())
    lines = path.read_text().splitlines()
    assert lines[0] == "EXISTING=1"
    assert "GitVersion_BuildMetaData=" not in "\n".join(lines)
    parsed = dict(line.split("=", 1) for line in lines)
    assert parsed["GitVersion_FullSemVer"] == "1.2.4-1"


def test_shell_parse() -> None:
    assert Shell.parse("Bash") is Shell.BASH
    with pytest.raises(GitVersionError, match="Unknown shell"):
        Shell.parse("fish")
