# SPDX-License-Identifier: MIT
"""Module entry point so ``python -m pygitversion`` works inside any venv.

This is the supported invocation for environments where the ``gitversion``
console script is not on ``PATH`` (PLAN.md section 7.5).
"""

from __future__ import annotations

import sys

from pygitversion.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
