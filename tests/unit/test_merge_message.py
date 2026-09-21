# SPDX-License-Identifier: MIT
"""Merge-message parsing and version-in-branch-name extraction (upstream ``MergeMessageTests``)."""

from __future__ import annotations

import pytest
from usg_pygitversion.calculation.merge_message import MergeMessage, try_get_semantic_version
from usg_pygitversion.config.provider import build
from usg_pygitversion.git.refname import ReferenceName
from usg_pygitversion.semver import SemanticVersionFormat


@pytest.mark.parametrize(
    ("message", "fmt", "source", "target", "pr", "version"),
    [
        (
            "Merge branch 'release/1.2.0' into develop",
            "Default",
            "release/1.2.0",
            "develop",
            None,
            "1.2.0",
        ),
        ("Merge branch 'feature/x'", "Default", "feature/x", None, None, None),
        ("Merge tag 'v2.0.0' into main", "Default", "v2.0.0", "main", None, "2.0.0"),
        (
            "Finish release/1.5.0 into develop",
            "SmartGit",
            "release/1.5.0",
            "develop",
            None,
            "1.5.0",
        ),
        (
            "Merge pull request #12 in org/repo from release/3.0.0 to main",
            "BitBucketPull",
            "release/3.0.0",
            "main",
            12,
            "3.0.0",
        ),
        (
            "Pull request #7: title\r\n\r\nMerge in PRJ/repo from release/1.1.0 to develop",
            "BitBucketPullv7",
            "release/1.1.0",
            "develop",
            7,
            "1.1.0",
        ),
        (
            "Merged in release/4.0.0 (pull request #99)",
            "BitBucketCloudPull",
            "release/4.0.0",
            None,
            99,
            "4.0.0",
        ),
        (
            "Merge pull request #5 from org/release/2.2.0",
            "GitHubPull",
            "release/2.2.0",
            None,
            5,
            "2.2.0",
        ),
        (
            "Merge remote-tracking branch 'origin/release/1.0.0' into develop",
            "RemoteTracking",
            "refs/remotes/origin/release/1.0.0",
            "develop",
            None,
            "1.0.0",
        ),
        (
            "Merge pull request 42 from release/9.9.9 into main",
            "AzureDevOpsPull",
            "release/9.9.9",
            "main",
            42,
            "9.9.9",
        ),
    ],
)
def test_default_formats(
    message: str, fmt: str, source: str, target: str | None, pr: int | None, version: str | None
) -> None:
    parsed = MergeMessage.parse(message, build())
    assert parsed.format_name == fmt
    assert parsed.merged_branch == ReferenceName.from_branch_name(source)
    assert parsed.target_branch == target
    assert parsed.pull_request_number == pr
    assert parsed.is_merged_pull_request == (pr is not None)
    assert (str(parsed.version) if parsed.version else None) == version


def test_no_match_and_empty_message() -> None:
    assert MergeMessage.parse("just a commit", build()).format_name is None
    assert MergeMessage.parse("", build()).merged_branch is None


def test_custom_formats_are_tried_first_in_order() -> None:
    configuration = build({"merge-message-formats": {"Custom": r"^Land (?<SourceBranch>\S+)"}})
    parsed = MergeMessage.parse("Land release/2.0.0", configuration)
    assert parsed.format_name == "Custom"
    assert parsed.version is not None
    assert str(parsed.version) == "2.0.0"


@pytest.mark.parametrize(
    ("name", "expected_version", "expected_name"),
    [
        ("release/1.2.3", "1.2.3", None),
        ("release/1.2.3-foo", "1.2.3", "foo"),
        ("release-2.0.0", "2.0.0", None),
        ("release/v3.1", "3.1.0", None),
        ("origin/release/4.0.0", "4.0.0", None),
        ("feature/upgrade-to-9000.0.1", None, None),
        ("hotfix/downgrade-some-lib-to-3.2.1", None, None),
        ("release/1.0.0/nested", "1.0.0", "/nested"),
        ("main", None, None),
        ("release/next", None, None),
    ],
)
def test_try_get_semantic_version(
    name: str, expected_version: str | None, expected_name: str | None
) -> None:
    ref = ReferenceName.from_branch_name(name)
    result = try_get_semantic_version(ref, None, "[vV]?", SemanticVersionFormat.LOOSE)
    if expected_version is None:
        assert result is None
    else:
        assert result is not None
        assert str(result.value) == expected_version
        assert result.name == expected_name
