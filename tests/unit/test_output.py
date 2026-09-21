# SPDX-License-Identifier: MIT
"""Tests for the JSON serializer, dotenv lines and the output dispatcher."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pygitversion.buildagents.base import LocalBuild
from pygitversion.calculation.variables import AVAILABLE_VARIABLES, GitVersionVariables
from pygitversion.cli.arguments import Arguments, OutputType
from pygitversion.errors import GitVersionError
from pygitversion.output.generator import dotenv_lines, write_outputs
from pygitversion.output.serializer import from_json, to_json


def sample() -> GitVersionVariables:
    values: dict[str, str | None] = {name: f"v-{name}" for name in AVAILABLE_VARIABLES}
    values.update(
        {
            "Major": "1",
            "Minor": "2",
            "Patch": "4",
            "PreReleaseNumber": "1",
            "WeightedPreReleaseNumber": "55001",
            "BuildMetaData": None,
            "CommitsSinceVersionSource": "1",
            "UncommittedChanges": "0",
            "VersionSourceDistance": "1",
            "PreReleaseLabel": "",
            "FullSemVer": "1.2.4-1",
            "BranchName": "feature/it's",
        }
    )
    return GitVersionVariables(values)


def test_to_json_matches_reference_shape() -> None:
    text = to_json(sample())
    assert text.startswith('{\n  "AssemblySemFileVer": ')
    loaded = json.loads(text)
    assert list(loaded) == sorted(AVAILABLE_VARIABLES)
    assert loaded["Major"] == 1
    assert loaded["BuildMetaData"] is None
    assert loaded["PreReleaseLabel"] == ""
    assert loaded["BranchName"] == "feature/it's"


def test_json_round_trip() -> None:
    original = sample()
    restored = from_json(to_json(original))
    assert restored["Major"] == "1"
    assert restored["BuildMetaData"] is None
    assert restored["PreReleaseLabel"] == ""
    assert restored["BranchName"] == original["BranchName"]


@pytest.mark.parametrize(
    "text",
    ["[]", "{", '{"Major": 1}', '{"' + '", "'.join(AVAILABLE_VARIABLES) + '": true}'],
)
def test_from_json_rejects_bad_documents(text: str) -> None:
    with pytest.raises(GitVersionError):
        from_json(text)


def test_dotenv_lines_are_sorted_and_quoted_like_upstream() -> None:
    lines = dotenv_lines(sample())
    assert lines[0] == "GitVersion_AssemblySemFileVer='v-AssemblySemFileVer'"
    assert "GitVersion_BuildMetaData=''" in lines
    assert len(lines) == len(AVAILABLE_VARIABLES)


def _collect() -> tuple[list[str], Callable[[str], None]]:
    lines: list[str] = []
    return lines, lines.append


def test_dispatcher_json_file_and_show_variable(tmp_path: Path) -> None:
    args = Arguments(
        target_path=str(tmp_path), output={OutputType.JSON, OutputType.FILE}, output_file="out.json"
    )
    lines, writer = _collect()
    write_outputs(
        sample(), args, LocalBuild({}, tmp_path), writer, update_build_number=True, environment={}
    )
    assert json.loads("\n".join(lines))["FullSemVer"] == "1.2.4-1"
    assert json.loads((tmp_path / "out.json").read_text())["FullSemVer"] == "1.2.4-1"

    args = Arguments(
        target_path=str(tmp_path), output={OutputType.JSON}, show_variable="FullSemVer"
    )
    lines, writer = _collect()
    write_outputs(
        sample(), args, LocalBuild({}, tmp_path), writer, update_build_number=True, environment={}
    )
    assert lines == ["1.2.4-1"]


def test_dispatcher_format_and_conflicts(tmp_path: Path) -> None:
    args = Arguments(
        target_path=str(tmp_path), output={OutputType.JSON}, format="{Major}.{Minor} {env:X}"
    )
    lines, writer = _collect()
    write_outputs(
        sample(),
        args,
        LocalBuild({}, tmp_path),
        writer,
        update_build_number=True,
        environment={"X": "y"},
    )
    assert lines == ["1.2 y"]
    args.show_variable = "SemVer"
    with pytest.raises(GitVersionError, match="Cannot specify both"):
        write_outputs(
            sample(),
            args,
            LocalBuild({}, tmp_path),
            writer,
            update_build_number=True,
            environment={},
        )


def test_dispatcher_dotenv_suppresses_json_and_env_is_additive(tmp_path: Path) -> None:
    args = Arguments(target_path=str(tmp_path), output={OutputType.JSON, OutputType.DOTENV})
    lines, writer = _collect()
    write_outputs(
        sample(), args, LocalBuild({}, tmp_path), writer, update_build_number=True, environment={}
    )
    assert all(line.startswith("GitVersion_") for line in lines)

    args = Arguments(
        target_path=str(tmp_path), output={OutputType.ENV}, env_file=str(tmp_path / "vars.env")
    )
    lines, writer = _collect()
    write_outputs(
        sample(), args, LocalBuild({}, tmp_path), writer, update_build_number=True, environment={}
    )
    assert lines[0].startswith("export GitVersion_AssemblySemFileVer=")
    assert "GitVersion_FullSemVer=1.2.4-1" in (tmp_path / "vars.env").read_text().splitlines()
