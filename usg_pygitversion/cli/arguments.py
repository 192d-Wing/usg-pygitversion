# SPDX-License-Identifier: MIT
"""Command-line argument parsing. Ports ``ArgumentParser``/``Arguments`` (6.8.2).

The reference parser is hand-written: switches start with ``-`` or ``/``,
are matched case-insensitively, and the first non-switch argument is the
target path. This port keeps those semantics (so every documented
invocation keeps working) and adds the POSIX ``--name`` spelling plus the
``env`` output options from PLAN.md section 7.5.

Security (SI-10): every value is validated here before use. Output types,
verbosities, shells, variable names and override keys are matched against
allow-lists; paths are only checked for existence, never interpreted.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from usg_pygitversion._logging import Verbosity
from usg_pygitversion.buildagents.envexport import DEFAULT_PREFIX, Shell
from usg_pygitversion.calculation.variables import AVAILABLE_VARIABLES
from usg_pygitversion.config.override import parse_override_options
from usg_pygitversion.errors import ConfigurationError, UsageError

DEFAULT_OUTPUT_FILE_NAME = "GitVersion.json"

#: POSIX long names mapped onto the upstream switch names.
_ALIASES: dict[str, str] = {
    "log-file": "l",
    "logfile": "l",
    "branch": "b",
    "commit": "c",
    "username": "u",
    "password": "p",
    "show-variable": "showvariable",
    "show-config": "showconfig",
    "override-config": "overrideconfig",
    "output-file": "outputfile",
    "env-file": "envfile",
    "no-fetch": "nofetch",
    "no-cache": "nocache",
    "no-normalize": "nonormalize",
    "allow-shallow": "allowshallow",
    "target-path": "targetpath",
    "help": "h",
}

#: Switches that never take a value (``ArgumentRequiresValue``).
_BOOLEAN_SWITCHES: frozenset[str] = frozenset(
    {
        "updateassemblyinfo",
        "ensureassemblyinfo",
        "nofetch",
        "nonormalize",
        "nocache",
        "allowshallow",
        "diag",
    }
)

#: Upstream switches whose feature is out of scope for the port.
_UNSUPPORTED: dict[str, str] = {
    "updateassemblyinfo": "AssemblyInfo updating",
    "ensureassemblyinfo": "AssemblyInfo updating",
    "updateprojectfiles": "project file updating",
    "updatewixversionfile": "WiX version files",
    "url": "dynamic repository cloning (/url)",
    "dynamicrepolocation": "dynamic repository cloning (/dynamicRepoLocation)",
    "u": "remote authentication",
    "p": "remote authentication",
}

_TRUE_VALUES = ("1", "true")
_FALSE_VALUES = ("0", "false")


class OutputType(StrEnum):
    """``/output`` values; ``env`` is the usg-pygitversion addition."""

    JSON = "json"
    FILE = "file"
    BUILDSERVER = "buildserver"
    DOTENV = "dotenv"
    ENV = "env"


@dataclass
class Arguments:
    """Parsed command line. Mirrors upstream ``Arguments`` minus out-of-scope fields."""

    target_path: str | None = None
    configuration_file: str | None = None
    override_configuration: dict[str, Any] = field(default_factory=dict)
    show_configuration: bool = False
    target_branch: str | None = None
    commit_id: str | None = None
    diag: bool = False
    is_version: bool = False
    is_help: bool = False
    no_fetch: bool = False
    no_cache: bool = False
    no_normalize: bool = False
    allow_shallow: bool = False
    log_file_path: str | None = None
    show_variable: str | None = None
    format: str | None = None
    output_file: str | None = None
    output: set[OutputType] = field(default_factory=set)
    verbosity: Verbosity = Verbosity.NORMAL
    # usg-pygitversion additions (PLAN.md 7.5)
    shell: Shell = Shell.SH
    prefix: str = DEFAULT_PREFIX
    env_file: str | None = None

    @property
    def working_directory(self) -> Path:
        """``target_path`` as a path (always set after parsing)."""
        return Path(self.target_path) if self.target_path else Path.cwd()


def _is_switch_argument(value: str | None) -> bool:
    """Ports ``IsSwitchArgument``: ``-x``/``/x`` but not ``/p:Prop=Value`` style."""
    if value is None or not value.startswith(("-", "/")):
        return False
    body = value.lstrip("-/")
    return ":" not in body.split("=", 1)[0]


def _switch_name(value: str) -> str:
    """Strip the prefix (``--x``, ``-x``, ``/x``), apply aliases, lower-case."""
    name = value
    if name.startswith("--"):
        name = name[2:]
    elif name.startswith(("-", "/")):
        name = name[1:]
    name = name.lower()
    return _ALIASES.get(name, name)


def _is_valid_path(value: str) -> bool:
    return os.sep == "/" and Path(value).is_dir()


def _requires_value(argument: str, index: int) -> bool:
    """Ports ``ArgumentRequiresValue``."""
    name = _switch_name(argument)
    might = name not in _BOOLEAN_SWITCHES
    if might and index == 0 and argument.startswith("/") and _is_valid_path(argument):
        return False
    return might


def _collect(argv: Sequence[str]) -> tuple[list[tuple[str, list[str]]], bool]:
    """Ports ``CollectSwitchesAndValuesFromArguments``.

    Returns:
        Ordered ``(switch, values)`` pairs and whether the first argument was a switch.
    """
    first_is_switch = True
    pairs: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    requires_value = False
    for index, arg in enumerate(argv):
        if not requires_value and _is_switch_argument(arg):
            current = []
            pairs.append((arg, current))
            requires_value = _requires_value(arg, index)
        elif current is not None:
            current.append(arg)
            requires_value = False
        elif index == 0:
            first_is_switch = False
    return pairs, first_is_switch


def _single(values: list[str], switch: str) -> str | None:
    """Ports ``EnsureArgumentValueCount``."""
    if len(values) > 1:
        raise UsageError(f"Could not parse command line parameter '{values[1]}'.")
    if not values:
        raise UsageError(f"Switch '{switch}' requires a value.")
    return values[0]


def _parse_show_variable(value: str | None, switch: str) -> str:
    found = None
    if value and value.strip():
        wanted = value.replace("'", "").lower()
        found = next((v for v in AVAILABLE_VARIABLES if v.lower() == wanted), None)
    if found is None:
        listing = ", ".join(f"'{v}'" for v in AVAILABLE_VARIABLES)
        raise UsageError(
            f"{switch} requires a valid version variable. Available variables are:\n{listing}"
        )
    return found


def _parse_format(value: str | None) -> str:
    message = "Format requires a valid format string. Available variables are: " + ", ".join(
        AVAILABLE_VARIABLES
    )
    if value is None or not value.strip():
        raise UsageError(message)
    lowered = value.lower()
    if not any(v.lower() in lowered for v in AVAILABLE_VARIABLES):
        raise UsageError(message)
    return value


def _parse_output(values: list[str]) -> set[OutputType]:
    result: set[OutputType] = set()
    for value in values:
        try:
            result.add(OutputType(value.lower()))
        except ValueError:
            raise UsageError(
                f"Value '{value}' cannot be parsed as output type, please use 'json', 'file', "
                "'buildserver', 'dotenv' or 'env'"
            ) from None
    return result


def _parse_verbosity(value: str | None) -> Verbosity:
    try:
        return Verbosity.parse(value or "")
    except ValueError:
        raise UsageError(f"Could not parse Verbosity value '{value}'") from None


def _parse_override(values: list[str]) -> dict[str, Any]:
    if not values:
        return {}
    try:
        return parse_override_options(values)
    except ConfigurationError as exc:
        raise UsageError(str(exc)) from None


def _apply_switch(arguments: Arguments, name: str, switch: str, values: list[str]) -> bool:  # noqa: PLR0911, PLR0912
    """Ports ``ParseSwitches``: returns False when ``name`` is not a known switch."""
    first = values[0] if values else None
    if name in _UNSUPPORTED:
        raise UsageError(
            f"'{switch}' is not supported: {_UNSUPPORTED[name]} is out of scope "
            "for usg-pygitversion."
        )
    if name == "l":
        arguments.log_file_path = _single(values, switch)
        return True
    if name == "config":
        arguments.configuration_file = _single(values, switch)
        return True
    if name == "overrideconfig":
        arguments.override_configuration.update(_parse_override(values))
        return True
    if name == "showconfig":
        lowered = (first or "").lower()
        arguments.show_configuration = lowered in _TRUE_VALUES or lowered not in _FALSE_VALUES
        return True
    if name == "c":
        arguments.commit_id = _single(values, switch)
        return True
    if name == "b":
        arguments.target_branch = _single(values, switch)
        return True
    if name in ("diag", "nofetch", "nonormalize", "nocache", "allowshallow"):
        setattr(
            arguments,
            {"nofetch": "no_fetch", "nonormalize": "no_normalize", "nocache": "no_cache"}.get(
                name, {"allowshallow": "allow_shallow"}.get(name, name)
            ),
            True,
        )
        return True
    if name in ("v", "showvariable"):
        arguments.show_variable = _parse_show_variable(first, switch)
        return True
    if name == "format":
        arguments.format = _parse_format(first)
        return True
    if name == "output":
        arguments.output |= _parse_output(values)
        return True
    if name == "outputfile":
        arguments.output_file = _single(values, switch)
        return True
    if name == "verbosity":
        arguments.verbosity = _parse_verbosity(first)
        return True
    if name == "shell":
        try:
            arguments.shell = Shell.parse(_single(values, switch) or "")
        except ConfigurationError as exc:  # pragma: no cover -- Shell.parse raises GitVersionError
            raise UsageError(str(exc)) from None
        return True
    if name == "prefix":
        arguments.prefix = _single(values, switch) or ""
        return True
    if name == "envfile":
        arguments.env_file = _single(values, switch)
        return True
    return False


def _apply_target_path(
    arguments: Arguments, name: str, switch: str, values: list[str], parse_ended: bool
) -> None:
    """Ports ``ParseTargetPath``."""
    if name == "targetpath":
        value = _single(values, switch)
        arguments.target_path = value
        if not value or not Path(value).is_dir():
            raise UsageError(f"The working directory '{value}' does not exist.")
        return
    message = f"Could not parse command line parameter '{switch}'."
    if not parse_ended:
        raise UsageError(message)
    if switch.startswith("/"):
        if _is_valid_path(switch):
            arguments.target_path = switch
            return
    elif not _is_switch_argument(switch):
        arguments.target_path = switch
        return
    raise UsageError(message + " If it is the target path, make sure it exists.")


def parse_arguments(
    argv: Sequence[str],
    *,
    prevent_fetch: bool = True,
    current_directory: str | None = None,
) -> Arguments:
    """Ports ``ArgumentParser.ParseArguments``.

    Args:
        argv: Arguments without the program name.
        prevent_fetch: The resolved build agent's ``PreventFetch`` answer.
        current_directory: Used when no path is given (defaults to ``os.getcwd()``).

    Raises:
        UsageError: For anything the reference tool would reject.
    """
    cwd = current_directory or str(Path.cwd())
    if not argv:
        return Arguments(target_path=cwd, output={OutputType.JSON}, no_fetch=prevent_fetch)
    first = argv[0]
    if first == "?" or _switch_name(first) in ("h", "?"):
        return Arguments(is_help=True)
    if _switch_name(first) == "version":
        return Arguments(is_version=True)

    arguments = Arguments()
    pairs, first_is_switch = _collect(argv)
    for index, (switch, values) in enumerate(pairs):
        name = _switch_name(switch)
        if _apply_switch(arguments, name, switch, values):
            continue
        _apply_target_path(arguments, name, switch, values, parse_ended=index == 0)

    if not arguments.output:
        arguments.output.add(OutputType.JSON)
    if OutputType.FILE in arguments.output and arguments.output_file is None:
        arguments.output_file = DEFAULT_OUTPUT_FILE_NAME
    if arguments.target_path is None:
        arguments.target_path = cwd if first_is_switch else first
    arguments.target_path = arguments.target_path.rstrip("/\\") or "/"
    arguments.no_fetch = arguments.no_fetch or prevent_fetch
    _validate_configuration_file(arguments)
    return arguments


def _validate_configuration_file(arguments: Arguments) -> None:
    """Ports ``ValidateConfigurationFile``: resolve ``/config`` and require it to exist."""
    explicit = arguments.configuration_file
    if explicit is None or not explicit.strip():
        return
    candidate = Path(explicit)
    if not candidate.is_absolute():
        candidate = Path(arguments.target_path or ".") / candidate
    if not candidate.is_file():
        raise UsageError(f"Could not find config file at '{candidate}'")
    arguments.configuration_file = str(candidate.resolve())


def environment_overrides(arguments: Arguments, environment: Mapping[str, str]) -> Arguments:
    """Apply ``GITVERSION_BRANCH`` as a default for ``/b`` (PLAN.md 7.5)."""
    if arguments.target_branch is None and environment.get("GITVERSION_BRANCH"):
        arguments.target_branch = environment["GITVERSION_BRANCH"]
    return arguments
