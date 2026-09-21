# SPDX-License-Identifier: MIT
"""Dispatches the calculated variables to the requested outputs. Ports ``OutputGenerator``.

Order matches upstream: build-server integration first, then ``dotenv``
(which suppresses JSON), then the JSON document to a file and/or the
console. The ``env`` output is additive like ``buildserver``; when it is the
only output the JSON is not printed so the result is safe to ``eval``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from pygitversion.buildagents.base import BuildAgent, Writer
from pygitversion.buildagents.envexport import EnvExporter, write_lines
from pygitversion.calculation.variables import GitVersionVariables
from pygitversion.cli.arguments import Arguments, OutputType
from pygitversion.errors import GitVersionError
from pygitversion.formatting import TemplateError, format_with
from pygitversion.output.serializer import to_json

_log = logging.getLogger("pygitversion.output")


def dotenv_lines(variables: GitVersionVariables) -> list[str]:
    """Ports ``WriteDotEnv``: ``GitVersion_<Name>='<value>'`` sorted by name.

    Upstream does not escape quotes in values; the format is reproduced
    byte for byte so existing consumers keep working.
    """
    return [f"GitVersion_{name}='{value or ''}'" for name, value in sorted(variables)]


def write_outputs(
    variables: GitVersionVariables,
    arguments: Arguments,
    agent: BuildAgent,
    writer: Writer,
    *,
    update_build_number: bool,
    environment: Mapping[str, str],
) -> None:
    """Emit every requested output."""
    outputs = arguments.output
    if OutputType.BUILDSERVER in outputs:
        agent.write_integration(writer, variables, update_build_number)

    exporter = EnvExporter(arguments.prefix)
    if arguments.env_file is not None:
        exporter.append_env_file(arguments.env_file, variables)
    if OutputType.ENV in outputs:
        for line in exporter.shell_lines(variables, arguments.shell):
            writer(line)

    if OutputType.DOTENV in outputs:
        for line in dotenv_lines(variables):
            writer(line)
        return

    json = to_json(variables)
    if OutputType.FILE in outputs and arguments.output_file is not None:
        output_path = Path(arguments.output_file)
        if not output_path.is_absolute():
            output_path = arguments.working_directory / output_path
        write_lines(output_path, [json])
    if OutputType.JSON in outputs:
        _write_json_to_console(json, variables, arguments, writer, environment)


def _write_json_to_console(
    json: str,
    variables: GitVersionVariables,
    arguments: Arguments,
    writer: Writer,
    environment: Mapping[str, str],
) -> None:
    """Ports ``WriteJsonToConsole`` including ``/showvariable`` and ``/format``."""
    if arguments.show_variable is None and arguments.format is None:
        writer(json)
        return
    if arguments.show_variable is not None and arguments.format is not None:
        raise GitVersionError("Cannot specify both /showvariable and /format")
    if arguments.show_variable is not None:
        if arguments.show_variable not in variables:
            raise GitVersionError(f"'{arguments.show_variable}' variable does not exist")
        writer(variables[arguments.show_variable] or "")
        return
    assert arguments.format is not None  # noqa: S101 -- narrowed above

    def resolve(member: str) -> str | None:
        if member not in variables:
            raise TemplateError(
                f"'{member}' is not a property or field on type 'GitVersionVariables'"
            )
        return variables[member]

    try:
        writer(format_with(arguments.format, resolve, environment))
    except TemplateError as exc:
        raise GitVersionError(str(exc)) from exc
