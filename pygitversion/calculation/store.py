# SPDX-License-Identifier: MIT
"""Repository queries the calculator needs, with caching.

Ports ``RepositoryStore``, ``MergeBaseFinder``, ``MergeCommitFinder``,
``SourceBranchFinder``, ``BranchesContainingCommitFinder`` and
``BranchRepository`` from 6.8.2.

Memory (PLAN.md 9.4): per-branch commit lists are loaded once and bounded by
the repository's ``max_commits``; everything else is a small cache keyed by
SHA or canonical name and lives only for one calculation run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import cached_property

from pygitversion.calculation.ignore import IgnoreFilters
from pygitversion.config.effective import get_branch_configuration
from pygitversion.config.schema import (
    BranchConfiguration,
    GitVersionConfiguration,
    IgnoreConfiguration,
)
from pygitversion.dotnet import regex as dotnet_regex
from pygitversion.errors import RepositoryError
from pygitversion.git.models import DETACHED_HEAD_CANONICAL, Branch, Commit, Tag
from pygitversion.git.refname import ReferenceName
from pygitversion.git.repository import GitRepository

_log = logging.getLogger("pygitversion.calculation")


class BranchCommit:
    """A (branch, commit) pair. Ports the ``BranchCommit`` struct."""

    __slots__ = ("branch", "commit")

    def __init__(self, commit: Commit, branch: Branch) -> None:
        """Bind the pair."""
        self.commit = commit
        self.branch = branch

    def __eq__(self, other: object) -> bool:
        """Equal when both members are equal."""
        return (
            isinstance(other, BranchCommit)
            and self.branch == other.branch
            and self.commit == other.commit
        )

    def __hash__(self) -> int:
        """Hash both members."""
        return hash((self.branch, self.commit))

    def __repr__(self) -> str:
        """Debug form."""
        return f"BranchCommit({self.branch} {self.commit})"


class RepositoryStore:
    """Cached, calculation-oriented view of a :class:`GitRepository`."""

    def __init__(self, repository: GitRepository) -> None:
        """Wrap ``repository``; nothing is read until asked for."""
        self.repository = repository
        self._branch_commits: dict[str, list[Commit]] = {}
        self._merge_base_cache: dict[tuple[str, str], Commit | None] = {}
        self._merge_commits_cache: dict[str, list[BranchCommit]] = {}
        self._changed_paths_cache: dict[str, tuple[str, ...]] = {}

    # -- basics ----------------------------------------------------------------

    @cached_property
    def head(self) -> Branch:
        """``HEAD`` as a branch (detached sentinel when applicable)."""
        return self.repository.head()

    @cached_property
    def branches(self) -> tuple[Branch, ...]:
        """All local and remote branches."""
        return self.repository.branches

    @cached_property
    def tags(self) -> tuple[Tag, ...]:
        """All tags."""
        return self.repository.tags

    @cached_property
    def uncommitted_changes(self) -> int:
        """Working-tree change count."""
        return self.repository.uncommitted_changes()

    def commit(self, sha: str) -> Commit:
        """Load a commit by SHA (cached in the repository)."""
        return self.repository.commit(sha)

    def tag_commit(self, tag: Tag) -> Commit | None:
        """The commit a tag points at, or ``None`` if it targets a non-commit."""
        try:
            return self.commit(tag.target)
        except RepositoryError:
            return None

    def changed_paths(self, sha: str) -> tuple[str, ...]:
        """Paths changed by a commit (cached). Ports ``ICommit.DiffPaths``."""
        paths = self._changed_paths_cache.get(sha)
        if paths is None:
            paths = self.repository.changed_paths(sha)
            self._changed_paths_cache[sha] = paths
        return paths

    def filters(self, ignore: IgnoreConfiguration) -> IgnoreFilters:
        """Build the ignore filters bound to this store."""
        return IgnoreFilters(ignore, self)

    # -- commit lists ----------------------------------------------------------

    def branch_commits(self, branch: Branch) -> list[Commit]:
        """Commits reachable from the branch tip, newest first (``Branch.Commits``)."""
        key = branch.name.canonical if not branch.is_detached_head else f"detached:{branch.tip}"
        cached = self._branch_commits.get(key)
        if cached is None:
            cached = list(self.repository.walk(branch.tip))
            self._branch_commits[key] = cached
        return cached

    @staticmethod
    def commits_prior_to(commits: Iterable[Commit], when: datetime) -> list[Commit]:
        """Ports ``GetCommitsPriorTo``: skip while ``When > olderThan``."""
        items = list(commits)
        idx = 0
        while idx < len(items) and items[idx].when > when:
            idx += 1
        return items[idx:]

    def get_commit_log(
        self,
        base_version_source: Commit | None,
        current_commit: Commit,
        ignore: IgnoreConfiguration,
    ) -> list[Commit]:
        """Commits between the source and the current commit. Ports ``GetCommitLog``."""
        exclude = [base_version_source.sha] if base_version_source is not None else []
        commits = list(self.repository.walk(current_commit.sha, exclude, order="date"))
        return self.filters(ignore).commits(commits)

    def commits_reachable_from_head(
        self, head: Commit | None, ignore: IgnoreConfiguration
    ) -> list[Commit]:
        """Ports ``GetCommitsReacheableFromHead`` (topological, oldest first)."""
        if head is None:
            return []
        commits = list(self.repository.walk(head.sha, order="topo-reverse"))
        return self.filters(ignore).commits(commits)

    def is_reachable_from(self, commit: Commit, branch: Branch) -> bool:
        """Ports ``GetCommitsReacheableFrom(commit, branch).Any()``."""
        return self.repository.is_ancestor(commit.sha, branch.tip)

    # -- merge bases -----------------------------------------------------------

    def find_merge_base_commits(self, a: Commit, b: Commit) -> Commit | None:
        """``git merge-base`` of two commits. Ports ``IGitRepository.FindMergeBase``."""
        key = (a.sha, b.sha)
        if key in self._merge_base_cache:
            return self._merge_base_cache[key]
        sha = self.repository.merge_base(a.sha, b.sha)
        result = self.commit(sha) if sha else None
        self._merge_base_cache[key] = result
        return result

    def get_forward_merge(self, commit: Commit | None, merge_base: Commit | None) -> Commit | None:
        """Ports ``GetForwardMerge``.

        The first commit reachable from ``commit`` but not from the base whose
        parents include the base.
        """
        if commit is None or merge_base is None:
            return None
        for candidate in self.repository.walk(commit.sha, [merge_base.sha]):
            if merge_base.sha in candidate.parents:
                return candidate
        return None

    def find_merge_base(self, first: Branch, second: Branch) -> Commit | None:
        """Ports ``MergeBaseFinder.FindMergeBaseOf`` including the forward-merge walk."""
        key = (first.name.canonical + "|" + first.tip, second.name.canonical + "|" + second.tip)
        if key in self._merge_base_cache:
            return self._merge_base_cache[key]
        commit = self.commit(first.tip)
        commit_to_find = self.commit(second.tip)
        if commit.sha in commit_to_find.parents:
            commit_to_find = self.commit(commit_to_find.parents[0])
        result = self._find_merge_base_with_forward_merges(commit, commit_to_find)
        if result is None:
            _log.info("No merge base of '%s' and '%s' could be found.", first, second)
        else:
            _log.info("Merge base of '%s' and '%s' is '%s'", first, second, result)
        self._merge_base_cache[key] = result
        return result

    def _find_merge_base_with_forward_merges(
        self, commit: Commit, commit_to_find: Commit
    ) -> Commit | None:
        merge_base = self.find_merge_base_commits(commit, commit_to_find)
        if merge_base is None:
            return None
        while True:
            forward = self.get_forward_merge(commit_to_find, merge_base)
            if forward is None:
                break
            second = self.commit(forward.parents[0])
            new_base = self.find_merge_base_commits(commit, second)
            if new_base is None:
                _log.warning("Could not find merge base for %s", commit)
            if new_base == merge_base:
                break
            merge_base = new_base
            commit_to_find = second
            if merge_base is None:
                break
        return merge_base

    # -- branches --------------------------------------------------------------

    def find_branch(self, name: ReferenceName) -> Branch | None:
        """Exact canonical-name lookup."""
        return next((b for b in self.branches if b.name == name), None)

    def get_target_branch(self, target_branch_name: str | None) -> Branch:
        """Ports ``GetTargetBranch``: prefer HEAD, else a local branch matching the name."""
        desired = self.head
        if not target_branch_name:
            return desired
        exact = next((b for b in self.branches if b.name.equivalent_to(target_branch_name)), None)
        if exact is not None and exact == desired:
            return desired
        candidates = [b for b in self.branches if b.name.equivalent_to(target_branch_name)]
        if not candidates:
            return desired
        # MinBy(IsRemote): the first local candidate, else the first remote one.
        return min(candidates, key=lambda b: b.is_remote)

    def get_current_commit(
        self, branch: Branch, commit_id: str | None, ignore: IgnoreConfiguration
    ) -> Commit | None:
        """Ports ``GetCurrentCommit``: newest non-ignored commit at or before ``commit_id``."""
        current: Commit | None = None
        if commit_id and commit_id.strip():
            _log.info("Searching for specific commit '%s'", commit_id)
            try:
                current = self.commit(commit_id)
            except RepositoryError:
                _log.warning("Commit '%s' specified but not found", commit_id)
        commits = self.branch_commits(branch)
        if current is not None:
            commits = self.commits_prior_to(commits, current.when)
        else:
            _log.info("Using latest commit on specified branch")
        filtered = self.filters(ignore).commits(commits)
        return filtered[0] if filtered else None

    def excluding_branches(self, excluded: Iterable[Branch]) -> list[Branch]:
        """All branches except ``excluded``."""
        skip = set(excluded)
        return [b for b in self.branches if b not in skip]

    def get_branches_containing_commit(
        self, commit: Commit, branches: Iterable[Branch] | None = None, only_tracked: bool = False
    ) -> list[Branch]:
        """Ports ``BranchesContainingCommitFinder``."""
        candidates = list(branches) if branches is not None else list(self.branches)

        def include_tracked(branch: Branch) -> bool:
            return (only_tracked and branch.is_tracking) or not only_tracked

        direct = [b for b in candidates if b.tip == commit.sha and not include_tracked(b)]
        if direct:
            for b in direct:
                _log.info("Direct branch found: '%s'.", b)
            return direct
        result: list[Branch] = []
        for b in candidates:
            if not include_tracked(b):
                continue
            if self.is_reachable_from(commit, b):
                result.append(b)
        return result

    # -- source branches -------------------------------------------------------

    def _source_branch_regexes(
        self, branch: Branch, configuration: GitVersionConfiguration
    ) -> list[object]:
        """Ports ``SourceBranchPredicate.GetSourceBranchRegexes``."""
        current: BranchConfiguration = get_branch_configuration(configuration, branch.name)
        regexes: list[object] = []
        for source in current.source_branches:
            regex = configuration.branches[source].regex
            if regex is not None:
                regexes.append(dotnet_regex.compile(regex))
        return regexes

    def find_source_branches_of(
        self, branch: Branch, configuration: GitVersionConfiguration, candidates: Iterable[Branch]
    ) -> list[Branch]:
        """Ports ``SourceBranchFinder.FindSourceBranchesOf``."""
        regexes = self._source_branch_regexes(branch, configuration)
        result: list[Branch] = []
        for candidate in candidates:
            if candidate == branch:
                continue
            name = dotnet_regex.bounded(candidate.name.without_origin)
            if any(r.search(name) for r in regexes):  # type: ignore[attr-defined]
                result.append(candidate)
        return result

    def find_merge_commits_for(
        self, branch: Branch, configuration: GitVersionConfiguration, excluded: Iterable[Branch]
    ) -> list[BranchCommit]:
        """Ports ``MergeCommitFinder.FindMergeCommitsFor``."""
        excluded_list = list(excluded)
        key = branch.name.canonical + "|" + ",".join(b.name.canonical for b in excluded_list)
        cached = self._merge_commits_cache.get(key)
        if cached is None:
            candidates = self.excluding_branches(excluded_list)
            found: list[BranchCommit] = []
            for source in self.find_source_branches_of(branch, configuration, candidates):
                merge_base = self.find_merge_base(branch, source)
                if merge_base is not None:
                    found.append(BranchCommit(merge_base, source))
            # OrderByDescending(When) is stable: equal timestamps keep branch order.
            found.sort(key=lambda bc: bc.commit.when, reverse=True)
            cached = found
            self._merge_commits_cache[key] = cached
        return [bc for bc in cached if not branch.name.equivalent_to(bc.branch.name.without_origin)]

    def get_source_branches(
        self, branch: Branch, configuration: GitVersionConfiguration, excluded: Iterable[Branch]
    ) -> list[Branch]:
        """Ports ``RepositoryStore.GetSourceBranches``."""
        commit_branches = self.find_merge_commits_for(branch, configuration, excluded)
        ordered = list(dict.fromkeys(commit_branches))  # HashSet semantics, insertion order
        ignore = self._collect_ignored_merge_commit_branches(branch, ordered)
        self._remove_commit_branches_found_in_other_branches(ordered, ignore)
        reference_lookup = self._references_by_sha()
        returned: set[Branch] = set()
        result: list[Branch] = []
        groups: dict[Commit, list[Branch]] = {}
        for bc in ordered:
            groups.setdefault(bc.commit, []).append(bc.branch)
        for commit, group in groups.items():
            ref_names = reference_lookup.get(commit.sha, set())
            matched = False
            for b in group:
                if b.name.canonical in ref_names:
                    if b not in returned:
                        returned.add(b)
                        result.append(b)
                    matched = True
            if matched:
                continue
            for b in group:
                if b not in returned:
                    returned.add(b)
                    result.append(b)
        return result

    def _references_by_sha(self) -> dict[str, set[str]]:
        """All refs grouped by target SHA (``repository.References.ToLookup``)."""
        out: dict[str, set[str]] = {}
        for b in self.branches:
            out.setdefault(b.tip, set()).add(b.name.canonical)
        for t in self.tags:
            # A tag reference targets the tag object for annotated tags; the
            # lookup is by reference target, so use the unpeeled target where
            # known. Our Tag model stores the peeled commit only; branches are
            # what this lookup is consulted for in practice.
            out.setdefault(t.target, set()).add(t.name.canonical)
        return out

    def _collect_ignored_merge_commit_branches(
        self, branch: Branch, commit_branches: list[BranchCommit]
    ) -> set[BranchCommit]:
        """Ports ``CollectIgnoredMergeCommitBranches``."""
        ignore: set[BranchCommit] = set()
        commits = self.branch_commits(branch)
        for bc in commit_branches:
            for commit in commits:
                if (
                    commit.when > bc.commit.when
                    and len(commit.parents) > 1
                    and bc.commit.sha in commit.parents
                ):
                    ignore.add(bc)
        return ignore

    def _remove_commit_branches_found_in_other_branches(
        self, commit_branches: list[BranchCommit], ignore: set[BranchCommit]
    ) -> None:
        """Ports ``RemoveCommitBranchesFoundInOtherBranches`` (mutates the list)."""
        for item in reversed(commit_branches[1:]):
            if item in ignore:
                continue
            for bc in list(commit_branches):
                if item.commit == bc.commit:
                    break
                other_commits = self.branch_commits(bc.branch)
                found = any(c.when >= item.commit.when and c == item.commit for c in other_commits)
                if found and item in commit_branches:
                    commit_branches.remove(item)

    # -- branch classification -------------------------------------------------

    def branches_where(
        self,
        configuration: GitVersionConfiguration,
        predicate: Callable[[BranchConfiguration], bool],
        exclude: Iterable[Branch] = (),
    ) -> list[Branch]:
        """Ports ``BranchRepository.GetBranches``."""
        skip = set(exclude)
        return [
            b
            for b in self.branches
            if b not in skip and predicate(get_branch_configuration(configuration, b.name))
        ]

    def main_branches(
        self, configuration: GitVersionConfiguration, exclude: Iterable[Branch] = ()
    ) -> list[Branch]:
        """Ports ``GetMainBranches``."""
        return self.branches_where(configuration, lambda c: c.is_main_branch is True, exclude)

    def release_branches(
        self, configuration: GitVersionConfiguration, exclude: Iterable[Branch] = ()
    ) -> list[Branch]:
        """Ports ``GetReleaseBranches``."""
        return self.branches_where(configuration, lambda c: c.is_release_branch is True, exclude)

    @staticmethod
    def detached(tip: str) -> Branch:
        """The detached-HEAD sentinel branch for ``tip``."""
        return Branch(ReferenceName(DETACHED_HEAD_CANONICAL), tip)
