# SPDX-License-Identifier: MIT
"""Choose the winning base version and apply the deployment mode.

Ports ``NextVersionCalculator``, ``VersionCalculatorBase`` and the three
deployment-mode calculators from 6.8.2.
"""

from __future__ import annotations

import functools
import logging

from usg_pygitversion.calculation.base_version import (
    BaseVersion,
    BaseVersionOperand,
    NextVersion,
)
from usg_pygitversion.calculation.branch_finder import EffectiveBranchConfigurationFinder
from usg_pygitversion.calculation.context import GitVersionContext
from usg_pygitversion.calculation.store import RepositoryStore
from usg_pygitversion.calculation.strategies import (
    FallbackStrategy,
    Services,
    Strategy,
    default_strategies,
    tagged_semantic_version_flags,
)
from usg_pygitversion.calculation.tagged_versions import (
    SemanticVersionWithTag,
    TaggedSemanticVersionService,
)
from usg_pygitversion.config.effective import EffectiveConfiguration, get_branch_configuration
from usg_pygitversion.config.enums import DeploymentMode, IncrementStrategy
from usg_pygitversion.errors import GitVersionError
from usg_pygitversion.git.models import Commit
from usg_pygitversion.semver import BuildMetaData, PreReleaseTag, SemanticVersion, VersionField

_log = logging.getLogger("usg_pygitversion.calculation")


def _compare_next(a: NextVersion, b: NextVersion) -> int:
    return a.compare_to(b)


class NextVersionCalculator:
    """Ports ``NextVersionCalculator.FindVersion`` and its helpers."""

    def __init__(
        self,
        context: GitVersionContext,
        store: RepositoryStore,
        tags: TaggedSemanticVersionService,
        services: Services,
        strategies: list[Strategy] | None = None,
    ) -> None:
        """Wire the collaborators."""
        self.context = context
        self.store = store
        self.tags = tags
        self.services = services
        self.strategies = strategies if strategies is not None else default_strategies(services)
        self.finder = EffectiveBranchConfigurationFinder(store)

    # -- entry point -------------------------------------------------------------

    def find_version(self) -> SemanticVersion:
        """Ports ``FindVersion``."""
        ctx = self.context
        _log.info("Running against branch: %s (%s)", ctx.current_branch, ctx.current_commit)
        branch_configuration = get_branch_configuration(ctx.configuration, ctx.current_branch.name)
        effective = EffectiveConfiguration.create(ctx.configuration, branch_configuration)
        unknown_properties = branch_configuration.increment is IncrementStrategy.INHERIT

        if (
            ctx.is_current_commit_tagged
            and not unknown_properties
            and effective.prevent_increment_when_current_commit_tagged
        ):
            found = self._try_get_tagged_version(effective)
            if found is not None:
                return found

        next_version = self._calculate_next_version()
        if (
            ctx.is_current_commit_tagged
            and unknown_properties
            and next_version.configuration.prevent_increment_when_current_commit_tagged
        ):
            found = self._try_get_tagged_version(next_version.configuration)
            if found is not None:
                return found

        version = self._apply_deployment_mode(
            next_version.configuration.mode,
            next_version.incremented_version,
            next_version.base_version,
        )

        ignore = ctx.configuration.ignore
        alternatives: list[SemanticVersionWithTag] = []
        lookup = self.tags.get_tagged_semantic_versions_of_branch(
            next_version.branch_configuration.branch,
            ctx.configuration.tag_prefix,
            ctx.configuration.semantic_version_format,
            ignore,
            not_older_than=ctx.current_commit.when,
        )
        for commit, versions in lookup:
            if commit.when > ctx.current_commit.when:
                continue
            if ignore.before is not None and commit.when <= ignore.before:
                continue
            if commit.sha in ignore.shas:
                continue
            alternatives.extend(versions)
        alternative = max(alternatives).value if alternatives else None
        if alternative is not None and version.is_less_than(alternative, include_prerelease=False):
            version = version.with_(
                major=alternative.major, minor=alternative.minor, patch=alternative.patch
            )
        return version

    # -- tagged current commit ---------------------------------------------------

    def _try_get_tagged_version(
        self, configuration: EffectiveConfiguration
    ) -> SemanticVersion | None:
        """Ports ``TryGetSemanticVersion``: reuse the tag on the current commit."""
        ctx = self.context
        lookup = self.tags.get_tagged_semantic_versions(
            ctx.current_branch,
            ctx.configuration,
            None,
            ctx.current_commit.when,
            tagged_semantic_version_flags(configuration),
        )
        label = self.services.label(configuration)
        candidates = [
            v
            for v in lookup[ctx.current_commit]
            if v.value.is_match_for_branch_specific_label(label)
        ]
        if not candidates:
            return None
        current = max(candidates)
        metadata = BuildMetaData(
            version_source_semver=current.value,
            version_source_sha=ctx.current_commit.sha,
            commits_since_tag=None,
            branch=ctx.current_branch.name.friendly,
            sha=ctx.current_commit.sha,
            short_sha=ctx.current_commit.short_sha,
            commit_date=ctx.current_commit.when,
            uncommitted_changes=ctx.uncommitted_changes,
            version_source_increment=VersionField.NONE,
        )
        prerelease = current.value.prerelease
        if configuration.mode is DeploymentMode.CONTINUOUS_DEPLOYMENT:
            prerelease = PreReleaseTag()
        return current.value.with_(prerelease=prerelease, build_metadata=metadata)

    # -- candidate selection -----------------------------------------------------

    def _calculate_next_version(self) -> NextVersion:
        """Ports ``CalculateNextVersion``."""
        candidates = self._get_next_versions()
        if not candidates:
            raise GitVersionError("No base versions determined on the current branch.")
        # LINQ Max keeps the first of equal maxima.
        max_version = candidates[0]
        for candidate in candidates[1:]:
            if candidate.compare_to(max_version) > 0:
                max_version = candidate

        matching = [
            c
            for c in candidates
            if c.base_version.base_version_source is not None
            and c.incremented_version.compare_to(max_version.incremented_version) == 0
        ]
        if len(matching) > 1:
            latest = functools.reduce(self._compare_versions, matching)
            latest_source = latest.base_version.base_version_source
            max_version = latest
            _log.info(
                "Found multiple base versions which will produce the same SemVer (%s), "
                "taking latest source for commit counting (%s)",
                max_version.incremented_version,
                latest.base_version.source,
            )
        else:
            filtered = candidates
            if not max_version.incremented_version.prerelease.has_tag():
                filtered = [
                    c for c in filtered if not c.base_version.semantic_version.prerelease.has_tag()
                ]
            with_source = [c for c in filtered if c.base_version.base_version_source is not None]
            with_source.sort(
                key=functools.cmp_to_key(self._order_by_version_then_date), reverse=True
            )
            version = with_source[0] if with_source else None
            if version is None:
                without = [c for c in filtered if c.base_version.base_version_source is None]
                without.sort(key=functools.cmp_to_key(_compare_next), reverse=True)
                version = without[0]
            latest_source = version.base_version.base_version_source

        calculated = BaseVersion(
            BaseVersionOperand(
                source=max_version.base_version.source,
                semantic_version=max_version.base_version.semantic_version,
                base_version_source=latest_source,
            )
        )
        _log.info("Base version used: %s", calculated)
        return NextVersion(
            max_version.incremented_version, calculated, max_version.branch_configuration
        )

    @staticmethod
    def _order_by_version_then_date(a: NextVersion, b: NextVersion) -> int:
        cmp = a.compare_to(b)
        if cmp != 0:
            return cmp
        a_when = (
            a.base_version.base_version_source.when if a.base_version.base_version_source else None
        )
        b_when = (
            b.base_version.base_version_source.when if b.base_version.base_version_source else None
        )
        if a_when == b_when:
            return 0
        if a_when is None:
            return -1
        if b_when is None:
            return 1
        return (a_when > b_when) - (a_when < b_when)

    @staticmethod
    def _compare_versions(a: NextVersion, b: NextVersion) -> NextVersion:
        """Ports ``CompareVersions``: the candidate with the later source commit."""
        if a.base_version.base_version_source is None:
            return b
        if b.base_version.base_version_source is None:
            return a
        return (
            a
            if a.base_version.base_version_source.when >= b.base_version.base_version_source.when
            else b
        )

    def _get_next_versions(self) -> list[NextVersion]:
        """Ports the nested ``GetNextVersions`` methods."""
        ctx = self.context
        results: list[NextVersion] = []
        ordered = [s for s in self.strategies if not isinstance(s, FallbackStrategy)]
        ordered += [s for s in self.strategies if isinstance(s, FallbackStrategy)]
        for branch_configuration in self.finder.get_configurations(
            ctx.current_branch, ctx.configuration
        ):
            at_least_one = False
            for strategy in ordered:
                if at_least_one and isinstance(strategy, FallbackStrategy):
                    continue
                for base_version in strategy.get_base_versions(branch_configuration):
                    _log.info("%s", base_version)
                    if not self._include_version(base_version):
                        continue
                    at_least_one = True
                    results.append(
                        NextVersion(
                            base_version.get_incremented_version(),
                            base_version,
                            branch_configuration,
                        )
                    )
        return results

    def _include_version(self, base_version: BaseVersion) -> bool:
        """Ports ``IncludeVersion``: apply the ignore filters to the base version source."""
        reason = self.store.filters(self.context.configuration.ignore).exclude_reason(
            base_version.base_version_source
        )
        if reason is not None:
            _log.info("%s", reason)
            return False
        return True

    # -- deployment modes --------------------------------------------------------

    def _build_metadata(self, base_version: BaseVersion) -> BuildMetaData:
        """Ports ``VersionCalculatorBase.CreateVersionBuildMetaData``."""
        ctx = self.context
        commit_log = self.store.get_commit_log(
            base_version.base_version_source, ctx.current_commit, ctx.configuration.ignore
        )
        commits_since_tag = len(commit_log)
        _log.info(
            "%d commits found between %s and %s",
            commits_since_tag,
            base_version.base_version_source,
            ctx.current_commit,
        )
        source: Commit | None = base_version.base_version_source
        return BuildMetaData(
            version_source_semver=base_version.semantic_version,
            version_source_sha=source.sha if source else None,
            commits_since_tag=commits_since_tag,
            branch=ctx.current_branch.name.friendly,
            sha=ctx.current_commit.sha,
            short_sha=ctx.current_commit.short_sha,
            commit_date=ctx.current_commit.when,
            uncommitted_changes=ctx.uncommitted_changes,
            version_source_increment=base_version.increment,
            version_source_distance=commits_since_tag,
        )

    def _apply_deployment_mode(
        self, mode: DeploymentMode, version: SemanticVersion, base_version: BaseVersion
    ) -> SemanticVersion:
        """Ports the three ``IDeploymentModeCalculator`` implementations."""
        metadata = self._build_metadata(base_version)
        if mode is DeploymentMode.MANUAL_DEPLOYMENT:
            return version.with_(build_metadata=metadata)
        if mode is DeploymentMode.CONTINUOUS_DELIVERY:
            tag = version.prerelease
            if not tag.has_tag() or tag.number is None:
                raise GitVersionError("Continuous delivery requires a pre-release tag.")
            count = metadata.commits_since_tag or 0
            return version.with_(
                prerelease=PreReleaseTag(
                    tag.name, tag.number + count - 1, tag.promote_tag_even_if_name_is_empty
                ),
                build_metadata=metadata.with_(
                    version_source_distance=count, commits_since_tag=None
                ),
            )
        count = metadata.commits_since_tag or 0
        return version.with_(
            prerelease=PreReleaseTag(),
            build_metadata=metadata.with_(version_source_distance=count, commits_since_tag=None),
        )
