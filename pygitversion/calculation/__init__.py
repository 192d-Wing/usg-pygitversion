# SPDX-License-Identifier: MIT
"""Version calculation engine. Ports ``GitVersion.Core`` version calculation at 6.8.2.

Entry point: :func:`calculate_variables`. The pipeline is

1. :mod:`context` builds a :class:`GitVersionContext` (branch, commit,
   configuration, tagged state, dirty count).
2. :mod:`calculator` runs the version strategies through the effective
   branch configurations, picks the winning base version, applies the
   deployment mode and returns a :class:`~pygitversion.semver.SemanticVersion`.
3. :mod:`variables` turns that into the 28 output variables.
"""

from pygitversion.calculation.api import calculate_variables
from pygitversion.calculation.context import GitVersionContext
from pygitversion.calculation.variables import GitVersionVariables

__all__ = ["GitVersionContext", "GitVersionVariables", "calculate_variables"]
