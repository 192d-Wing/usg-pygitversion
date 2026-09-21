# SPDX-License-Identifier: MIT
"""The version-source strategies. Ports ``VersionSearchStrategies/*`` (6.8.2) except Mainline.

Each strategy yields :class:`BaseVersion` candidates for one effective
branch configuration. Order of registration follows upstream's assembly
type order (source-file order) with ``Fallback`` moved last by the
calculator.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Protocol

from usg_pygitversion.calculation.base_version import (
    BaseVersion,
    BaseVersionOperator,
    EffectiveBranchConfiguration,
)
from usg_pygitversion.calculation.context import GitVersionContext
from usg_pygitversion.calculation.increment import IncrementStrategyFinder
from usg_pygitversion.calculation.mainline import MainlineStrategy
from usg_pygitversion.calculation.merge_message import MergeMessage, try_get_semantic_version
from usg_pygitversion.calculation.store import RepositoryStore
from usg_pygitversion.calculation.tagged_versions import (
    SemanticVersionWithTag,
    TaggedSemanticVersions,
    TaggedSemanticVersionService,
)
from usg_pygitversion.config.effective import (
    EffectiveConfiguration,
    get_branch_configuration,
    get_effective_configuration,
    is_release_branch,
)
from usg_pygitversion.config.enums import VersionStrategy
from usg_pygitversion.git.models import Branch, Commit
from usg_pygitversion.semver import IncrementMode, SemanticVersion, VersionField

_log = logging.getLogger("usg_pygitversion.calculation")


def tagged_semantic_version_flags(configuration: EffectiveConfiguration) -> TaggedSemanticVersions:
    """Ports ``EffectiveConfiguration.GetTaggedSemanticVersion``."""
    flags = TaggedSemanticVersions.OF_BRANCH
    if configuration.track_merge_target:
        flags |= TaggedSemanticVersions.OF_MERGE_TARGETS
    if configuration.tracks_release_branches:
        flags |= TaggedSemanticVersions.OF_RELEASE_BRANCHES
    if not configuration.is_main_branch and not configuration.is_release_branch:
        flags |= TaggedSemanticVersions.OF_MAIN_BRANCHES
    return flags


class Services:
    """The collaborators every strategy shares."""

    def __init__(
        self,
        context: GitVersionContext,
        store: RepositoryStore,
        tags: TaggedSemanticVersionService,
        increments: IncrementStrategyFinder,
    ) -> None:
        """Bundle the collaborators."""
        self.context = context
        self.store = store
        self.tags = tags
        self.increments = increments

    def label(
        self, configuration: EffectiveConfiguration, override: str | None = None
    ) -> str | None:
        """``GetBranchSpecificLabel`` for the current branch."""
        return configuration.branch_specific_label(
            self.context.current_branch.name, override, self.context.environment
        )

    def enabled(self, strategy: VersionStrategy) -> bool:
        """Whether ``strategy`` is switched on in the configuration."""
        return bool(self.context.configuration.version_strategy & strategy)


class Strategy(Protocol):
    """A version-source strategy."""

    name: str

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """Yield candidates."""
        ...


class ConfiguredNextVersionStrategy:
    """Ports ``ConfiguredNextVersionVersionStrategy``."""

    name = "ConfiguredNextVersion"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``ConfiguredNextVersionVersionStrategy.GetBaseVersions``."""
        ctx = self.s.context
        if not self.s.enabled(VersionStrategy.CONFIGURED_NEXT_VERSION):
            return
        next_version = ctx.configuration.next_version
        if not next_version:
            return
        version = SemanticVersion.parse(
            next_version, ctx.configuration.tag_prefix, ctx.configuration.semantic_version_format
        )
        label = self.s.label(configuration.value)
        if not version.is_match_for_branch_specific_label(label):
            return
        operator: BaseVersionOperator | None = None
        if not version.is_prerelease or (label is not None and version.prerelease.name != label):
            operator = BaseVersionOperator(
                increment=VersionField.NONE, force_increment=False, label=label
            )
        yield BaseVersion.of(
            "NextVersion in GitVersion configuration file", version, operator=operator
        )


class FallbackStrategy:
    """Ports ``FallbackVersionStrategy``."""

    name = "Fallback"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``FallbackVersionStrategy.GetBaseVersions``."""
        ctx = self.s.context
        if not self.s.enabled(VersionStrategy.FALLBACK):
            return
        label = self.s.label(configuration.value)
        lookup = self.s.tags.get_tagged_semantic_versions(
            ctx.current_branch,
            ctx.configuration,
            label,
            ctx.current_commit.when,
            tagged_semantic_version_flags(configuration.value),
        )
        commits = lookup.commits()
        base_source = commits[0] if commits else None
        increment = self.s.increments.determine_incremented_field(
            ctx.current_commit, base_source, True, configuration.value, label
        )
        yield BaseVersion(
            operator=BaseVersionOperator(
                source="Fallback base version",
                base_version_source=base_source,
                increment=increment,
                force_increment=False,
                label=label,
            )
        )


class MergeMessageStrategy:
    """Ports ``MergeMessageVersionStrategy`` (at most five results)."""

    name = "MergeMessage"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``MergeMessageVersionStrategy.GetBaseVersions``."""
        for count, item in enumerate(self._internal(configuration), start=1):
            yield item
            if count >= 5:  # noqa: PLR2004 -- upstream Take(5)
                return

    def _internal(self, configuration: EffectiveBranchConfiguration) -> Iterator[BaseVersion]:
        ctx = self.s.context
        if (
            not self.s.enabled(VersionStrategy.MERGE_MESSAGE)
            or not configuration.value.track_merge_message
        ):
            return
        filters = self.s.store.filters(configuration.value.ignore)
        for commit in filters.commits(ctx.current_branch_commits(self.s.store)):
            merge = MergeMessage.try_parse(commit, ctx.configuration)
            if (
                merge is None
                or merge.version is None
                or merge.merged_branch is None
                or not is_release_branch(ctx.configuration, merge.merged_branch)
            ):
                continue
            _log.info(
                "Found commit [%s] matching merge message format: %s", commit, merge.format_name
            )
            base_source: Commit | None = commit
            if commit.is_merge:
                base_source = self.s.store.find_merge_base_commits(
                    self.s.store.commit(commit.parents[0]), self.s.store.commit(commit.parents[1])
                )
            label = self.s.label(configuration.value)
            if configuration.value.prevent_increment_of_merged_branch:
                increment = VersionField.NONE
            else:
                increment = self.s.increments.determine_incremented_field(
                    ctx.current_commit, base_source, True, configuration.value, label
                )
            yield BaseVersion.of(
                f"Merge message '{commit.message.strip()}'",
                merge.version,
                operator=BaseVersionOperator(
                    increment=increment, force_increment=False, label=label
                ),
            )


class TaggedCommitStrategy:
    """Ports ``TaggedCommitVersionStrategy``."""

    name = "TaggedCommit"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``TaggedCommitVersionStrategy.GetBaseVersions``."""
        ctx = self.s.context
        if not self.s.enabled(VersionStrategy.TAGGED_COMMIT):
            return
        lookup = self.s.tags.get_tagged_semantic_versions(
            ctx.current_branch,
            ctx.configuration,
            None,
            ctx.current_commit.when,
            tagged_semantic_version_flags(configuration.value),
        )
        tagged = list(dict.fromkeys(lookup.all_versions()))
        label = self.s.label(configuration.value)
        threshold = SemanticVersion()
        alternatives: list[SemanticVersionWithTag] = []
        for item in tagged:
            if not item.value.is_match_for_branch_specific_label(label):
                alternatives.append(item)
                continue
            alternative_max = max(alternatives).value if alternatives else None
            highest_possible = item.value.increment(
                VersionField.MAJOR, None, alternative_max, mode=IncrementMode.FORCE
            )
            if highest_possible.is_less_than(threshold, include_prerelease=False):
                _log.info(
                    "The tag '%s' is skipped because it provides a lower base version "
                    "than other tags.",
                    item.value,
                )
                alternatives.clear()
                continue
            base_source = item.commit
            increment = self.s.increments.determine_incremented_field(
                ctx.current_commit, base_source, True, configuration.value, label
            )
            threshold = item.value.increment(increment, None, mode=IncrementMode.FORCE)
            yield BaseVersion.of(
                f"Git tag '{item.tag.name.friendly}'",
                item.value,
                base_source,
                BaseVersionOperator(
                    increment=increment,
                    force_increment=False,
                    label=label,
                    alternative_semantic_version=alternative_max,
                ),
            )
            alternatives.clear()


class VersionInBranchNameStrategy:
    """Ports ``VersionInBranchNameVersionStrategy``."""

    name = "VersionInBranchName"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``VersionInBranchNameVersionStrategy.GetBaseVersions``."""
        if not self.s.enabled(VersionStrategy.VERSION_IN_BRANCH_NAME):
            return
        found = self.try_get_base_version(configuration)
        if found is not None:
            yield found

    def try_get_base_version(
        self, configuration: EffectiveBranchConfiguration
    ) -> BaseVersion | None:
        """Ports ``TryGetBaseVersion`` (also used by the release-branch tracker)."""
        ctx = self.s.context
        if not configuration.value.is_release_branch:
            return None
        for branch in (ctx.current_branch, configuration.branch):
            result = try_get_semantic_version(
                branch.name,
                configuration.value.version_in_branch_pattern,
                configuration.value.tag_prefix,
                configuration.value.semantic_version_format,
            )
            if result is None:
                continue
            override: str | None = None
            if result.name and (
                ctx.current_branch.name == branch.name
                or get_branch_configuration(ctx.configuration, ctx.current_branch.name).label
                is None
            ):
                override = result.name
            label = self.s.label(configuration.value, override)
            return BaseVersion.of(
                "Version in branch name",
                result.value,
                operator=BaseVersionOperator(
                    increment=VersionField.NONE, force_increment=False, label=label
                ),
            )
        return None


class TrackReleaseBranchesStrategy:
    """Ports ``TrackReleaseBranchesVersionStrategy``."""

    name = "TrackReleaseBranches"

    def __init__(self, services: Services) -> None:
        """Bind services."""
        self.s = services
        self._release = VersionInBranchNameStrategy(services)

    def get_base_versions(
        self, configuration: EffectiveBranchConfiguration
    ) -> Iterator[BaseVersion]:
        """See ``TrackReleaseBranchesVersionStrategy.GetBaseVersions``."""
        ctx = self.s.context
        if not self.s.enabled(VersionStrategy.TRACK_RELEASE_BRANCHES):
            return
        if not configuration.value.tracks_release_branches:
            return
        for release_branch in self.s.store.release_branches(ctx.configuration):
            found = self._try_get_base_version(release_branch, configuration)
            if found is not None:
                yield found

    def _try_get_base_version(
        self, release_branch: Branch, configuration: EffectiveBranchConfiguration
    ) -> BaseVersion | None:
        ctx = self.s.context
        release_configuration = EffectiveBranchConfiguration(
            get_effective_configuration(ctx.configuration, release_branch.name), release_branch
        )
        base = self._release.try_get_base_version(release_configuration)
        if base is None:
            return None
        base_source = self.s.store.find_merge_base(release_branch, ctx.current_branch)
        label = self.s.label(configuration.value)
        increment = self.s.increments.determine_incremented_field(
            ctx.current_commit, base_source, True, configuration.value, label
        )
        return BaseVersion.of(
            "Release branch exists -> " + base.source,
            base.semantic_version,
            base_source,
            BaseVersionOperator(increment=increment, force_increment=False, label=label),
        )


def default_strategies(services: Services) -> list[Strategy]:
    """All strategies in upstream registration order (source-file order)."""
    return [
        ConfiguredNextVersionStrategy(services),
        FallbackStrategy(services),
        MainlineStrategy(services.context, services.store, services.tags, services.increments),
        MergeMessageStrategy(services),
        TaggedCommitStrategy(services),
        TrackReleaseBranchesStrategy(services),
        VersionInBranchNameStrategy(services),
    ]
