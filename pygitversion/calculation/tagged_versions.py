# SPDX-License-Identifier: MIT
"""Tags parsed as semantic versions, grouped by commit.

Ports ``TaggedSemanticVersionRepository``, ``TaggedSemanticVersionService``,
``TaggedSemanticVersions`` and ``SemanticVersionWithTag`` from 6.8.2. The
C# ``ILookup<ICommit, SemanticVersionWithTag>`` is modelled by
:class:`CommitLookup`: an ordered mapping (commit date descending) from
commit to the versions tagged on it.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import Flag

from pygitversion.calculation.store import RepositoryStore
from pygitversion.config.schema import GitVersionConfiguration, IgnoreConfiguration
from pygitversion.git.models import Branch, Commit, Tag
from pygitversion.semver import SemanticVersion, SemanticVersionFormat

_log = logging.getLogger("pygitversion.calculation")


class TaggedSemanticVersions(Flag):
    """Which tag sets to consider. Ports the ``TaggedSemanticVersions`` flags."""

    NONE = 0
    OF_BRANCH = 1
    OF_MERGE_TARGETS = 2
    OF_MAIN_BRANCHES = 4
    OF_RELEASE_BRANCHES = 8


@functools.total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class SemanticVersionWithTag:
    """A parsed tag. Ports ``SemanticVersionWithTag``; ordered by version."""

    value: SemanticVersion
    tag: Tag
    commit: Commit

    def __eq__(self, other: object) -> bool:
        """Records compare all members; the tag name identifies it."""
        if not isinstance(other, SemanticVersionWithTag):
            return NotImplemented
        return self.value == other.value and self.tag == other.tag

    def __hash__(self) -> int:
        """Hash the version and tag name."""
        return hash((self.value, self.tag))

    def __lt__(self, other: SemanticVersionWithTag) -> bool:
        """Order by semantic version (``CompareTo(other.Value)``)."""
        return self.value.compare_to(other.value) < 0


class CommitLookup:
    """Ordered ``commit -> [SemanticVersionWithTag]`` mapping, newest commit first."""

    def __init__(self, pairs: Iterable[tuple[Commit, SemanticVersionWithTag]]) -> None:
        """Group distinct pairs by commit, preserving first-seen order."""
        self._groups: dict[str, tuple[Commit, list[SemanticVersionWithTag]]] = {}
        seen: set[tuple[str, str]] = set()
        for commit, item in pairs:
            key = (commit.sha, item.tag.name.canonical)
            if key in seen:
                continue
            seen.add(key)
            self._groups.setdefault(commit.sha, (commit, []))[1].append(item)

    @classmethod
    def sorted_by_commit_date(
        cls, pairs: Iterable[tuple[Commit, SemanticVersionWithTag]]
    ) -> CommitLookup:
        """Build with groups ordered by commit date descending (``OrderByDescending(When)``)."""
        items = list(pairs)
        items.sort(key=lambda p: p[0].when, reverse=True)
        return cls(items)

    def __getitem__(self, commit: Commit) -> list[SemanticVersionWithTag]:
        """Versions on ``commit`` (empty list when none), like ``ILookup`` indexing."""
        group = self._groups.get(commit.sha)
        return list(group[1]) if group else []

    def __contains__(self, commit: object) -> bool:
        """``lookup.Contains(commit)``."""
        return isinstance(commit, Commit) and commit.sha in self._groups

    def __iter__(self) -> Iterator[tuple[Commit, list[SemanticVersionWithTag]]]:
        """Iterate groups in order."""
        for commit, items in self._groups.values():
            yield commit, list(items)

    def __len__(self) -> int:
        """Number of commits."""
        return len(self._groups)

    def all_versions(self) -> list[SemanticVersionWithTag]:
        """``SelectMany`` over the groups."""
        return [item for _, items in self._groups.values() for item in items]

    def commits(self) -> list[Commit]:
        """The commits in order."""
        return [commit for commit, _ in self._groups.values()]


class TaggedSemanticVersionRepository:
    """Ports ``TaggedSemanticVersionRepository`` with its three caches."""

    def __init__(self, store: RepositoryStore) -> None:
        """Bind to a store."""
        self.store = store
        self._all_cache: dict[tuple[str, SemanticVersionFormat], list[SemanticVersionWithTag]] = {}
        self._branch_cache: dict[
            tuple[str, str, SemanticVersionFormat], list[SemanticVersionWithTag]
        ] = {}
        self._merge_target_cache: dict[
            tuple[str, str, SemanticVersionFormat], list[tuple[Commit, SemanticVersionWithTag]]
        ] = {}

    def all(
        self, tag_prefix: str | None, fmt: SemanticVersionFormat, ignore: IgnoreConfiguration
    ) -> CommitLookup:
        """Every tag that parses as a version. Ports ``GetTaggedSemanticVersions``."""
        prefix = tag_prefix or ""
        key = (prefix, fmt)
        items = self._all_cache.get(key)
        if items is None:
            _log.info("Getting tagged semantic versions. TagPrefix: %s and Format: %s", prefix, fmt)
            found: list[SemanticVersionWithTag] = []
            filters = self.store.filters(ignore)
            for tag in filters.tags(self.store.tags, self.store.tag_commit):
                version = SemanticVersion.try_parse(tag.name.friendly, prefix, fmt)
                commit = self.store.tag_commit(tag)
                if version is not None and commit is not None:
                    found.append(SemanticVersionWithTag(version, tag, commit))
            found.sort(key=lambda v: v.commit.when, reverse=True)
            items = found
            self._all_cache[key] = items
        return CommitLookup((v.commit, v) for v in items)

    def of_branch(
        self,
        branch: Branch,
        tag_prefix: str | None,
        fmt: SemanticVersionFormat,
        ignore: IgnoreConfiguration,
    ) -> CommitLookup:
        """Tags on commits reachable from ``branch``. Ports ``..OfBranch``."""
        prefix = tag_prefix or ""
        key = (branch.name.canonical + "|" + branch.tip, prefix, fmt)
        items = self._branch_cache.get(key)
        if items is None:
            versions = self.all(prefix, fmt, ignore)
            found: list[SemanticVersionWithTag] = []
            for commit in self.store.filters(ignore).commits(self.store.branch_commits(branch)):
                found.extend(versions[commit])
            found = list(dict.fromkeys(found))
            found.sort(key=lambda v: v.commit.when, reverse=True)
            items = found
            self._branch_cache[key] = items
        return CommitLookup((v.commit, v) for v in items)

    def of_merge_target(
        self,
        branch: Branch,
        tag_prefix: str | None,
        fmt: SemanticVersionFormat,
        ignore: IgnoreConfiguration,
    ) -> CommitLookup:
        """Tags on merge commits with a parent on ``branch``. Ports ``..OfMergeTarget``."""
        prefix = tag_prefix or ""
        key = (branch.name.canonical + "|" + branch.tip, prefix, fmt)
        items = self._merge_target_cache.get(key)
        if items is None:
            shas = {
                c.sha for c in self.store.filters(ignore).commits(self.store.branch_commits(branch))
            }
            found: list[tuple[Commit, SemanticVersionWithTag]] = []
            for version in self.all(prefix, fmt, ignore).all_versions():
                found.extend(
                    (self.store.commit(parent_sha), version)
                    for parent_sha in version.commit.parents
                    if parent_sha in shas
                )
            found = list(dict.fromkeys(found))
            found.sort(key=lambda p: p[0].when, reverse=True)
            items = found
            self._merge_target_cache[key] = items
        return CommitLookup(items)


class TaggedSemanticVersionService:
    """Ports ``TaggedSemanticVersionService``: combines the tag sets with label and date filters."""

    def __init__(self, repository: TaggedSemanticVersionRepository) -> None:
        """Bind to the tag repository."""
        self.repository = repository
        self.store = repository.store

    def get_tagged_semantic_versions(
        self,
        branch: Branch,
        configuration: GitVersionConfiguration,
        label: str | None,
        not_older_than: datetime | None,
        flags: TaggedSemanticVersions,
    ) -> CommitLookup:
        """Ports ``GetTaggedSemanticVersions``."""
        pairs: list[tuple[Commit, SemanticVersionWithTag]] = []
        prefix, fmt, ignore = (
            configuration.tag_prefix,
            configuration.semantic_version_format,
            configuration.ignore,
        )
        if flags & TaggedSemanticVersions.OF_BRANCH:
            pairs.extend(self._of_branch(branch, prefix, fmt, ignore, label, not_older_than))
        if flags & TaggedSemanticVersions.OF_MERGE_TARGETS:
            pairs.extend(self._of_merge_target(branch, prefix, fmt, ignore, label, not_older_than))
        if flags & TaggedSemanticVersions.OF_MAIN_BRANCHES:
            for main in self.store.main_branches(configuration, [branch]):
                pairs.extend(self._of_branch(main, prefix, fmt, ignore, label, None))
        if flags & TaggedSemanticVersions.OF_RELEASE_BRANCHES:
            for release in self.store.release_branches(configuration, [branch]):
                pairs.extend(self._of_branch(release, prefix, fmt, ignore, label, None))
        return CommitLookup.sorted_by_commit_date(dict.fromkeys(pairs))

    def get_tagged_semantic_versions_of_branch(
        self,
        branch: Branch,
        tag_prefix: str | None,
        fmt: SemanticVersionFormat,
        ignore: IgnoreConfiguration,
        label: str | None = None,
        not_older_than: datetime | None = None,
    ) -> CommitLookup:
        """Ports ``GetTaggedSemanticVersionsOfBranch``."""
        pairs = self._of_branch(branch, tag_prefix, fmt, ignore, label, not_older_than)
        return CommitLookup.sorted_by_commit_date(dict.fromkeys(pairs))

    def _of_branch(
        self,
        branch: Branch,
        tag_prefix: str | None,
        fmt: SemanticVersionFormat,
        ignore: IgnoreConfiguration,
        label: str | None,
        not_older_than: datetime | None,
    ) -> list[tuple[Commit, SemanticVersionWithTag]]:
        out: list[tuple[Commit, SemanticVersionWithTag]] = []
        for commit, versions in self.repository.of_branch(branch, tag_prefix, fmt, ignore):
            if not_older_than is not None and commit.when > not_older_than:
                continue
            out.extend(
                (commit, v) for v in versions if v.value.is_match_for_branch_specific_label(label)
            )
        return out

    def _of_merge_target(
        self,
        branch: Branch,
        tag_prefix: str | None,
        fmt: SemanticVersionFormat,
        ignore: IgnoreConfiguration,
        label: str | None,
        not_older_than: datetime | None,
    ) -> list[tuple[Commit, SemanticVersionWithTag]]:
        out: list[tuple[Commit, SemanticVersionWithTag]] = []
        for commit, versions in self.repository.of_merge_target(branch, tag_prefix, fmt, ignore):
            if not_older_than is not None and commit.when > not_older_than:
                continue
            out.extend(
                (commit, v) for v in versions if v.value.is_match_for_branch_specific_label(label)
            )
        return out
