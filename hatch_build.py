# SPDX-License-Identifier: MIT
"""Hatch plugins that version the package with its own calculator (PLAN.md 8.3).

* ``resolve_version`` backs ``[tool.hatch.version] source = "code"``. It
  runs the in-tree ``usg_pygitversion`` on the repository and maps the
  ``SemVer`` variable to PEP 440. Outside a git checkout (an sdist) it
  reads the ``_version.py`` that the sdist build wrote.
* ``VersionFileHook`` writes ``usg_pygitversion/_version.py`` into every build
  so the installed package reports the same version.

Both run the calculator in a subprocess with an argument list, never a
shell, and only inside the project directory (SI-10).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import (  # type: ignore[import-not-found]
    BuildHookInterface,
)

VERSION_FILE = Path("usg_pygitversion") / "_version.py"


def _calculate(root: Path) -> tuple[str, str]:
    """Return ``(pep440, semver)`` for the checkout at ``root``."""
    sys.path.insert(0, str(root))
    from usg_pygitversion._pep440 import to_pep440  # noqa: PLC0415 -- in-tree import

    completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [sys.executable, "-m", "usg_pygitversion", str(root), "/nocache", "/output", "json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    semver = json.loads(completed.stdout)["SemVer"]
    return to_pep440(semver), semver


def _read_version_file(root: Path) -> tuple[str, str] | None:
    path = root / VERSION_FILE
    if not path.is_file():
        return None
    namespace: dict[str, Any] = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)  # noqa: S102 -- our own generated file
    return namespace["__version__"], namespace["__gitversion__"]


def _resolve(root: Path) -> tuple[str, str]:
    if (root / ".git").exists():
        return _calculate(root)
    cached = _read_version_file(root)
    if cached is None:
        raise RuntimeError("not a git checkout and usg_pygitversion/_version.py is missing")
    return cached


def resolve_version() -> str:
    """Entry point for ``[tool.hatch.version] source = "code"``."""
    return _resolve(Path(__file__).resolve().parent)[0]


class VersionFileHook(BuildHookInterface):  # type: ignore[misc,no-any-unimported]
    """Build hook: materialise ``usg_pygitversion/_version.py``."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:  # noqa: ARG002
        """Write the version file before the artifact is assembled."""
        pep440, semver = _resolve(Path(self.root))
        target = Path(self.root) / VERSION_FILE
        target.write_text(
            "# SPDX-License-Identifier: MIT\n"
            '"""Generated at build time by hatch_build.py; do not edit."""\n\n'
            f"__version__ = {pep440!r}\n"
            f"__gitversion__ = {semver!r}\n",
            encoding="utf-8",
        )
        build_data.setdefault("artifacts", []).append(str(VERSION_FILE))
