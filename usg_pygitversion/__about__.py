# SPDX-License-Identifier: MIT
"""Package version.

At build time ``hatch_build.py`` writes ``_version.py`` from the tool's own
calculation (PLAN.md 8.3). In a plain source checkout that file does not
exist, so a development placeholder is used instead.
"""

from __future__ import annotations

__version__: str
__gitversion__: str | None

try:
    from usg_pygitversion._version import __gitversion__, __version__
except ImportError:  # pragma: no cover -- source checkout without a build
    __version__ = "0.0.0.dev0"
    __gitversion__ = None

__all__ = ["__gitversion__", "__version__"]
