"""Tests for ReferenceName, mirroring upstream ReferenceNameTests."""

from __future__ import annotations

import pytest
from pygitversion.git import ReferenceName


@pytest.mark.parametrize(
    ("canonical", "friendly", "without_origin", "without_remote", "flags"),
    [
        ("refs/heads/main", "main", "main", "main", "local"),
        ("refs/heads/feature/x", "feature/x", "feature/x", "feature/x", "local"),
        ("refs/remotes/origin/main", "origin/main", "main", "main", "remote"),
        ("refs/remotes/upstream/dev", "upstream/dev", "upstream/dev", "dev", "remote"),
        ("refs/tags/v1.0.0", "v1.0.0", "v1.0.0", "v1.0.0", "tag"),
        ("refs/pull/12/head", "refs/pull/12/head", "refs/pull/12/head", "refs/pull/12/head", "pr"),
        (
            "refs/remotes/pull/12/head",
            "pull/12/head",
            "pull/12/head",
            "pull/12/head",
            "remote,pr",
        ),
        (
            "refs/pull-requests/7/merge",
            "refs/pull-requests/7/merge",
            "refs/pull-requests/7/merge",
            "refs/pull-requests/7/merge",
            "pr",
        ),
    ],
)
def test_views(
    canonical: str, friendly: str, without_origin: str, without_remote: str, flags: str
) -> None:
    ref = ReferenceName.parse(canonical)
    assert ref.friendly == friendly
    assert ref.without_origin == without_origin
    assert ref.without_remote == without_remote
    assert ref.is_local_branch == ("local" in flags)
    assert ref.is_remote_branch == ("remote" in flags)
    assert ref.is_tag == ("tag" in flags)
    assert ref.is_pull_request == ("pr" in flags)
    assert str(ref) == friendly


def test_parse_rejects_non_canonical() -> None:
    assert ReferenceName.try_parse("main") is None
    with pytest.raises(ValueError, match="canonical"):
        ReferenceName.parse("main")


def test_from_branch_name_accepts_both_forms() -> None:
    assert ReferenceName.from_branch_name("main").canonical == "refs/heads/main"
    assert ReferenceName.from_branch_name("refs/heads/main").canonical == "refs/heads/main"
    assert ReferenceName.from_branch_name("refs/remotes/origin/x").is_remote_branch


def test_from_tag_name() -> None:
    assert ReferenceName.from_tag_name("1.0").canonical == "refs/tags/1.0"
    with pytest.raises(ValueError, match="empty"):
        ReferenceName.from_tag_name("")


def test_equivalent_to_is_case_insensitive_over_three_forms() -> None:
    ref = ReferenceName("refs/remotes/origin/Main")
    assert ref.equivalent_to("refs/remotes/origin/main")
    assert ref.equivalent_to("ORIGIN/MAIN")
    assert ref.equivalent_to("main")
    assert not ref.equivalent_to("develop")
    assert not ref.equivalent_to(None)


def test_equality_and_ordering_on_canonical() -> None:
    a, b = ReferenceName("refs/heads/a"), ReferenceName("refs/heads/b")
    assert a == ReferenceName("refs/heads/a")
    assert a != b
    assert a < b
    assert len({a, ReferenceName("refs/heads/a")}) == 1
