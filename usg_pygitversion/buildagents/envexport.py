# SPDX-License-Identifier: MIT
"""Generic environment export for build servers without a dedicated agent.

One :class:`EnvExporter` owns variable naming, prefix handling, empty-value
skipping and per-shell quoting, so the built-in agents, ``--output env``,
``--env-file`` and the Python API cannot drift apart (PLAN.md section 7.5).

Security (SI-10, SI-11): variable names are validated against a strict
identifier pattern before they reach a shell, values are quoted so that
``eval`` cannot execute anything embedded in a branch name, and values that
cannot be represented safely in the target shell are rejected instead of
being emitted mangled.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, MutableMapping
from enum import StrEnum
from pathlib import Path

from usg_pygitversion.calculation.variables import GitVersionVariables
from usg_pygitversion.errors import GitVersionError

DEFAULT_PREFIX = "GitVersion_"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Shell(StrEnum):
    """Shells ``--output env`` can target."""

    SH = "sh"
    BASH = "bash"
    POWERSHELL = "powershell"
    CMD = "cmd"

    @classmethod
    def parse(cls, text: str) -> Shell:
        """Case-insensitive lookup.

        Raises:
            GitVersionError: For an unknown shell name.
        """
        for member in cls:
            if member.value == text.strip().lower():
                return member
        names = ", ".join(m.value for m in cls)
        raise GitVersionError(f"Unknown shell {text!r}; expected one of {names}")


def _quote_sh(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _quote_powershell(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_cmd(value: str) -> str:
    # cmd.exe has no reliable escaping for these inside ``set "K=V"``.
    if any(ch in value for ch in '"\r\n'):
        raise GitVersionError("value cannot be represented safely for cmd.exe")
    return value.replace("%", "%%")


def write_lines(path: Path, lines: Iterable[str], *, append: bool = False) -> None:
    """Write ``lines`` (newline-terminated) to ``path`` with owner-only permissions.

    A fresh file is created ``0o600`` (SC-28); an existing file keeps its mode.
    """
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")


class EnvExporter:
    """Turns variables into ``<prefix><Name>`` environment entries."""

    def __init__(self, prefix: str = DEFAULT_PREFIX) -> None:
        """Validate the prefix once; it is user-controlled via ``--prefix``."""
        if not _IDENTIFIER.match(prefix + "X"):
            raise GitVersionError(f"invalid environment variable prefix {prefix!r}")
        self.prefix = prefix

    def entries(
        self, variables: GitVersionVariables, *, skip_empty: bool = True
    ) -> list[tuple[str, str]]:
        """``(name, value)`` pairs in variable order.

        Empty values are skipped by default, matching the GitHub Actions
        agent; pass ``skip_empty=False`` to export them as ``""``.
        """
        result: list[tuple[str, str]] = []
        for name, value in variables:
            if not value and skip_empty:
                continue
            key = self.prefix + name
            if not _IDENTIFIER.match(key):  # pragma: no cover -- names are fixed upstream
                raise GitVersionError(f"invalid environment variable name {key!r}")
            result.append((key, value or ""))
        return result

    def export(self, variables: GitVersionVariables, target: MutableMapping[str, str]) -> None:
        """Populate ``target`` (for example ``os.environ``) in place."""
        for key, value in self.entries(variables, skip_empty=False):
            target[key] = value

    def shell_lines(self, variables: GitVersionVariables, shell: Shell) -> list[str]:
        """Assignments that are safe to ``eval`` in ``shell``."""
        lines: list[str] = []
        for key, value in self.entries(variables, skip_empty=False):
            if shell in (Shell.SH, Shell.BASH):
                lines.append(f"export {key}={_quote_sh(value)}")
            elif shell is Shell.POWERSHELL:
                lines.append(f"$env:{key} = {_quote_powershell(value)}")
            else:
                lines.append(f'set "{key}={_quote_cmd(value)}"')
        return lines

    def env_file_lines(self, variables: GitVersionVariables) -> list[str]:
        """``KEY=value`` lines in the ``$GITHUB_ENV`` contract (empty values skipped)."""
        lines: list[str] = []
        for key, value in self.entries(variables):
            if "\n" in value or "\r" in value:
                raise GitVersionError(f"value of {key} contains a newline")
            lines.append(f"{key}={value}")
        return lines

    def append_env_file(self, path: str | Path, variables: GitVersionVariables) -> None:
        """Append to an environment file such as ``$GITHUB_ENV``."""
        write_lines(Path(path), self.env_file_lines(variables), append=True)
