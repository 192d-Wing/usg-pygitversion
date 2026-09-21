"""pygitversion: semantic versioning from git history, without .NET.

A pure-Python port of GitVersion 6.8.2 (https://gitversion.net). The public,
supported API is intentionally tiny (PLAN.md section 7.5):

* :func:`calculate` -- run the version calculation for a repository.
* :func:`export_env` -- write the resulting variables into an environment
  mapping, for build scripts that want ``GitVersion_*`` variables in-process.
* :class:`GitVersionVariables` -- the typed result.

Everything else in the package is private and may change between minor
versions.

Phase 0 ships only the package skeleton; :func:`calculate` raises
:class:`~pygitversion.errors.NotImplementedYetError` until the calculation
engine lands in Phase 3.
"""

from __future__ import annotations

from pygitversion.__about__ import __version__
from pygitversion.errors import NotImplementedYetError

__all__ = ["__version__", "calculate"]


def calculate(path: str = ".") -> None:  # noqa: ARG001 -- placeholder signature
    """Calculate GitVersion variables for the repository at ``path``.

    Args:
        path: Directory inside a git working tree. Defaults to the current
            directory, matching the upstream CLI.

    Raises:
        NotImplementedYetError: Always, until Phase 3 delivers the engine.
    """
    raise NotImplementedYetError("version calculation lands in Phase 3")
