# SPDX-License-Identifier: MIT
"""Package version metadata.

Phase 0 uses a static placeholder. From Phase 5 onward a hatch build hook
computes this value by running pygitversion on its own repository and
normalising the result to PEP 440 (PLAN.md section 8.3).
"""

__version__ = "0.0.1"
