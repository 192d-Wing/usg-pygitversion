# SPDX-License-Identifier: MIT
"""Tests for the ported argument parser (upstream ``ArgumentParserTests`` subset)."""

from __future__ import annotations

from pathlib import Path

import pytest
from usg_pygitversion._logging import Verbosity
from usg_pygitversion.buildagents.envexport import Shell
from usg_pygitversion.cli.arguments import DEFAULT_OUTPUT_FILE_NAME, OutputType, parse_arguments
from usg_pygitversion.errors import UsageError


def test_empty_means_json_in_current_directory(tmp_path: Path) -> None:
    args = parse_arguments([], current_directory=str(tmp_path))
    assert args.target_path == str(tmp_path)
    assert args.output == {OutputType.JSON}
    assert args.no_fetch is True


@pytest.mark.parametrize("flag", ["/?", "-h", "--help", "?", "/H"])
def test_help_forms(flag: str) -> None:
    assert parse_arguments([flag]).is_help


def test_version_forms() -> None:
    assert parse_arguments(["/version"]).is_version
    assert parse_arguments(["--version"]).is_version


def test_first_argument_is_the_target_path(tmp_path: Path) -> None:
    args = parse_arguments([str(tmp_path) + "/", "/showvariable", "SemVer"])
    assert args.target_path == str(tmp_path)
    assert args.show_variable == "SemVer"


def test_switches_are_case_insensitive_and_accept_all_prefixes(tmp_path: Path) -> None:
    args = parse_arguments(
        ["-B", "main", "/C", "abc", "--log-file", "x.log", "/OUTPUT", "dotenv", "-nocache"],
        current_directory=str(tmp_path),
    )
    assert args.target_branch == "main"
    assert args.commit_id == "abc"
    assert args.log_file_path == "x.log"
    assert args.output == {OutputType.DOTENV}
    assert args.no_cache is True
    assert args.target_path == str(tmp_path)


def test_multiple_outputs_and_default_output_file(tmp_path: Path) -> None:
    args = parse_arguments(["/output", "json", "/output", "file"], current_directory=str(tmp_path))
    assert args.output == {OutputType.JSON, OutputType.FILE}
    assert args.output_file == DEFAULT_OUTPUT_FILE_NAME
    args = parse_arguments(["/output", "json", "buildserver"], current_directory=str(tmp_path))
    assert args.output == {OutputType.JSON, OutputType.BUILDSERVER}


def test_env_output_alone_does_not_add_json(tmp_path: Path) -> None:
    args = parse_arguments(
        ["--output", "env", "--shell", "PowerShell", "--prefix", "APP_"],
        current_directory=str(tmp_path),
    )
    assert args.output == {OutputType.ENV}
    assert args.shell is Shell.POWERSHELL
    assert args.prefix == "APP_"


def test_env_file_option(tmp_path: Path) -> None:
    args = parse_arguments(["--env-file", "vars.env"], current_directory=str(tmp_path))
    assert args.env_file == "vars.env"
    assert args.output == {OutputType.JSON}


def test_show_variable_is_case_insensitive_and_unquoted(tmp_path: Path) -> None:
    args = parse_arguments(["/showvariable", "'semver'"], current_directory=str(tmp_path))
    assert args.show_variable == "SemVer"


def test_show_variable_rejects_unknown(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="requires a valid version variable"):
        parse_arguments(["/showvariable", "Nope"], current_directory=str(tmp_path))


def test_format_requires_a_variable(tmp_path: Path) -> None:
    assert parse_arguments(["/format", "{Major}.{Minor}"], current_directory=str(tmp_path)).format
    with pytest.raises(UsageError, match="Format requires a valid format string"):
        parse_arguments(["/format", "{Nope}"], current_directory=str(tmp_path))


def test_bad_output_type(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="cannot be parsed as output type"):
        parse_arguments(["/output", "bogus"], current_directory=str(tmp_path))


def test_unknown_switch_is_reported(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="Could not parse command line parameter '/bogus'"):
        parse_arguments(["/bogus"], current_directory=str(tmp_path))


def test_out_of_scope_switches_are_rejected_clearly(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="out of scope"):
        parse_arguments(["/updateassemblyinfo"], current_directory=str(tmp_path))


def test_override_config(tmp_path: Path) -> None:
    args = parse_arguments(
        ["/overrideconfig", "tag-prefix=v", "/overrideconfig", "next-version=1.2.3"],
        current_directory=str(tmp_path),
    )
    assert args.override_configuration == {"tag-prefix": "v", "next-version": "1.2.3"}
    with pytest.raises(UsageError, match="Unsupported key 'bogus'"):
        parse_arguments(["/overrideconfig", "bogus=1"], current_directory=str(tmp_path))


def test_showconfig_values(tmp_path: Path) -> None:
    assert parse_arguments(["/showconfig"], current_directory=str(tmp_path)).show_configuration
    assert not parse_arguments(
        ["/showconfig", "false"], current_directory=str(tmp_path)
    ).show_configuration


def test_config_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="Could not find config file"):
        parse_arguments(["/config", "missing.yml"], current_directory=str(tmp_path))
    (tmp_path / "custom.yml").write_text("next-version: 1.0.0\n")
    args = parse_arguments(["/config", "custom.yml"], current_directory=str(tmp_path))
    assert args.configuration_file == str((tmp_path / "custom.yml").resolve())


def test_verbosity_and_diag(tmp_path: Path) -> None:
    args = parse_arguments(["/verbosity", "diagnostic", "/diag"], current_directory=str(tmp_path))
    assert args.verbosity is Verbosity.DIAGNOSTIC
    assert args.diag is True


def test_too_many_values(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="Could not parse command line parameter 'extra'"):
        parse_arguments(["/b", "main", "extra"], current_directory=str(tmp_path))


@pytest.mark.parametrize("value", ["--output=/tmp/x", "-n", "--all"])
def test_commit_id_must_not_look_like_an_option(tmp_path: Path, value: str) -> None:
    # `/c` consumes the next token whatever it looks like; a leading `-`
    # would otherwise be handed to `git log` as an option (SI-10).
    with pytest.raises(UsageError, match="must not start with '-'"):
        parse_arguments(["/c", value], current_directory=str(tmp_path))
    with pytest.raises(UsageError, match="requires a commit id"):
        parse_arguments(["/c", "  "], current_directory=str(tmp_path))
