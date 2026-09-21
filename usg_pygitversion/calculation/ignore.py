# SPDX-License-Identifier: MIT
"""``ignore`` configuration applied to commits, tags and base versions.

Ports ``ShaVersionFilter``, ``MinDateVersionFilter``, ``PathFilter`` and the
``IIgnoreConfiguration`` extension methods ``ToFilters`` / ``Filter``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from usg_pygitversion.config.schema import IgnoreConfiguration
from usg_pygitversion.dotnet import regex as dotnet_regex
from usg_pygitversion.git.models import Commit, Tag

if TYPE_CHECKING:
    from usg_pygitversion.calculation.store import RepositoryStore


class VersionFilter:
    """One exclusion rule. ``exclude`` returns a reason string or ``None``."""

    def exclude(self, commit: Commit | None) -> str | None:
        """Return a reason when ``commit`` must be excluded."""
        raise NotImplementedError


class ShaFilter(VersionFilter):
    """Ports ``ShaVersionFilter``: exclude commits whose SHA starts with a listed prefix."""

    def __init__(self, shas: Iterable[str]) -> None:
        """Store the prefixes lower-cased for ordinal-ignore-case matching."""
        self._shas = tuple(s.lower() for s in shas)

    def exclude(self, commit: Commit | None) -> str | None:
        """See :class:`VersionFilter`."""
        if commit is None or not any(commit.sha.lower().startswith(s) for s in self._shas):
            return None
        return f"Sha {commit} was ignored due to commit having been excluded by configuration"


class MinDateFilter(VersionFilter):
    """Ports ``MinDateVersionFilter``: exclude commits before ``commits-before``."""

    def __init__(self, minimum: object) -> None:
        """Keep the cut-off datetime."""
        self._minimum = minimum

    def exclude(self, commit: Commit | None) -> str | None:
        """See :class:`VersionFilter`."""
        if commit is None or commit.when >= self._minimum:  # type: ignore[operator]
            return None
        return "Source was ignored due to commit date being outside of configured range"


class PathFilter(VersionFilter):
    """Ports ``PathFilter`` (inclusive mode): exclude when *all* changed paths match."""

    def __init__(
        self, patterns: Iterable[str], changed_paths: Callable[[str], tuple[str, ...]]
    ) -> None:
        """Compile patterns through the .NET shim; ``changed_paths`` resolves a SHA's diff."""
        self._patterns = [dotnet_regex.compile(p) for p in patterns]
        self._changed_paths = changed_paths
        self._cache: dict[str, bool] = {}

    def _is_match(self, path: str) -> bool:
        hit = self._cache.get(path)
        if hit is None:
            hit = any(p.search(dotnet_regex.bounded(path)) for p in self._patterns)
            self._cache[path] = hit
        return hit

    def exclude(self, commit: Commit | None) -> str | None:
        """See :class:`VersionFilter`."""
        if commit is None:
            return None
        paths = self._changed_paths(commit.sha)
        # Upstream uses LINQ All, which is true for an empty sequence, so an
        # empty commit is excluded when paths are configured.
        if all(self._is_match(p) for p in paths):
            return "Source was ignored due to all commit paths matching ignore regex"
        return None


class IgnoreFilters:
    """The filters implied by an :class:`IgnoreConfiguration`. Ports ``ToFilters``/``Filter``."""

    def __init__(self, ignore: IgnoreConfiguration, store: RepositoryStore) -> None:
        """Build filters in upstream order: sha, date, paths."""
        self.ignore = ignore
        self.filters: list[VersionFilter] = []
        if ignore.shas:
            self.filters.append(ShaFilter(ignore.shas))
        if ignore.before is not None:
            self.filters.append(MinDateFilter(ignore.before))
        if ignore.paths:
            self.filters.append(PathFilter(ignore.paths, store.changed_paths))

    @property
    def is_empty(self) -> bool:
        """True when nothing is configured (filtering is skipped)."""
        return self.ignore.is_empty

    def exclude_reason(self, commit: Commit | None) -> str | None:
        """First filter reason that excludes ``commit``, else ``None``."""
        for f in self.filters:
            reason = f.exclude(commit)
            if reason is not None:
                return reason
        return None

    def commits(self, commits: Iterable[Commit]) -> list[Commit]:
        """Ports ``Filter(ICommit[])``."""
        items = list(commits)
        if self.is_empty:
            return items
        return [c for c in items if self.exclude_reason(c) is None]

    def tags(self, tags: Iterable[Tag], commit_of: Callable[[Tag], Commit | None]) -> list[Tag]:
        """Ports ``Filter(ITag[])``: a tag is kept when its peeled commit is kept."""
        items = list(tags)
        if self.is_empty:
            return items
        return [t for t in items if self.exclude_reason(commit_of(t)) is None]
