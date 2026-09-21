# SPDX-License-Identifier: MIT
"""usg-pygitversion: semantic versioning from git history, without .NET.

A pure-Python port of GitVersion 6.8.2 (https://gitversion.net). The public,
supported API is intentionally tiny (PLAN.md section 7.5):

* :func:`calculate` -- run the version calculation for a repository.
* :func:`export_env` -- write the resulting variables into an environment
  mapping, for build scripts that want ``GitVersion_*`` variables in-process.
* :class:`GitVersionVariables` -- the typed result.

Everything else in the package is private and may change between minor
versions.

Example::

    import os, usg_pygitversion

    version = usg_pygitversion.calculate(".")
    usg_pygitversion.export_env(version, os.environ)
    print(version.full_sem_ver, version.as_dict()["SemVer"])
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from usg_pygitversion.__about__ import __version__
from usg_pygitversion.calculation.variables import GitVersionVariables

__all__ = ["GitVersionVariables", "__version__", "calculate", "export_env"]


def calculate(
    path: str | Path = ".",
    *,
    config_file: str | None = None,
    overrides: Mapping[str, Any] | None = None,
    branch: str | None = None,
    commit: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> GitVersionVariables:
    """Calculate GitVersion variables for the repository at ``path``.

    The disk cache is not consulted: the API always computes a fresh result.

    Args:
        path: Directory inside a git working tree (default: current directory).
        config_file: Explicit configuration file (upstream ``/config``).
        overrides: ``/overrideconfig`` values as a YAML-shaped mapping.
        branch: Branch to calculate for instead of ``HEAD`` (``/b``).
        commit: Commit to calculate for (``/c``).
        environment: Environment for ``{env:...}`` placeholders; defaults to
            the process environment.

    Raises:
        GitVersionError: For any handled failure (not a repository, bad
            configuration, no commits).
    """
    import os  # noqa: PLC0415 -- keep the import surface of the package tiny

    from usg_pygitversion.calculation.api import calculate_variables  # noqa: PLC0415

    return calculate_variables(
        path,
        override_document=dict(overrides) if overrides else None,
        explicit_config_file=config_file,
        target_branch=branch,
        commit_id=commit,
        environment=dict(os.environ) if environment is None else environment,
    )


def export_env(
    variables: GitVersionVariables,
    target: MutableMapping[str, str],
    *,
    prefix: str = "GitVersion_",
) -> None:
    """Populate ``target`` with ``<prefix><Name>`` entries for every variable.

    Empty variables are exported as ``""`` so that consumers can rely on
    every name being present.
    """
    from usg_pygitversion.buildagents.envexport import EnvExporter  # noqa: PLC0415

    EnvExporter(prefix).export(variables, target)
