# SPDX-License-Identifier: MIT
"""The Mainline (trunk-based) version strategy.

Ports ``MainlineVersionStrategy`` and the ``VersionCalculation/Mainline``
folder from GitVersion 6.8.2: the iteration/commit tree built by walking the
branch history (recursing into merged branches), the pre/post context
enrichers, and the nineteen "incrementer" rules that translate that tree
into a sequence of base-version operands and operators.

The C# types map one to one so the port can be reviewed side by side:
``MainlineIteration``, ``MainlineCommit``, ``MainlineContext`` and one class
per incrementer, registered in the upstream order.
"""
# ruff: noqa: ARG001, ARG002 -- every rule shares the (iteration, commit, ctx) signature

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

from usg_pygitversion.calculation.base_version import (
    BaseVersion,
    BaseVersionOperand,
    BaseVersionOperator,
    EffectiveBranchConfiguration,
)
from usg_pygitversion.calculation.context import GitVersionContext
from usg_pygitversion.calculation.increment import (
    IncrementStrategyFinder,
    increment_strategy_to_field,
)
from usg_pygitversion.calculation.merge_message import MergeMessage, try_get_semantic_version
from usg_pygitversion.calculation.store import RepositoryStore
from usg_pygitversion.calculation.tagged_versions import (
    CommitLookup,
    TaggedSemanticVersions,
    TaggedSemanticVersionService,
)
from usg_pygitversion.config.effective import EffectiveConfiguration, get_branch_configuration
from usg_pygitversion.config.enums import (
    CommitMessageIncrementMode,
    IncrementStrategy,
    VersionStrategy,
)
from usg_pygitversion.config.schema import BranchConfiguration, GitVersionConfiguration
from usg_pygitversion.errors import GitVersionError
from usg_pygitversion.git.models import Branch, Commit
from usg_pygitversion.git.refname import ReferenceName
from usg_pygitversion.semver import SemanticVersion, VersionField

_log = logging.getLogger("usg_pygitversion.calculation")

Increment = BaseVersionOperand | BaseVersionOperator | BaseVersion


def consolidate(source: VersionField, *items: VersionField | None) -> VersionField:
    """Ports ``VersionFieldExtensions.Consolidate``: the largest of the given fields."""
    result = source
    for item in items:
        if item is not None and result < item:
            result = item
    return result


def _max_or_none(versions: Iterable[SemanticVersion]) -> SemanticVersion | None:
    items = list(versions)
    return max(items) if items else None


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


class MainlineIteration:
    """One walk over a branch's commits. Ports ``MainlineIteration``."""

    def __init__(
        self,
        id_: str,
        branch_name: ReferenceName,
        configuration: BranchConfiguration,
        parent_iteration: MainlineIteration | None,
        parent_commit: MainlineCommit | None,
    ) -> None:
        """Create an empty iteration."""
        self.id = id_
        self.branch_name = branch_name
        self.configuration = configuration
        self.parent_iteration = parent_iteration
        self.parent_commit = parent_commit
        self.depth: int = (parent_iteration.depth if parent_iteration is not None else 0) + 1
        self._stack: list[MainlineCommit] = []  # newest first, as pushed
        self._lookup: dict[str, MainlineCommit] = {}
        self._effective: EffectiveConfiguration | None = None

    @property
    def commits(self) -> list[MainlineCommit]:
        """Commits oldest first (upstream enumerates its ``Stack`` LIFO)."""
        return list(reversed(self._stack))

    @property
    def number_of_commits(self) -> int:
        """Count of commits."""
        return len(self._stack)

    def create_commit(
        self, value: Commit | None, branch_name: ReferenceName, configuration: BranchConfiguration
    ) -> MainlineCommit:
        """Append a (possibly dummy) commit below the current one. Ports ``CreateCommit``."""
        if self._stack:
            commit = self._stack[-1].append(value, branch_name, configuration)
        else:
            commit = MainlineCommit(self, value, branch_name, configuration)
        self._stack.append(commit)
        if value is not None:
            self._lookup[value.sha] = commit
        return commit

    def find_commit(self, commit: Commit) -> MainlineCommit | None:
        """Look up by git commit."""
        return self._lookup.get(commit.sha)

    def get_effective_configuration(
        self, configuration: GitVersionConfiguration
    ) -> EffectiveConfiguration:
        """Ports ``GetEffectiveConfiguration``: resolves ``Inherit`` through the first commit."""
        if self._effective is not None:
            return self._effective
        branch = self.configuration
        first = self.commits[0] if self._stack else None
        if branch.increment is not IncrementStrategy.INHERIT or first is None:
            self._effective = EffectiveConfiguration.create(configuration, branch)
            return self._effective
        parent = first.get_effective_configuration(configuration)
        self._effective = EffectiveConfiguration.create(
            configuration, branch.inherit(parent.as_branch())
        )
        return self._effective


class MainlineCommit:
    """A commit in the iteration chain. Ports ``MainlineCommit``."""

    def __init__(
        self,
        iteration: MainlineIteration,
        value: Commit | None,
        branch_name: ReferenceName,
        configuration: BranchConfiguration,
    ) -> None:
        """Create a commit node; ``value`` ``None`` makes it a dummy."""
        self.iteration = iteration
        self._value = value
        self.branch_name = branch_name
        self.configuration = configuration
        self.increment: VersionField = VersionField.NONE
        self.successor: MainlineCommit | None = None
        self.predecessor: MainlineCommit | None = None
        self.child_iteration: MainlineIteration | None = None
        self.semantic_versions: list[SemanticVersion] = []
        self._effective: EffectiveConfiguration | None = None

    @property
    def is_dummy(self) -> bool:
        """True for the synthetic commit inserted at a branch point."""
        return self._value is None

    @property
    def value(self) -> Commit | None:
        """The git commit; a dummy borrows its successor's (``None`` when it has none).

        Upstream ``Value`` is ``Successor?.Value`` for a dummy, so a dummy at the
        top of an iteration has no value at all; callers store it as-is.
        """
        if self._value is not None:
            return self._value
        return self.successor.value if self.successor is not None else None

    @property
    def message(self) -> str:
        """Commit message, or a marker for dummies."""
        return "<<DUMMY>>" if self._value is None else self._value.message

    @property
    def has_child_iteration(self) -> bool:
        """True when a merged branch was walked below this commit."""
        return self.child_iteration is not None and self.child_iteration.number_of_commits != 0

    @property
    def parent_iteration(self) -> MainlineIteration | None:
        """The iteration that merged this one."""
        return self.iteration.parent_iteration

    @property
    def parent_commit(self) -> MainlineCommit | None:
        """The merge commit in the parent iteration."""
        return self.iteration.parent_commit

    def add_semantic_versions(self, values: Iterable[SemanticVersion]) -> None:
        """Record tags on this commit (set semantics)."""
        for value in values:
            if value not in self.semantic_versions:
                self.semantic_versions.append(value)

    def add_child_iteration(self, iteration: MainlineIteration) -> None:
        """Attach the walked merged branch."""
        self.child_iteration = iteration

    def append(
        self, value: Commit | None, branch_name: ReferenceName, configuration: BranchConfiguration
    ) -> MainlineCommit:
        """Create the predecessor (older) commit. Ports ``Append``."""
        if self.predecessor is not None:
            raise GitVersionError("mainline commit already has a predecessor")
        commit = MainlineCommit(self.iteration, value, branch_name, configuration)
        self.predecessor = commit
        commit.successor = self
        return commit

    def get_effective_configuration(
        self, configuration: GitVersionConfiguration
    ) -> EffectiveConfiguration:
        """Ports ``GetEffectiveConfiguration``: inherit via predecessors, then the parent."""
        if self._effective is not None:
            return self._effective
        branch = self.configuration
        last = self.configuration
        node: MainlineCommit | None = self
        while node is not None:
            if branch.increment is not IncrementStrategy.INHERIT:
                break
            if node.configuration != last:
                branch = branch.inherit(node.configuration)
            last = node.configuration
            node = node.predecessor
        has_parent = (
            self.iteration.parent_iteration is not None and self.iteration.parent_commit is not None
        )
        if branch.increment is not IncrementStrategy.INHERIT or not has_parent:
            self._effective = EffectiveConfiguration.create(configuration, branch)
            return self._effective
        parent = self.iteration.parent_commit
        if parent is None:  # pragma: no cover -- guarded by has_parent
            raise GitVersionError("mainline iteration without parent commit")
        parent_effective = parent.get_effective_configuration(configuration)
        self._effective = EffectiveConfiguration.create(
            configuration, branch.inherit(parent_effective.as_branch())
        )
        return self._effective

    def get_increment_forced_by_branch(
        self, configuration: GitVersionConfiguration
    ) -> VersionField:
        """Ports ``GetIncrementForcedByBranch``."""
        return increment_strategy_to_field(
            self.get_effective_configuration(configuration).increment
        )

    def is_predecessor_the_last_commit_on_trunk(
        self, configuration: GitVersionConfiguration
    ) -> bool:
        """Ports ``IsPredecessorTheLastCommitOnTrunk``."""
        if self.get_effective_configuration(configuration).is_main_branch:
            return False
        return (
            self.predecessor is not None
            and self.predecessor.get_effective_configuration(configuration).is_main_branch
        )


@dataclass
class MainlineContext:
    """Mutable state threaded through the incrementers. Ports ``MainlineContext``."""

    increments: IncrementStrategyFinder
    configuration: GitVersionConfiguration
    environment: Mapping[str, str]
    target_label: str | None = None
    semantic_version: SemanticVersion | None = None
    label: str | None = None
    increment: VersionField = VersionField.NONE
    base_version_source: Commit | None = None
    alternative_semantic_versions: list[SemanticVersion] = field(default_factory=list)
    force_increment: bool = False

    def add_alternative(self, version: SemanticVersion) -> None:
        """Set-add into the alternatives."""
        if version not in self.alternative_semantic_versions:
            self.alternative_semantic_versions.append(version)

    def alternative_max(self) -> SemanticVersion | None:
        """``AlternativeSemanticVersions.Max()`` (``None`` when empty)."""
        return _max_or_none(self.alternative_semantic_versions)


def _label_of(
    effective: EffectiveConfiguration, name: ReferenceName, ctx: MainlineContext
) -> str | None:
    return effective.branch_specific_label(name, None, ctx.environment)


# ---------------------------------------------------------------------------
# Enrichers
# ---------------------------------------------------------------------------


def enrich_semantic_version(
    iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
) -> None:
    """Ports ``EnrichSemanticVersion``: pick the best tag on the commit for the label."""
    label = ctx.target_label
    if label is None:
        label = _label_of(
            iteration.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )
    if label is None:
        label = _label_of(
            commit.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )
    matching = [v for v in commit.semantic_versions if v.is_match_for_branch_specific_label(label)]
    for other in commit.semantic_versions:
        if other not in matching:
            ctx.add_alternative(other)
    ctx.semantic_version = _max_or_none(matching)


def enrich_increment(
    iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
) -> None:
    """Ports ``EnrichIncrement``."""
    effective = commit.get_effective_configuration(ctx.configuration)
    by_branch = increment_strategy_to_field(effective.increment)
    git_commit = commit.value
    by_commit = (
        VersionField.NONE
        if commit.is_dummy or git_commit is None
        else _increment_forced_by_commit(ctx, git_commit, effective)
    )
    commit.increment = by_commit
    ctx.increment = consolidate(ctx.increment, by_branch, by_commit)
    if commit.predecessor is not None and commit.predecessor.branch_name != commit.branch_name:
        ctx.label = None
    if ctx.label is None:
        ctx.label = _label_of(effective, commit.branch_name, ctx)
    if effective.is_main_branch:
        ctx.base_version_source = (
            commit.predecessor.value if commit.predecessor is not None else None
        )
    ctx.force_increment = ctx.force_increment or (
        effective.is_main_branch
        or commit.is_predecessor_the_last_commit_on_trunk(ctx.configuration)
    )


def _increment_forced_by_commit(
    ctx: MainlineContext, commit: Commit, effective: EffectiveConfiguration
) -> VersionField:
    mode = effective.commit_message_incrementing
    if mode is CommitMessageIncrementMode.ENABLED:
        return ctx.increments.get_increment_forced_by_commit(commit, effective)
    if mode is CommitMessageIncrementMode.DISABLED:
        return VersionField.NONE
    return (
        ctx.increments.get_increment_forced_by_commit(commit, effective)
        if commit.is_merge
        else VersionField.NONE
    )


def remove_semantic_version(commit: MainlineCommit, ctx: MainlineContext) -> None:
    """Ports ``RemoveSemanticVersion``."""
    ctx.semantic_version = None


def remove_increment(commit: MainlineCommit, ctx: MainlineContext) -> None:
    """Ports ``RemoveIncrement``: reset after a trunk commit."""
    if not commit.get_effective_configuration(ctx.configuration).is_main_branch:
        return
    ctx.increment = VersionField.NONE
    ctx.label = None
    ctx.alternative_semantic_versions.clear()


# ---------------------------------------------------------------------------
# Incrementers
# ---------------------------------------------------------------------------


def _operator(ctx: MainlineContext, source: str, **overrides: object) -> BaseVersionOperator:
    values: dict[str, object] = {
        "source": source,
        "base_version_source": ctx.base_version_source,
        "increment": ctx.increment,
        "force_increment": ctx.force_increment,
        "label": ctx.label,
        "alternative_semantic_version": ctx.alternative_max(),
    }
    values.update(overrides)
    return BaseVersionOperator(**values)  # type: ignore[arg-type]


class Incrementer:
    """Base for one rule. Subclasses override ``match`` and ``increments``."""

    name = "Incrementer"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """Precondition."""
        raise NotImplementedError

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """Yield operands/operators and mutate ``ctx``."""
        raise NotImplementedError


def _is_main(commit: MainlineCommit, ctx: MainlineContext) -> bool:
    return commit.get_effective_configuration(ctx.configuration).is_main_branch


class CommitOnTrunk(Incrementer):
    """Ports ``CommitOnTrunk``."""

    name = "CommitOnTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            not commit.has_child_iteration
            and _is_main(commit, ctx)
            and ctx.semantic_version is None
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        if commit.predecessor is not None and commit.predecessor.branch_name != commit.branch_name:
            ctx.label = None
        effective = commit.get_effective_configuration(ctx.configuration)
        if ctx.label is None:
            ctx.label = _label_of(effective, commit.branch_name, ctx)
        ctx.force_increment = True
        yield _operator(ctx, self.name)
        ctx.base_version_source = commit.value


class CommitOnTrunkBranchedBase(Incrementer):
    """Ports ``CommitOnTrunkBranchedBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            _is_main(commit, ctx)
            and commit.branch_name != iteration.branch_name
            and commit.successor is None
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        iteration_effective = iteration.get_effective_configuration(ctx.configuration)
        if iteration_effective.is_release_branch:
            found = try_get_semantic_version(
                iteration.branch_name,
                iteration_effective.version_in_branch_pattern,
                iteration_effective.tag_prefix,
                iteration_effective.semantic_version_format,
            )
            if found is not None:
                ctx.add_alternative(found.value)
        if iteration.configuration.increment is IncrementStrategy.INHERIT:
            ctx.increment = commit.get_increment_forced_by_branch(ctx.configuration)
        else:
            ctx.increment = increment_strategy_to_field(iteration.configuration.increment)
        label = _label_of(iteration_effective, iteration.branch_name, ctx)
        ctx.label = label if label is not None else ctx.label
        ctx.force_increment = True
        yield _operator(ctx, self.name)


class CommitOnTrunkBranchedToTrunk(CommitOnTrunkBranchedBase):
    """Ports ``CommitOnTrunkBranchedToTrunk``."""

    name = "CommitOnTrunkBranchedToTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            super().match(iteration, commit, ctx)
            and iteration.get_effective_configuration(ctx.configuration).is_main_branch
        )


class CommitOnTrunkBranchedToNonTrunk(CommitOnTrunkBranchedBase):
    """Ports ``CommitOnTrunkBranchedToNonTrunk``."""

    name = "CommitOnTrunkBranchedToNonTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            super().match(iteration, commit, ctx)
            and not iteration.get_effective_configuration(ctx.configuration).is_main_branch
        )


class CommitOnTrunkWithPreReleaseTagBase(Incrementer):
    """Ports ``CommitOnTrunkWithPreReleaseTagBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            _is_main(commit, ctx)
            and not commit.has_child_iteration
            and ctx.semantic_version is not None
            and ctx.semantic_version.is_prerelease
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        assert ctx.semantic_version is not None  # noqa: S101 -- precondition
        yield BaseVersionOperand(self.name, ctx.semantic_version, ctx.base_version_source)


class CommitOnTrunkWithPreReleaseTag(CommitOnTrunkWithPreReleaseTagBase):
    """Ports ``CommitOnTrunkWithPreReleaseTag``."""

    name = "CommitOnTrunkWithPreReleaseTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastCommitOnTrunkWithPreReleaseTag(CommitOnTrunkWithPreReleaseTagBase):
    """Ports ``LastCommitOnTrunkWithPreReleaseTag``."""

    name = "LastCommitOnTrunkWithPreReleaseTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        yield from super().increments(iteration, commit, ctx)
        if not iteration.get_effective_configuration(ctx.configuration).is_main_branch:
            return
        ctx.increment = commit.get_increment_forced_by_branch(ctx.configuration)
        ctx.label = _label_of(
            commit.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )
        ctx.force_increment = False
        yield _operator(ctx, self.name)


class CommitOnTrunkWithStableTagBase(Incrementer):
    """Ports ``CommitOnTrunkWithStableTagBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            _is_main(commit, ctx)
            and not commit.has_child_iteration
            and ctx.semantic_version is not None
            and not ctx.semantic_version.is_prerelease
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        assert ctx.semantic_version is not None  # noqa: S101 -- precondition
        yield BaseVersionOperand(self.name, ctx.semantic_version, ctx.base_version_source)
        ctx.label = _label_of(
            commit.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )


class CommitOnTrunkWithStableTag(CommitOnTrunkWithStableTagBase):
    """Ports ``CommitOnTrunkWithStableTag``."""

    name = "CommitOnTrunkWithStableTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastCommitOnTrunkWithStableTag(CommitOnTrunkWithStableTagBase):
    """Ports ``LastCommitOnTrunkWithStableTag``."""

    name = "LastCommitOnTrunkWithStableTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        yield from super().increments(iteration, commit, ctx)
        if not iteration.get_effective_configuration(ctx.configuration).is_main_branch:
            return
        ctx.force_increment = True
        yield _operator(ctx, self.name)


class MergeCommitOnTrunkBase(Incrementer):
    """Ports ``MergeCommitOnTrunkBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return commit.has_child_iteration and _is_main(commit, ctx) and ctx.semantic_version is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        child = commit.child_iteration
        if child is None:
            raise GitVersionError("The commit child iteration is null.")
        base_version = determine_base_version_recursive(
            child, ctx.target_label, ctx.increments, ctx.configuration, ctx.environment
        )
        if ctx.label is None and base_version.operator is not None:
            ctx.label = base_version.operator.label
        effective = commit.get_effective_configuration(ctx.configuration)
        increment = VersionField.NONE
        if not effective.prevent_increment_of_merged_branch:
            increment = consolidate(increment, ctx.increment)
        if not child.get_effective_configuration(
            ctx.configuration
        ).prevent_increment_when_branch_merged:
            increment = consolidate(
                increment, base_version.operator.increment if base_version.operator else None
            )
        if effective.commit_message_incrementing is not CommitMessageIncrementMode.DISABLED:
            increment = consolidate(increment, commit.increment)
        ctx.increment = increment
        if base_version.base_version_source is not None:
            ctx.base_version_source = base_version.base_version_source
            ctx.semantic_version = base_version.semantic_version
            ctx.force_increment = (
                base_version.operator.force_increment if base_version.operator else False
            )
        elif (
            base_version.operator is not None
            and base_version.operator.alternative_semantic_version is not None
        ):
            ctx.add_alternative(base_version.operator.alternative_semantic_version)
        if ctx.semantic_version is not None:
            yield BaseVersionOperand(self.name, ctx.semantic_version, ctx.base_version_source)
        yield _operator(ctx, self.name)
        ctx.base_version_source = commit.value


class MergeCommitOnTrunk(MergeCommitOnTrunkBase):
    """Ports ``MergeCommitOnTrunk``."""

    name = "MergeCommitOnTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastMergeCommitOnTrunk(MergeCommitOnTrunkBase):
    """Ports ``LastMergeCommitOnTrunk``."""

    name = "LastMergeCommitOnTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None


class FirstCommitOnRelease(Incrementer):
    """Ports ``FirstCommitOnRelease``."""

    name = "FirstCommitOnRelease"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        effective = commit.get_effective_configuration(ctx.configuration)
        return (
            not commit.has_child_iteration
            and not effective.is_main_branch
            and effective.is_release_branch
            and ctx.semantic_version is None
            and (commit.predecessor is None or commit.branch_name != commit.predecessor.branch_name)
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        effective = commit.get_effective_configuration(ctx.configuration)
        found = try_get_semantic_version(
            commit.branch_name,
            effective.version_in_branch_pattern,
            effective.tag_prefix,
            effective.semantic_version_format,
        )
        if found is not None:
            ctx.add_alternative(found.value)
        yield from ()


class CommitOnNonTrunk(Incrementer):
    """Ports ``CommitOnNonTrunk``."""

    name = "CommitOnNonTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            not commit.has_child_iteration
            and not _is_main(commit, ctx)
            and ctx.semantic_version is None
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        if commit.predecessor is not None and commit.predecessor.branch_name != commit.branch_name:
            ctx.label = None
        effective = commit.get_effective_configuration(ctx.configuration)
        if ctx.label is None:
            ctx.label = _label_of(effective, commit.branch_name, ctx)
        if commit.successor is not None:
            return
        yield _operator(ctx, self.name)
        ctx.base_version_source = commit.value
        ctx.force_increment = False


class CommitOnNonTrunkBranchedBase(Incrementer):
    """Ports ``CommitOnNonTrunkBranchedBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            not _is_main(commit, ctx)
            and commit.branch_name != iteration.branch_name
            and commit.successor is None
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        if iteration.configuration.increment is IncrementStrategy.INHERIT:
            by_branch = commit.get_increment_forced_by_branch(ctx.configuration)
        else:
            by_branch = increment_strategy_to_field(iteration.configuration.increment)
        ctx.increment = consolidate(ctx.increment, by_branch)
        iteration_effective = iteration.get_effective_configuration(ctx.configuration)
        label = _label_of(iteration_effective, iteration.branch_name, ctx)
        ctx.label = label if label is not None else ctx.label
        ctx.force_increment = True
        yield _operator(
            ctx,
            self.name,
            base_version_source=None,
            increment=VersionField.NONE,
            force_increment=False,
        )


class CommitOnNonTrunkBranchedToTrunk(CommitOnNonTrunkBranchedBase):
    """Ports ``CommitOnNonTrunkBranchedToTrunk``."""

    name = "CommitOnNonTrunkBranchedToTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            super().match(iteration, commit, ctx)
            and iteration.get_effective_configuration(ctx.configuration).is_main_branch
        )


class CommitOnNonTrunkBranchedToNonTrunk(CommitOnNonTrunkBranchedBase):
    """Ports ``CommitOnNonTrunkBranchedToNonTrunk``."""

    name = "CommitOnNonTrunkBranchedToNonTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            super().match(iteration, commit, ctx)
            and not iteration.get_effective_configuration(ctx.configuration).is_main_branch
        )


class CommitOnNonTrunkWithPreReleaseTagBase(Incrementer):
    """Ports ``CommitOnNonTrunkWithPreReleaseTagBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            not commit.has_child_iteration
            and not _is_main(commit, ctx)
            and ctx.semantic_version is not None
            and ctx.semantic_version.is_prerelease
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        assert ctx.semantic_version is not None  # noqa: S101 -- precondition
        yield BaseVersionOperand(self.name, ctx.semantic_version, ctx.base_version_source)
        ctx.increment = commit.get_increment_forced_by_branch(ctx.configuration)
        ctx.label = _label_of(
            commit.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )
        ctx.force_increment = False


class CommitOnNonTrunkWithPreReleaseTag(CommitOnNonTrunkWithPreReleaseTagBase):
    """Ports ``CommitOnNonTrunkWithPreReleaseTag``."""

    name = "CommitOnNonTrunkWithPreReleaseTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastCommitOnNonTrunkWithPreReleaseTag(CommitOnNonTrunkWithPreReleaseTagBase):
    """Ports ``LastCommitOnNonTrunkWithPreReleaseTag``."""

    name = "LastCommitOnNonTrunkWithPreReleaseTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        yield from super().increments(iteration, commit, ctx)
        yield _operator(ctx, self.name, force_increment=False)


class CommitOnNonTrunkWithStableTagBase(Incrementer):
    """Ports ``CommitOnNonTrunkWithStableTagBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            not _is_main(commit, ctx)
            and not commit.has_child_iteration
            and ctx.semantic_version is not None
            and not ctx.semantic_version.is_prerelease
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        ctx.base_version_source = commit.value
        assert ctx.semantic_version is not None  # noqa: S101 -- precondition
        yield BaseVersionOperand(self.name, ctx.semantic_version, ctx.base_version_source)
        ctx.increment = commit.get_increment_forced_by_branch(ctx.configuration)
        ctx.label = _label_of(
            commit.get_effective_configuration(ctx.configuration), commit.branch_name, ctx
        )


class CommitOnNonTrunkWithStableTag(CommitOnNonTrunkWithStableTagBase):
    """Ports ``CommitOnNonTrunkWithStableTag``."""

    name = "CommitOnNonTrunkWithStableTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastCommitOnNonTrunkWithStableTag(CommitOnNonTrunkWithStableTagBase):
    """Ports ``LastCommitOnNonTrunkWithStableTag``."""

    name = "LastCommitOnNonTrunkWithStableTag"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        yield from super().increments(iteration, commit, ctx)
        yield _operator(ctx, self.name, force_increment=True)


class MergeCommitOnNonTrunkBase(Incrementer):
    """Ports ``MergeCommitOnNonTrunkBase``."""

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return (
            commit.has_child_iteration
            and not _is_main(commit, ctx)
            and ctx.semantic_version is None
        )

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream (yields nothing; only mutates the context)."""
        child = commit.child_iteration
        if child is None:
            raise GitVersionError("The commit child iteration is null.")
        base_version = determine_base_version_recursive(
            child, ctx.target_label, ctx.increments, ctx.configuration, ctx.environment
        )
        if ctx.label is None and base_version.operator is not None:
            ctx.label = base_version.operator.label
        ctx.increment = self._consolidate_increment(commit, ctx, base_version)
        self._apply_base_version(ctx, base_version)
        yield from ()

    @staticmethod
    def _consolidate_increment(
        commit: MainlineCommit, ctx: MainlineContext, base_version: BaseVersion
    ) -> VersionField:
        effective = commit.get_effective_configuration(ctx.configuration)
        increment = VersionField.NONE
        if not effective.prevent_increment_of_merged_branch:
            increment = consolidate(increment, ctx.increment)
        if not effective.prevent_increment_when_branch_merged:
            increment = consolidate(
                increment, base_version.operator.increment if base_version.operator else None
            )
        if effective.commit_message_incrementing is not CommitMessageIncrementMode.DISABLED:
            increment = consolidate(increment, commit.increment)
        return increment

    @staticmethod
    def _apply_base_version(ctx: MainlineContext, base_version: BaseVersion) -> None:
        if base_version.base_version_source is not None:
            ctx.base_version_source = base_version.base_version_source
            ctx.semantic_version = base_version.semantic_version
            return
        if base_version.semantic_version != SemanticVersion():
            ctx.add_alternative(base_version.semantic_version)
        if (
            base_version.operator is not None
            and base_version.operator.alternative_semantic_version is not None
        ):
            ctx.add_alternative(base_version.operator.alternative_semantic_version)


class MergeCommitOnNonTrunk(MergeCommitOnNonTrunkBase):
    """Ports ``MergeCommitOnNonTrunk``."""

    name = "MergeCommitOnNonTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is not None


class LastMergeCommitOnNonTrunk(MergeCommitOnNonTrunkBase):
    """Ports ``LastMergeCommitOnNonTrunk``."""

    name = "LastMergeCommitOnNonTrunk"

    def match(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> bool:
        """See upstream."""
        return super().match(iteration, commit, ctx) and commit.successor is None

    def increments(
        self, iteration: MainlineIteration, commit: MainlineCommit, ctx: MainlineContext
    ) -> Iterator[Increment]:
        """See upstream."""
        yield from super().increments(iteration, commit, ctx)
        label = ctx.target_label if ctx.target_label is not None else ctx.label
        yield _operator(ctx, self.name, label=label)


#: Upstream ``TrunkIncrementerCollection`` order.
INCREMENTERS: tuple[Incrementer, ...] = (
    CommitOnTrunk(),
    CommitOnTrunkWithPreReleaseTag(),
    LastCommitOnTrunkWithPreReleaseTag(),
    CommitOnTrunkWithStableTag(),
    LastCommitOnTrunkWithStableTag(),
    MergeCommitOnTrunk(),
    LastMergeCommitOnTrunk(),
    CommitOnTrunkBranchedToTrunk(),
    CommitOnTrunkBranchedToNonTrunk(),
    FirstCommitOnRelease(),
    CommitOnNonTrunk(),
    CommitOnNonTrunkWithPreReleaseTag(),
    LastCommitOnNonTrunkWithPreReleaseTag(),
    CommitOnNonTrunkWithStableTag(),
    LastCommitOnNonTrunkWithStableTag(),
    MergeCommitOnNonTrunk(),
    LastMergeCommitOnNonTrunk(),
    CommitOnNonTrunkBranchedToTrunk(),
    CommitOnNonTrunkBranchedToNonTrunk(),
)


# ---------------------------------------------------------------------------
# Folding the tree into a base version
# ---------------------------------------------------------------------------


def _get_increments(
    iteration: MainlineIteration,
    target_label: str | None,
    increments: IncrementStrategyFinder,
    configuration: GitVersionConfiguration,
    environment: Mapping[str, str],
) -> Iterator[Increment]:
    """Ports ``GetIncrements``: enrich, run matching incrementers, post-enrich, per commit."""
    ctx = MainlineContext(increments, configuration, environment, target_label=target_label)
    for commit in iteration.commits:
        enrich_semantic_version(iteration, commit, ctx)
        enrich_increment(iteration, commit, ctx)
        # Upstream evaluates every precondition before running any incrementer
        # (LINQ Where is lazy but the loop body mutates ctx only after a match
        # is found, one incrementer at a time). Mirror that exactly.
        for incrementer in INCREMENTERS:
            if incrementer.match(iteration, commit, ctx):
                yield from incrementer.increments(iteration, commit, ctx)
        remove_semantic_version(commit, ctx)
        remove_increment(commit, ctx)


def determine_base_version_recursive(
    iteration: MainlineIteration,
    target_label: str | None,
    increments: IncrementStrategyFinder,
    configuration: GitVersionConfiguration,
    environment: Mapping[str, str],
) -> BaseVersion:
    """Ports ``DetermineBaseVersionRecursive``: fold operands and operators left to right."""
    result: BaseVersion | None = None
    for step in _get_increments(iteration, target_label, increments, configuration, environment):
        if isinstance(step, BaseVersionOperand):
            result = BaseVersion(step)
        elif isinstance(step, BaseVersionOperator):
            result = (result if result is not None else BaseVersion()).apply(step)
        else:
            result = step
    if result is None:
        raise GitVersionError("mainline iteration produced no base version")
    return result


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


@dataclass
class _TraversalState:
    """Ports the private ``TraversalState``."""

    configuration: BranchConfiguration
    branch_name: ReferenceName
    branch: Branch | None
    tagged: CommitLookup
    branched_from: dict[str, list[tuple[Branch, BranchConfiguration]]] | None = None
    branched_from_loader: object = None
    return_true_when_the_increment_is_known: bool = False


class MainlineStrategy:
    """Ports ``MainlineVersionStrategy``."""

    name = "Mainline"

    def __init__(
        self,
        context: GitVersionContext,
        store: RepositoryStore,
        tags: TaggedSemanticVersionService,
        increments: IncrementStrategyFinder,
    ) -> None:
        """Wire the collaborators."""
        self.context = context
        self.store = store
        self.tags = tags
        self.increments = increments
        self._iteration_counter = 0
        self._branched_from_cache: dict[
            str, dict[str, list[tuple[Branch, BranchConfiguration]]]
        ] = {}

    # -- entry -----------------------------------------------------------------

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """Ports ``GetBaseVersions``."""
        ctx = self.context
        if not ctx.configuration.version_strategy & VersionStrategy.MAINLINE:
            return
        branch_configuration = get_branch_configuration(ctx.configuration, ctx.current_branch.name)
        iteration = self._create_iteration(ctx.current_branch.name, branch_configuration)
        commits = self.store.filters(ctx.configuration.ignore).commits(
            ctx.current_branch_commits(self.store)
        )
        flags = TaggedSemanticVersions.OF_BRANCH
        if branch_configuration.track_merge_target is True:
            flags |= TaggedSemanticVersions.OF_MERGE_TARGETS
        if branch_configuration.tracks_release_branches is True:
            flags |= TaggedSemanticVersions.OF_RELEASE_BRANCHES
        if not (
            branch_configuration.is_main_branch is True
            or branch_configuration.is_release_branch is True
        ):
            flags |= TaggedSemanticVersions.OF_MAIN_BRANCHES
        tagged = self.tags.get_tagged_semantic_versions(
            ctx.current_branch, ctx.configuration, None, ctx.current_commit.when, flags
        )
        target_label = configuration.value.branch_specific_label(
            ctx.current_branch.name, None, ctx.environment
        )
        self._iterate(commits, iteration, configuration.branch, target_label, tagged, set())
        yield determine_base_version_recursive(
            iteration, target_label, self.increments, ctx.configuration, ctx.environment
        )

    def _create_iteration(
        self,
        branch_name: ReferenceName,
        configuration: BranchConfiguration,
        parent_iteration: MainlineIteration | None = None,
        parent_commit: MainlineCommit | None = None,
    ) -> MainlineIteration:
        self._iteration_counter += 1
        return MainlineIteration(
            f"#{self._iteration_counter}",
            branch_name,
            configuration,
            parent_iteration,
            parent_commit,
        )

    # -- traversal -------------------------------------------------------------

    def _tag_flags(self, branch_configuration: BranchConfiguration) -> TaggedSemanticVersions:
        root = self.context.configuration
        flags = TaggedSemanticVersions.OF_BRANCH
        track_merge_target = branch_configuration.track_merge_target
        if (
            track_merge_target if track_merge_target is not None else root.track_merge_target
        ) is True:
            flags |= TaggedSemanticVersions.OF_MERGE_TARGETS
        tracks_release = branch_configuration.tracks_release_branches
        if (tracks_release if tracks_release is not None else root.tracks_release_branches) is True:
            flags |= TaggedSemanticVersions.OF_RELEASE_BRANCHES
        if not (
            branch_configuration.is_main_branch is True
            or branch_configuration.is_release_branch is True
        ):
            flags |= TaggedSemanticVersions.OF_MAIN_BRANCHES
        return flags

    def _branched_from(
        self, state: _TraversalState
    ) -> dict[str, list[tuple[Branch, BranchConfiguration]]]:
        if state.branched_from is None:
            loader = state.branched_from_loader
            state.branched_from = loader() if callable(loader) else {}
        return state.branched_from

    def _iterate(
        self,
        commits: Iterable[Commit],
        iteration: MainlineIteration,
        target_branch: Branch,
        target_label: str | None,
        tagged: CommitLookup,
        traversed: set[str],
    ) -> bool:
        """Ports ``IterateOverCommitsRecursive``."""
        branch = self.store.find_branch(iteration.branch_name)
        state = _TraversalState(
            configuration=iteration.configuration,
            branch_name=iteration.branch_name,
            branch=branch,
            tagged=tagged,
            branched_from_loader=(
                lambda b=branch: {} if b is None else self._commits_was_branched_from(b)
            ),
        )
        for item in commits:
            if item.sha in traversed:
                continue
            traversed.add(item.sha)
            self._apply_branched_from_transition(item, iteration, target_branch, state)
            commit, stop = self._process_commit(item, iteration, target_label, state)
            if stop:
                return True
            if item.is_merge and self._handle_merge_commit(
                item, commit, iteration, target_branch, target_label, state, traversed
            ):
                return True
        return False

    def _apply_branched_from_transition(
        self,
        item: Commit,
        iteration: MainlineIteration,
        target_branch: Branch,
        state: _TraversalState,
    ) -> None:
        """Ports ``ApplyBranchedFromTransition``."""
        candidates = self._branched_from(state).get(item.sha)
        if not candidates:
            return
        first_branch, first_configuration = candidates[0]
        if (
            state.configuration.is_main_branch is True
            and first_configuration.is_main_branch is not True
        ):
            return
        exclude_branch = state.branch
        if any(b != first_branch and b == target_branch for b, _ in candidates):
            iteration.create_commit(
                None,
                target_branch.name,
                get_branch_configuration(self.context.configuration, target_branch.name),
            )
        state.configuration = first_configuration
        state.branch_name = first_branch.name
        state.branch = self.store.find_branch(state.branch_name)
        pointer = state.branch
        excluded = [exclude_branch] if exclude_branch is not None else []
        state.branched_from = None
        state.branched_from_loader = lambda b=pointer, ex=tuple(excluded): (
            {} if b is None else self._commits_was_branched_from(b, *ex)
        )
        state.tagged = self.tags.get_tagged_semantic_versions(
            first_branch,
            self.context.configuration,
            None,
            self.context.current_commit.when,
            self._tag_flags(state.configuration),
        )

    def _process_commit(
        self,
        item: Commit,
        iteration: MainlineIteration,
        target_label: str | None,
        state: _TraversalState,
    ) -> tuple[MainlineCommit, bool]:
        """Ports ``ProcessCommit``."""
        commit = iteration.create_commit(item, state.branch_name, state.configuration)
        versions = state.tagged[item]
        commit.add_semantic_versions(v.value for v in versions)
        label = target_label
        if label is None:
            label = EffectiveConfiguration.create(
                self.context.configuration, state.configuration
            ).branch_specific_label(state.branch_name, None, self.context.environment)
        for version in versions:
            if not version.value.is_match_for_branch_specific_label(label):
                continue
            if state.configuration.increment is not IncrementStrategy.INHERIT:
                return commit, True
            state.return_true_when_the_increment_is_known = True
        if (
            state.return_true_when_the_increment_is_known
            and state.configuration.increment is not IncrementStrategy.INHERIT
        ):
            return commit, True
        return commit, False

    def _handle_merge_commit(
        self,
        item: Commit,
        commit: MainlineCommit,
        iteration: MainlineIteration,
        target_branch: Branch,
        target_label: str | None,
        state: _TraversalState,
        traversed: set[str],
    ) -> bool:
        """Ports ``HandleMergeCommit``."""
        root = self.context.configuration
        track = state.configuration.track_merge_message
        if (track if track is not None else root.track_merge_message) is not True:
            return False
        merge = MergeMessage.try_parse(item, root)
        if merge is None or merge.merged_branch is None:
            return False
        if merge.merged_branch.equivalent_to(state.branch_name.without_origin):
            return False
        child_configuration = get_branch_configuration(root, merge.merged_branch)
        child_branch_name = merge.merged_branch
        merged_side = 1
        if child_configuration.is_main_branch is True:
            if state.configuration.is_main_branch is True:
                raise GitVersionError(
                    "merging a main branch into a main branch is not supported by Mainline"
                )
            merged_side = 0
            child_configuration = state.configuration
            child_branch_name = iteration.branch_name
        merged = list(reversed(self.increments.get_merged_commits(item, merged_side, root.ignore)))
        child_iteration = self._create_iteration(
            child_branch_name, child_configuration, iteration, commit
        )
        done = self._iterate(
            merged, child_iteration, target_branch, target_label, state.tagged, traversed
        )
        commit.add_child_iteration(child_iteration)
        if done:
            return True
        traversed.update(c.sha for c in merged)
        return False

    def _commits_was_branched_from(
        self, branch: Branch, *excluded: Branch
    ) -> dict[str, list[tuple[Branch, BranchConfiguration]]]:
        """Ports ``GetCommitsWasBranchedFrom``: branch-point commit -> candidate source branches."""
        root = self.context.configuration
        key = branch.name.canonical + "|" + ",".join(sorted(b.name.canonical for b in excluded))
        cached = self._branched_from_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, list[tuple[Branch, BranchConfiguration]]] = {}
        branch_commits = self.store.find_merge_commits_for(branch, root, excluded)
        by_branch: dict[Branch, Commit] = {}
        for bc in branch_commits:
            by_branch[bc.branch] = bc.commit  # ToDictionary: last wins for duplicate branches
        for candidate, commit in by_branch.items():
            branch_configuration = get_branch_configuration(root, candidate.name)
            existing = result.get(commit.sha)
            if existing is not None:
                if (
                    branch_configuration.increment is IncrementStrategy.INHERIT
                    and branch_configuration.is_main_branch is None
                ):
                    raise GitVersionError(
                        "ambiguous branch point with an inheriting candidate branch"
                    )
                is_main = branch_configuration.is_main_branch
                if (is_main if is_main is not None else root.is_main_branch) is True:
                    existing.append((candidate, branch_configuration))
            else:
                result[commit.sha] = [(candidate, branch_configuration)]
        for sha, items in result.items():

            def is_main_key(entry: tuple[Branch, BranchConfiguration]) -> bool:
                value = entry[1].is_main_branch
                return (value if value is not None else root.is_main_branch) is True

            result[sha] = sorted(items, key=is_main_key, reverse=True)
        self._branched_from_cache[key] = result
        return result
