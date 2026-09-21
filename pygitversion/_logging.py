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
from enum import StrEnum
from pathlib import Path

LOGGER_NAME = "pygitversion"


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
            Verbosity.MINIMAL: logging.ERROR,
            Verbosity.NORMAL: logging.WARNING,
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


def configure(verbosity: Verbosity, log_file: Path | None = None) -> logging.Logger:
    """Configure the package logger and return it.

    Handlers write to stderr so stdout stays clean for machine-readable
    output (JSON, dotenv, shell exports).

    Args:
        verbosity: Desired level.
        log_file: Optional file to append to. Created ``0o600`` (SC-28,
            AU-9) so other local users cannot read the build log.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(verbosity.level)
    logger.handlers.clear()  # idempotent: safe to call more than once
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    stream = logging.StreamHandler()  # defaults to sys.stderr
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if log_file is not None:
        # Open with an explicit restrictive mode rather than relying on umask.
        fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        os.close(fd)  # FileHandler opened its own descriptor; ours only set the mode
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
