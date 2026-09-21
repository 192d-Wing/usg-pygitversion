"""Tests for the repository fixture DSL itself.

The fixture is the foundation of every scenario test, so its own behaviour
(determinism, hermeticity, cleanup) is verified first.
"""

from __future__ import annotations

from pathlib import Path

from tests.fixtures import RepositoryFixture


def test_initialises_on_requested_branch(repo: RepositoryFixture) -> None:
    assert repo.current_branch == "main"
    assert repo.branches() == []  # no commits yet, so no branch ref exists


def test_commits_are_deterministic_across_fixtures() -> None:
    # Two independent fixtures producing the same history must yield the
    # same SHAs; this is what makes golden and differential tests stable.
    with RepositoryFixture() as a, RepositoryFixture() as b:
        a.make_commits(3)
        b.make_commits(3)
        assert a.head_sha == b.head_sha


def test_branch_tag_merge_roundtrip(repo: RepositoryFixture) -> None:
    repo.make_a_tagged_commit("1.0.0")
    repo.branch_to("feature/x")
    repo.make_commits(2)
    merge_sha = repo.merge_to("main")
    assert repo.current_branch == "main"
    assert repo.head_sha == merge_sha
    assert repo.tags() == ["1.0.0"]
    assert repo.branches() == ["feature/x", "main"]
    # --no-ff guarantees a merge commit with two parents.
    parents = repo.git("rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(parents) == 3


def test_temporary_directory_is_removed() -> None:
    with RepositoryFixture() as repo:
        path: Path = repo.path
        assert path.is_dir()
    assert not path.exists()


def test_hermetic_environment_ignores_user_config(repo: RepositoryFixture) -> None:
    # HOME is redirected into the fixture, so no global config can leak.
    assert repo.git("config", "--global", "--list", check=False) == ""
