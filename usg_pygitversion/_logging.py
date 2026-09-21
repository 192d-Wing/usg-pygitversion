# SPDX-License-Identifier: MIT
"""Logging setup mapped to GitVersion's ``/verbosity`` levels.

Audit-relevant behaviour (NIST SP 800-53 AU-2, AU-3, AU-9):

* Every record carries a timestamp, level and component name.
* Log files requested with ``/l`` are created with mode ``0o600``.
* Nothing in this module, and nothing that calls it, logs the process
  environment or file contents at any level. Diagnostic verbosity adds
  tracebacks and git command lines, never data.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

LOGGER_NAME = "usg_pygitversion"


class Verbosity(StrEnum):
    """Upstream verbosity names, case-insensitive on the CLI."""

    QUIET = "Quiet"
    MINIMAL = "Minimal"
    NORMAL = "Normal"
    VERBOSE = "Verbose"
    DIAGNOSTIC = "Diagnostic"

    @property
    def level(self) -> int:
        """Translate to a :mod:`logging` level."""
        return {
            Verbosity.QUIET: logging.CRITICAL + 10,  # effectively off
            Verbosity.MINIMAL: logging.WARNING,
            Verbosity.NORMAL: logging.INFO,
            Verbosity.VERBOSE: logging.INFO,
            Verbosity.DIAGNOSTIC: logging.DEBUG,
        }[self]

    @classmethod
    def parse(cls, text: str) -> Verbosity:
        """Parse a user-supplied verbosity name, ignoring case.

        Raises:
            ValueError: If ``text`` is not a known verbosity.
        """
        lookup = {member.value.lower(): member for member in cls}
        try:
            return lookup[text.strip().lower()]
        except KeyError:
            names = ", ".join(m.value for m in cls)
            msg = f"unknown verbosity {text!r}; expected one of {names}"
            raise ValueError(msg) from None


class _UpstreamFormatter(logging.Formatter):
    """``LEVEL [yy-MM-dd HH:mm:ss:ff] message``, the reference tool's line format."""

    _LEVELS: ClassVar[dict[str, str]] = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARN",
        "ERROR": "ERROR",
        "CRITICAL": "ERROR",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Render one record."""
        stamp = time.strftime("%y-%m-%d %H:%M:%S", time.localtime(record.created))
        hundredths = int(record.msecs / 10)
        level = self._LEVELS.get(record.levelname, record.levelname)
        return f"{level} [{stamp}:{hundredths:02d}] {record.getMessage()}"


def configure(
    verbosity: Verbosity, log_file: Path | None = None, *, console: bool = False
) -> logging.Logger:
    """Configure the package logger and return it.

    Warnings and errors always go to stderr so stdout stays clean for
    machine-readable output. ``console=True`` (``/output buildserver`` or
    ``/l console``) additionally mirrors the log to stdout in the reference
    tool's format, as upstream does.

    Args:
        verbosity: Desired level for the console and file appenders.
        log_file: Optional file to append to. Created ``0o600`` (SC-28,
            AU-9) so other local users cannot read the build log.
        console: Mirror the log to stdout.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(min(verbosity.level, logging.WARNING))
    logger.handlers.clear()  # idempotent: safe to call more than once
    logger.propagate = False

    if console:
        stdout = logging.StreamHandler(sys.stdout)
        stdout.setLevel(verbosity.level)
        stdout.setFormatter(_UpstreamFormatter())
        logger.addHandler(stdout)
    else:
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(logging.WARNING)
        stderr.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(stderr)

    if log_file is not None:
        # Open with an explicit restrictive mode rather than relying on umask.
        fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        os.close(fd)  # FileHandler opened its own descriptor; ours only set the mode
        file_handler.setLevel(verbosity.level)
        file_handler.setFormatter(_UpstreamFormatter())
        logger.addHandler(file_handler)

    return logger


def shutdown() -> None:
    """Flush, close and detach every handler :func:`configure` installed.

    Called when an invocation ends so that a log file descriptor is not
    left open and a handler bound to the stdout of one invocation is not
    reused by the next (in-process callers such as the tests would
    otherwise write to a closed stream).
    """
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.flush()
        handler.close()
