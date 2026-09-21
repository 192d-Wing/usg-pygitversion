# SPDX-License-Identifier: MIT
"""Base versions produced by strategies and the ``NextVersion`` candidates.

Ports ``BaseVersionOperand``, ``BaseVersionOperator``, ``BaseVersion`` and
``NextVersion`` from 6.8.2.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

from usg_pygitversion.config.effective import EffectiveConfiguration
from usg_pygitversion.git.models import Branch, Commit
from usg_pygitversion.semver import IncrementMode, SemanticVersion, VersionField


@dataclass(frozen=True, slots=True)
class BaseVersionOperand:
    """The version a strategy found and where. Ports ``BaseVersionOperand``."""

    source: str = ""
    semantic_version: SemanticVersion = field(default_factory=SemanticVersion)
    base_version_source: Commit | None = None


@dataclass(frozen=True, slots=True)
class BaseVersionOperator:
    """How the operand is to be incremented. Ports ``BaseVersionOperator``."""

    source: str = ""
    base_version_source: Commit | None = None
    increment: VersionField = VersionField.NONE
    force_increment: bool = False
    label: str | None = None
    alternative_semantic_version: SemanticVersion | None = None


@dataclass(frozen=True, slots=True)
class BaseVersion:
    """Operand plus optional operator. Ports ``BaseVersion``."""

    operand: BaseVersionOperand = field(default_factory=BaseVersionOperand)
    operator: BaseVersionOperator | None = None

    @classmethod
    def of(
        cls,
        source: str,
        semantic_version: SemanticVersion,
        base_version_source: Commit | None = None,
        operator: BaseVersionOperator | None = None,
    ) -> BaseVersion:
        """Constructor mirroring ``new BaseVersion(source, version, commit) { Operator = .. }``."""
        return cls(BaseVersionOperand(source, semantic_version, base_version_source), operator)

    @property
    def source(self) -> str:
        """Operator source when set, else the operand's."""
        if self.operator is not None and self.operator.source:
            return self.operator.source
        return self.operand.source

    @property
    def semantic_version(self) -> SemanticVersion:
        """The found version."""
        return self.operand.semantic_version

    @property
    def increment(self) -> VersionField:
        """The operator's increment, ``NONE`` without an operator."""
        return self.operator.increment if self.operator is not None else VersionField.NONE

    @property
    def base_version_source(self) -> Commit | None:
        """Operator source commit when set, else the operand's."""
        if self.operator is not None and self.operator.base_version_source is not None:
            return self.operator.base_version_source
        return self.operand.base_version_source

    @property
    def should_increment(self) -> bool:
        """True when an operator is attached."""
        return self.operator is not None

    def get_incremented_version(self) -> SemanticVersion:
        """Apply the operator. Ports ``GetIncrementedVersion``."""
        result = self.semantic_version
        if self.operator is not None:
            result = result.increment(
                self.operator.increment,
                self.operator.label,
                self.operator.alternative_semantic_version,
                mode=IncrementMode.FORCE
                if self.operator.force_increment
                else IncrementMode.STANDARD,
            )
        return result

    def apply(self, operator: BaseVersionOperator) -> BaseVersion:
        """Ports ``Apply``: the incremented version becomes the operand of a new operator."""
        return BaseVersion.of(
            self.source, self.get_incremented_version(), self.base_version_source, operator
        )

    def __str__(self) -> str:
        """Log line matching upstream ``ToString``."""
        commit_source = (
            self.base_version_source.short_sha if self.base_version_source else "External"
        )
        if self.operator is not None:
            kind = (
                "Force version increment "
                if self.operator.force_increment
                else "Version increment "
            )
            label = (
                " with no label"
                if self.operator.label is None
                else f" with label '{self.operator.label}'"
            )
            text = (
                f"{self.source}: {kind}'{self.semantic_version.to_string('f')}' "
                f"+semver '{self.operator.increment.upstream_name}'{label}"
            )
        else:
            text = f"{self.source}: Take '{self.semantic_version.to_string('f')}'"
        if self.base_version_source is not None:
            text += f" based on commit '{commit_source}'."
        return text


@dataclass(frozen=True, slots=True)
class EffectiveBranchConfiguration:
    """An effective configuration paired with the branch it was resolved for."""

    value: EffectiveConfiguration
    branch: Branch


@functools.total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class NextVersion:
    """A candidate: base version, incremented form and branch config. Ports ``NextVersion``."""

    incremented_version: SemanticVersion
    base_version: BaseVersion
    branch_configuration: EffectiveBranchConfiguration

    @property
    def configuration(self) -> EffectiveConfiguration:
        """The effective configuration."""
        return self.branch_configuration.value

    def compare_to(self, other: NextVersion | None) -> int:
        """Compare by incremented version (pre-release included, metadata excluded)."""
        return self.incremented_version.compare_to(other.incremented_version if other else None)

    def __eq__(self, other: object) -> bool:
        """Equal when incremented versions compare equal (upstream ``==``)."""
        if not isinstance(other, NextVersion):
            return NotImplemented
        return self.compare_to(other) == 0

    def __hash__(self) -> int:
        """Hash on the string form, as upstream."""
        return hash(str(self))

    def __lt__(self, other: NextVersion) -> bool:
        """Order by incremented version."""
        return self.compare_to(other) < 0

    def __str__(self) -> str:
        """``base | incremented``."""
        return f"{self.base_version} | {self.incremented_version}"
