# SPDX-License-Identifier: MIT
"""Configuration enumerations.

Ports ``DeploymentMode``, ``IncrementStrategy``, ``CommitMessageIncrementMode``,
``AssemblyVersioningScheme``, ``AssemblyFileVersioningScheme`` and the
``VersionStrategies`` flags enum from GitVersion 6.8.2. Values are the exact
upstream spellings because they appear in ``/showconfig`` output. Parsing is
case-insensitive, matching the reference binary's behaviour (verified:
``mode: continuousdeployment`` is accepted).
"""

from __future__ import annotations

from enum import Flag, StrEnum
from typing import Self

from pygitversion.errors import ConfigurationError


class _CaseInsensitiveEnum(StrEnum):
    """StrEnum whose :meth:`parse` ignores case and reports a helpful error."""

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse an upstream enum name, ignoring case.

        Raises:
            ConfigurationError: If ``text`` is not a member name.
        """
        wanted = text.strip().lower()
        for member in cls:
            if member.value.lower() == wanted:
                return member
        names = ", ".join(m.value for m in cls)
        msg = f"invalid value {text!r} for {cls.__name__}; expected one of: {names}"
        raise ConfigurationError(msg)


class DeploymentMode(_CaseInsensitiveEnum):
    """How pre-release numbers advance. Ports ``DeploymentMode``."""

    MANUAL_DEPLOYMENT = "ManualDeployment"
    CONTINUOUS_DELIVERY = "ContinuousDelivery"
    CONTINUOUS_DEPLOYMENT = "ContinuousDeployment"


class IncrementStrategy(_CaseInsensitiveEnum):
    """Which version field a branch bumps. Ports ``IncrementStrategy``."""

    NONE = "None"
    MAJOR = "Major"
    MINOR = "Minor"
    PATCH = "Patch"
    INHERIT = "Inherit"


class CommitMessageIncrementMode(_CaseInsensitiveEnum):
    """Whether ``+semver:`` messages are honoured. Ports ``CommitMessageIncrementMode``."""

    ENABLED = "Enabled"
    DISABLED = "Disabled"
    MERGE_MESSAGE_ONLY = "MergeMessageOnly"


class AssemblyVersioningScheme(_CaseInsensitiveEnum):
    """Format of ``AssemblySemVer``. Ports ``AssemblyVersioningScheme``."""

    MAJOR_MINOR_PATCH_TAG = "MajorMinorPatchTag"
    MAJOR_MINOR_PATCH = "MajorMinorPatch"
    MAJOR_MINOR = "MajorMinor"
    MAJOR = "Major"
    NONE = "None"


class AssemblyFileVersioningScheme(_CaseInsensitiveEnum):
    """Format of ``AssemblySemFileVer``. Ports ``AssemblyFileVersioningScheme``."""

    MAJOR_MINOR_PATCH_TAG = "MajorMinorPatchTag"
    MAJOR_MINOR_PATCH = "MajorMinorPatch"
    MAJOR_MINOR = "MajorMinor"
    MAJOR = "Major"
    NONE = "None"


class VersionStrategy(Flag):
    """Version-source strategies, combinable. Ports the ``VersionStrategies`` flags enum."""

    NONE = 0
    FALLBACK = 1
    CONFIGURED_NEXT_VERSION = 2
    MERGE_MESSAGE = 4
    TAGGED_COMMIT = 8
    TRACK_RELEASE_BRANCHES = 16
    VERSION_IN_BRANCH_NAME = 32
    MAINLINE = 64

    @property
    def upstream_name(self) -> str:
        """The upstream spelling of a single flag (used in YAML output)."""
        return _STRATEGY_NAMES[self]

    @classmethod
    def parse(cls, text: str) -> VersionStrategy:
        """Parse one strategy name, ignoring case and non-alphanumerics.

        Raises:
            ConfigurationError: If ``text`` names no strategy.
        """
        wanted = "".join(ch for ch in text if ch.isalnum()).lower()
        for member, name in _STRATEGY_NAMES.items():
            if name.lower() == wanted:
                return member
        names = ", ".join(_STRATEGY_NAMES.values())
        msg = f"unknown version strategy {text!r}; expected one of: {names}"
        raise ConfigurationError(msg)


_STRATEGY_NAMES: dict[VersionStrategy, str] = {
    VersionStrategy.FALLBACK: "Fallback",
    VersionStrategy.CONFIGURED_NEXT_VERSION: "ConfiguredNextVersion",
    VersionStrategy.MERGE_MESSAGE: "MergeMessage",
    VersionStrategy.TAGGED_COMMIT: "TaggedCommit",
    VersionStrategy.TRACK_RELEASE_BRANCHES: "TrackReleaseBranches",
    VersionStrategy.VERSION_IN_BRANCH_NAME: "VersionInBranchName",
    VersionStrategy.MAINLINE: "Mainline",
}
