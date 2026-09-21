# SPDX-License-Identifier: MIT
"""Unit tests for the Mainline helpers: merged-commit lookup and version-field folding."""

from __future__ import annotations

import pytest
from pygitversion.calculation.increment import IncrementStrategyFinder
from pygitversion.calculation.mainline import consolidate
from pygitversion.calculation.store import RepositoryStore
from pygitversion.calculation.tagged_versions import TaggedSemanticVersionRepository
from pygitversion.config.schema import IgnoreConfiguration
from pygitversion.errors import GitVersionError
from pygitversion.git import GitRepository
from pygitversion.semver import VersionField

from tests.fixtures import RepositoryFixture


def _finder(repo: RepositoryFixture) -> tuple[RepositoryStore, IncrementStrategyFinder]:
    store = RepositoryStore(GitRepository(repo.path))
    return store, IncrementStrategyFinder(store, TaggedSemanticVersionRepository(store))


def test_get_merged_commits_returns_each_side_oldest_first(repo: RepositoryFixture) -> None:
    repo.make_a_commit("base")
    repo.branch_to("feature/x")
    f1 = repo.make_a_commit("f1")
    f2 = repo.make_a_commit("f2")
    repo.checkout("main")
    m1 = repo.make_a_commit("m1")
    merge = repo.merge_no_ff("feature/x")
    store, finder = _finder(repo)
    ignore = IgnoreConfiguration()
    merged = finder.get_merged_commits(store.commit(merge), 1, ignore)
    assert [c.sha for c in merged] == [f1, f2]
    first_parent_side = finder.get_merged_commits(store.commit(merge), 0, ignore)
    assert [c.sha for c in first_parent_side] == [m1]


def test_get_merged_commits_rejects_non_merge_commit(repo: RepositoryFixture) -> None:
    sha = repo.make_a_commit()
    store, finder = _finder(repo)
    with pytest.raises(GitVersionError, match="not a merge commit"):
        finder.get_merged_commits(store.commit(sha), 1, IgnoreConfiguration())


def test_get_merged_commits_rejects_octopus_merge(repo: RepositoryFixture) -> None:
    repo.make_a_commit("base")
    repo.branch_to("a")
    repo.make_a_commit("a1")
    repo.checkout("main")
    repo.branch_to("b")
    repo.make_a_commit("b1")
    repo.checkout("main")
    repo.git("merge", "--quiet", "--no-edit", "--no-ff", "a", "b")
    store, finder = _finder(repo)
    with pytest.raises(GitVersionError, match="more than one merge source"):
        finder.get_merged_commits(store.commit(repo.head_sha), 1, IgnoreConfiguration())


def test_consolidate_keeps_the_largest_field() -> None:
    assert consolidate(VersionField.NONE) is VersionField.NONE
    assert consolidate(VersionField.PATCH, None, VersionField.MINOR) is VersionField.MINOR
    assert consolidate(VersionField.MAJOR, VersionField.PATCH) is VersionField.MAJOR
