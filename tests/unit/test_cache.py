# SPDX-License-Identifier: MIT
"""Tests for the on-disk cache."""

from __future__ import annotations

import sys

from usg_pygitversion.cache import CacheProvider, cache_key
from usg_pygitversion.git import GitRepository

from tests.fixtures import RepositoryFixture
from tests.unit.test_output import sample


def test_key_changes_with_head_config_and_overrides(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    repository = GitRepository(repo.path)
    base = cache_key(repository, repo.path, None)
    assert len(base) == 40 and base == base.upper()
    assert cache_key(repository, repo.path, {"tag-prefix": "v"}) != base
    repo.write_config("next-version: 2.0.0\n")
    with_config = cache_key(repository, repo.path, None)
    assert with_config != base
    repo.make_a_commit()
    assert cache_key(GitRepository(repo.path), repo.path, None) != with_config


def test_round_trip_and_corrupt_file_is_removed(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    provider = CacheProvider(GitRepository(repo.path))
    key = "A" * 40
    assert provider.load(key) is None
    provider.save(key, sample())
    path = provider.path_for(key)
    if sys.platform != "win32":
        # Windows honours only the read-only bit of the creation mode and
        # reports 0o666; owner-only access there comes from the profile ACL.
        assert oct(path.stat().st_mode & 0o777) == oct(0o600)
    loaded = provider.load(key)
    assert loaded is not None and loaded["FullSemVer"] == "1.2.4-1"
    path.write_text("{not json")
    assert provider.load(key) is None
    assert not path.exists()
    assert provider.directory.is_dir()


def test_key_changes_with_target_branch_and_commit(repo: RepositoryFixture) -> None:
    # Upstream's key stops at HEAD; this port is read-only so /b and /c must
    # be part of the key or a HEAD result would be served for them (SI-7).
    first = repo.make_a_commit()
    repo.make_a_commit()
    repository = GitRepository(repo.path)
    base = cache_key(repository, repo.path, None)
    assert cache_key(repository, repo.path, None, commit_id=first) != base
    assert cache_key(repository, repo.path, None, target_branch="other") != base
    assert cache_key(repository, repo.path, None, target_branch="other") != cache_key(
        repository, repo.path, None, commit_id=first
    )
    # Absent values leave the upstream-shaped key untouched.
    assert cache_key(repository, repo.path, None, target_branch=None, commit_id="") == base
