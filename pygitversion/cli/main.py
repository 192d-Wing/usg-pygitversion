# SPDX-License-Identifier: MIT
"""Command-line entry point.

Accepts GitVersion's ``/flag`` syntax and POSIX ``--flag`` syntax. The
upstream surface is documented at
https://gitversion.net/docs/usage/cli/arguments and is filled in phase by
phase; Phase 0 implements only ``/version``, ``/help`` and ``/verbosity`` so
that packaging, CI and the smoke test exercise a real code path.

Security notes (NIST SP 800-53 SI-10, SI-11):

* All arguments go through :mod:`argparse` with typed choices; nothing is
  interpreted as a shell string.
* Handled errors print a one-line message and exit 1. Tracebacks appear only
  at ``Diagnostic`` verbosity.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pygitversion import __version__, _logging
from pygitversion.errors import GitVersionError, NotImplementedYetError, UsageError

# Upstream flags that take no value. Needed by the ``/flag`` translator so it
# can tell ``/nofetch`` (boolean) from ``/c <sha>`` (valued). Extended as
# later phases add options.
_BOOLEAN_FLAGS: frozenset[str] = frozenset(
    {
        "version",
        "help",
        "?",
        "diag",
        "nofetch",
        "nocache",
        "nonormalize",
        "allowshallow",
        "showconfig",
        "updateassemblyinfo",
        "ensureassemblyinfo",
        "updateprojectfiles",
        "updatewixversionfile",
    }
)

# Short upstream names that map to long POSIX names.
_SHORT_TO_LONG: dict[str, str] = {
    "?": "help",
    "b": "branch",
    "c": "commit",
    "l": "log-file",
    "u": "username",
    "p": "password",
}


def translate_dotnet_style(argv: Sequence[str]) -> list[str]:
    """Rewrite ``/flag value`` and ``/flag`` into ``--flag value`` / ``--flag``.

    A leading ``/`` is only treated as a flag prefix when what follows looks
    like an option name, so absolute POSIX paths such as ``/home/me/repo``
    pass through untouched. Both forms may be mixed on one command line.

    Args:
        argv: Raw arguments, without the program name.

    Returns:
        Arguments suitable for :mod:`argparse` with ``--`` style options.
    """
    out: list[str] = []
    for arg in argv:
        if arg.startswith("/") and len(arg) > 1 and "/" not in arg[1:] and " " not in arg:
            name = arg[1:]
            long = _SHORT_TO_LONG.get(name.lower(), name.lower())
            out.append(f"--{long}")
        else:
            out.append(arg)
    return out


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the currently ported option surface."""
    parser = argparse.ArgumentParser(
        prog="gitversion",
        description="Semantic versioning from git history (Python port of GitVersion).",
        add_help=False,  # we register --help ourselves to keep /? working
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="directory containing the .git folder (default: current directory)",
    )
    parser.add_argument("--help", "-h", action="help", help="show this help and exit")
    parser.add_argument("--version", action="store_true", help="print the tool version and exit")
    parser.add_argument(
        "--verbosity",
        default=_logging.Verbosity.NORMAL.value,
        help="Quiet, Minimal, Normal, Verbose or Diagnostic (default: Normal)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="append diagnostics to this file (upstream /l)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code.

    Args:
        argv: Arguments without the program name. ``None`` reads
            :data:`sys.argv`.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    try:
        ns = parser.parse_args(translate_dotnet_style(raw))
        verbosity = _logging.Verbosity.parse(ns.verbosity)
    except ValueError as exc:
        # Verbosity parse failure: report like argparse would, exit 2.
        parser.error(str(exc))
    except SystemExit as exc:
        # argparse exits 0 for --help, 2 for usage errors. Propagate its code.
        return int(exc.code or 0)

    log = _logging.configure(verbosity, ns.log_file)

    try:
        if ns.version:
            sys.stdout.write(f"{__version__}\n")
            return 0
        # Phase 0: nothing else is wired. Later phases dispatch here.
        raise NotImplementedYetError("version calculation lands in Phase 3")
    except UsageError as exc:
        log.error("%s", exc)
        return 2
    except GitVersionError as exc:
        # SI-11: message only. The traceback is opt-in via Diagnostic.
        log.error("%s", exc, exc_info=verbosity is _logging.Verbosity.DIAGNOSTIC)
        return exc.exit_code
