# SPDX-License-Identifier: MIT
"""Command-line entry point.

Accepts GitVersion's ``/flag`` and ``-flag`` syntax plus POSIX ``--flag``
(see :mod:`usg_pygitversion.cli.arguments`). Exit codes follow upstream: 0 on
success, 1 for every handled error. Usage errors also exit 1 (the .NET tool
crashes with an unhandled exception there; see ``docs/deviations.md``).

Security notes (NIST SP 800-53 SI-10, SI-11): nothing is interpreted as a
shell string; handled errors print a one-line message; tracebacks appear
only at ``Diagnostic`` verbosity.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from usg_pygitversion import __version__, app
from usg_pygitversion.cli.arguments import parse_arguments
from usg_pygitversion.cli.help import help_text
from usg_pygitversion.errors import GitVersionError, UsageError


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code.

    Args:
        argv: Arguments without the program name. ``None`` reads :data:`sys.argv`.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        arguments = parse_arguments(raw)
    except UsageError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if arguments.is_help:
        sys.stdout.write(help_text(__version__) + "\n")
        return 0
    if arguments.is_version:
        sys.stdout.write(f"{__version__}\n")
        return 0
    try:
        return app.run(arguments)
    except GitVersionError as exc:  # pragma: no cover -- app.run handles these
        sys.stderr.write(f"An error occurred:\n{exc}\n")
        return 1
    except Exception:
        # SI-11: fail closed with a message; the traceback is opt-in.
        logging.getLogger("usg_pygitversion").error("An unexpected error occurred", exc_info=True)
        sys.stderr.write(
            "An unexpected error occurred; rerun with /verbosity Diagnostic for details.\n"
        )
        return 1
