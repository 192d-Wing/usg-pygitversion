# SPDX-License-Identifier: MIT
"""Configuration: ``GitVersion.yml`` loading, presets, overrides and effective values.

Ports ``GitVersion.Configuration`` and ``GitVersion.Core/Configuration`` at
tag 6.8.2. The public entry points are :func:`provide` (build the effective
:class:`GitVersionConfiguration` for a directory) and
:func:`get_effective_configuration` (resolve a branch's settings).
"""

from pygitversion.config.effective import (
    EffectiveConfiguration,
    get_branch_configuration,
    get_effective_configuration,
)
from pygitversion.config.enums import (
    AssemblyFileVersioningScheme,
    AssemblyVersioningScheme,
    CommitMessageIncrementMode,
    DeploymentMode,
    IncrementStrategy,
    VersionStrategy,
)
from pygitversion.config.provider import provide
from pygitversion.config.schema import (
    BranchConfiguration,
    GitVersionConfiguration,
    IgnoreConfiguration,
    PreventIncrementConfiguration,
)

__all__ = [
    "AssemblyFileVersioningScheme",
    "AssemblyVersioningScheme",
    "BranchConfiguration",
    "CommitMessageIncrementMode",
    "DeploymentMode",
    "EffectiveConfiguration",
    "GitVersionConfiguration",
    "IgnoreConfiguration",
    "IncrementStrategy",
    "PreventIncrementConfiguration",
    "VersionStrategy",
    "get_branch_configuration",
    "get_effective_configuration",
    "provide",
]
