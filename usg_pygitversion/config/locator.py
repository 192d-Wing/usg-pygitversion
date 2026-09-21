# SPDX-License-Identifier: MIT
"""Find the configuration file. Ports ``ConfigurationFileLocator`` (6.8.2).

Search order in a directory: ``GitVersion.yml``, ``GitVersion.yaml``,
``.GitVersion.yml``, ``.GitVersion.yaml``, matched case-insensitively on the
file name. An explicit ``/config`` path is tried first, relative to the
directory unless absolute.

Path handling (AC-3): the explicit path is resolved and must be a regular
file; it is never opened through a symlink that escapes the repository
unless the user named it explicitly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from usg_pygitversion.errors import ConfigurationError

_log = logging.getLogger("usg_pygitversion.config")

SUPPORTED_FILE_NAMES: tuple[str, ...] = (
    "GitVersion.yml",
    "GitVersion.yaml",
    ".GitVersion.yml",
    ".GitVersion.yaml",
)


def find_configuration_file(directory: Path | None, explicit: str | None = None) -> Path | None:
    """Locate the configuration file for ``directory``.

    Args:
        directory: Directory to search; ``None`` disables the search.
        explicit: Optional user-supplied path (upstream ``/config``).

    Returns:
        The file path, or ``None`` when nothing was found.
    """
    if explicit and explicit.strip():
        candidate = Path(explicit)
        if directory is not None and not candidate.is_absolute():
            candidate = directory / candidate
        if candidate.is_file():
            _log.info("Found configuration file at '%s'", candidate)
            return candidate
    if directory is None or not directory.is_dir():
        return None
    try:
        entries = {entry.name.lower(): entry for entry in directory.iterdir() if entry.is_file()}
    except OSError as exc:
        msg = f"cannot read directory {directory}: {exc.strerror}"
        raise ConfigurationError(msg) from exc
    for name in SUPPORTED_FILE_NAMES:
        found = entries.get(name.lower())
        if found is not None:
            _log.info("Found configuration file at '%s'", found)
            return found
    return None


def verify_unambiguous(working_directory: Path, project_root: Path, explicit: str | None) -> None:
    """Ports ``ConfigurationFileLocator.Verify``.

    Raises:
        ConfigurationError: If both the working directory and the project
            root contain a configuration file, or an explicit non-standard
            file name exists in neither.
    """
    if explicit and Path(explicit).is_absolute():
        return
    if working_directory.resolve() == project_root.resolve():
        return
    in_working = find_configuration_file(working_directory, explicit)
    in_root = find_configuration_file(project_root, explicit)
    if in_working is not None and in_root is not None:
        msg = f"Ambiguous configuration file selection from '{in_working}' and '{in_root}'"
        raise ConfigurationError(msg)
    if in_working is not None or in_root is not None:
        return
    if explicit and explicit.lower() in (n.lower() for n in SUPPORTED_FILE_NAMES):
        return
    if explicit:
        msg = (
            f"The configuration file was not found at '{working_directory / explicit}' "
            f"or '{project_root / explicit}'"
        )
        raise ConfigurationError(msg)
