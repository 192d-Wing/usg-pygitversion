# SPDX-License-Identifier: MIT
"""Typed exception hierarchy for pygitversion.

Every error the tool raises on purpose derives from :class:`GitVersionError`
so the CLI can map it to a clean message and a deterministic exit code
(NIST SP 800-53 SI-11: fail securely, no stack traces or environment
contents in user-facing errors unless diagnostic verbosity is requested).

Messages must never embed file contents, environment variables or
credentials. Include *what* failed and *where* (a path or ref name), not the
data that was being processed.
"""

from __future__ import annotations


class GitVersionError(Exception):
    """Base class for all expected pygitversion failures.

    Attributes:
        exit_code: Process exit status the CLI should use. Upstream uses 1
            for every handled error, so that is the default.
    """

    exit_code: int = 1


class NotImplementedYetError(GitVersionError):
    """A feature that is planned but not yet ported.

    Distinct from :class:`NotImplementedError` so that callers can tell the
    difference between "wrong usage of an abstract class" and "this phase of
    the port has not landed".
    """


class ConfigurationError(GitVersionError):
    """``GitVersion.yml`` or an override could not be parsed or validated (SI-10)."""


class RepositoryError(GitVersionError):
    """The path is not a git repository, or git could not be executed."""


class GitCommandError(RepositoryError):
    """A git subprocess exited non-zero or timed out.

    Attributes:
        args_: The git argument list that was run (never includes secrets;
            pygitversion does not pass credentials to git).
        returncode: Exit status of the child, or ``None`` on timeout.
        stderr: Captured standard error, truncated by the caller.
    """

    def __init__(self, args_: list[str], returncode: int | None, stderr: str) -> None:
        """Build the error with the failing command context."""
        self.args_ = args_
        self.returncode = returncode
        self.stderr = stderr
        status = "timed out" if returncode is None else f"exited {returncode}"
        super().__init__(f"git {' '.join(args_)} {status}: {stderr.strip()}")


class UsageError(GitVersionError):
    """Invalid command-line arguments."""
