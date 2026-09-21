# SPDX-License-Identifier: MIT
"""Decide which version field to bump. Ports ``IncrementStrategyFinder`` (6.8.2)."""

from __future__ import annotations

import re

from pygitversion.calculation.store import RepositoryStore
from pygitversion.calculation.tagged_versions import TaggedSemanticVersionRepository
from pygitversion.config.effective import EffectiveConfiguration
from pygitversion.config.enums import CommitMessageIncrementMode, IncrementStrategy
from pygitversion.dotnet import regex as dotnet_regex
from pygitversion.errors import ConfigurationError
from pygitversion.git.models import Commit
from pygitversion.semver import VersionField

DEFAULT_MAJOR = r"\+semver:\s?(breaking|major)"
DEFAULT_MINOR = r"\+semver:\s?(feature|minor)"
DEFAULT_PATCH = r"\+semver:\s?(fix|patch)"
DEFAULT_NO_BUMP = r"\+semver:\s?(none|skip)"


def increment_strategy_to_field(strategy: IncrementStrategy) -> VersionField:
    """Ports ``IncrementStrategy.ToVersionField``; ``Inherit`` is an error here."""
    mapping = {
        IncrementStrategy.NONE: VersionField.NONE,
        IncrementStrategy.MAJOR: VersionField.MAJOR,
        IncrementStrategy.MINOR: VersionField.MINOR,
        IncrementStrategy.PATCH: VersionField.PATCH,
    }
    try:
        return mapping[strategy]
    except KeyError:
        msg = f"increment strategy {strategy.value!r} cannot be converted to a version field"
        raise ConfigurationError(msg) from None


class IncrementStrategyFinder:
    """Combines the branch's configured increment with ``+semver:`` commit messages."""

    def __init__(self, store: RepositoryStore, tags: TaggedSemanticVersionRepository) -> None:
        """Bind to the store and tag repository."""
        self.store = store
        self.tags = tags
        self._commit_increment_cache: dict[str, VersionField | None] = {}

    def determine_incremented_field(
        self,
        current_commit: Commit,
        base_version_source: Commit | None,
        should_increment: bool,
        configuration: EffectiveConfiguration,
        label: str | None,
    ) -> VersionField:
        """Ports ``DetermineIncrementedField``."""
        from_messages = self._find_commit_message_increment(
            configuration, base_version_source, current_commit, label
        )
        default = increment_strategy_to_field(configuration.increment)
        if from_messages is None:
            return default if should_increment else VersionField.NONE
        if should_increment and from_messages < default:
            return default
        return from_messages

    def get_increment_forced_by_commit(
        self, commit: Commit, configuration: EffectiveConfiguration
    ) -> VersionField:
        """Ports ``GetIncrementForcedByCommit``."""
        return (
            self._increment_from_commit(commit, *self._regexes(configuration)) or VersionField.NONE
        )

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _regexes(configuration: EffectiveConfiguration) -> tuple[re.Pattern[str], ...]:
        return (
            dotnet_regex.compile(configuration.major_version_bump_message or DEFAULT_MAJOR),
            dotnet_regex.compile(configuration.minor_version_bump_message or DEFAULT_MINOR),
            dotnet_regex.compile(configuration.patch_version_bump_message or DEFAULT_PATCH),
            dotnet_regex.compile(configuration.no_bump_message or DEFAULT_NO_BUMP),
        )

    def _find_commit_message_increment(
        self,
        configuration: EffectiveConfiguration,
        base_version_source: Commit | None,
        current_commit: Commit,
        label: str | None,
    ) -> VersionField | None:
        if configuration.commit_message_incrementing is CommitMessageIncrementMode.DISABLED:
            return None
        commits = self._commit_history(configuration, base_version_source, current_commit, label)
        if (
            configuration.commit_message_incrementing
            is CommitMessageIncrementMode.MERGE_MESSAGE_ONLY
        ):
            commits = [c for c in commits if len(c.parents) > 1]
        regexes = self._regexes(configuration)
        increments = [
            i for i in (self._increment_from_commit(c, *regexes) for c in commits) if i is not None
        ]
        return max(increments) if increments else None

    def _commit_history(
        self,
        configuration: EffectiveConfiguration,
        base_version_source: Commit | None,
        current_commit: Commit,
        label: str | None,
    ) -> list[Commit]:
        """Ports ``GetCommitHistory``: the commit log minus anything at or below a matching tag."""
        intermediate = self.store.get_commit_log(
            base_version_source, current_commit, configuration.ignore
        )
        log: dict[str, Commit] = {c.sha: c for c in intermediate}
        target_shas: set[str] | None = None
        for commit in reversed(intermediate):
            if target_shas is None:
                target_shas = {
                    v.tag.target
                    for v in self.tags.all(
                        configuration.tag_prefix,
                        configuration.semantic_version_format,
                        configuration.ignore,
                    ).all_versions()
                    if v.value.is_match_for_branch_specific_label(label)
                }
            if commit.sha not in target_shas or log.pop(commit.sha, None) is None:
                continue
            parents = list(commit.parents)
            while parents:
                next_parents: list[str] = []
                for sha in parents:
                    removed = log.pop(sha, None)
                    if removed is not None:
                        next_parents.extend(removed.parents)
                parents = next_parents
        return list(log.values())

    def _increment_from_commit(
        self,
        commit: Commit,
        major: re.Pattern[str],
        minor: re.Pattern[str],
        patch: re.Pattern[str],
        no_bump: re.Pattern[str],
    ) -> VersionField | None:
        if commit.sha in self._commit_increment_cache:
            return self._commit_increment_cache[commit.sha]
        message = dotnet_regex.bounded(commit.message)
        result: VersionField | None
        if no_bump.search(message):
            result = VersionField.NONE
        elif major.search(message):
            result = VersionField.MAJOR
        elif minor.search(message):
            result = VersionField.MINOR
        elif patch.search(message):
            result = VersionField.PATCH
        else:
            result = None
        self._commit_increment_cache[commit.sha] = result
        return result
