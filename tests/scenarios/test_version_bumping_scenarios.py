# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/VersionBumpingScenarios.cs`` (6.8.2)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_applied_pre_release_label_causes_bump() -> None:
    configuration = gitflow(branches={"main": {"label": "pre", "source_branches": []}})
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0-pre.1")
        f.make_a_commit()
        f.assert_full_semver("1.0.0-pre.2", configuration)


def test_can_use_commit_messages_to_bump_version() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:minor")
        f.assert_full_semver("1.1.0-1")
        f.make_a_commit("+semver:major")
        f.assert_full_semver("2.0.0-2")


def test_can_use_commit_messages_to_bump_version_tag_takes_priority() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:major")
        f.assert_full_semver("2.0.0-1")
        f.apply_tag("1.1.0")
        f.assert_full_semver("1.1.0")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-1")


CONVENTIONAL_COMMIT_CASES = [
    ("build: Cleaned up various things", "1.0.1"),
    ("build: Cleaned up various things\n\nSome descriptive text", "1.0.1"),
    ("build: Cleaned up various things\n\nSome descriptive text\nWith a second line", "1.0.1"),
    ("build(ref): Cleaned up various things", "1.0.1"),
    ("build(ref)!: Major update", "2.0.0"),
    ("chore: Cleaned up various things", "1.0.1"),
    ("ci: Cleaned up various things", "1.0.1"),
    ("docs: Cleaned up various things", "1.0.1"),
    ("fix: Cleaned up various things", "1.0.1"),
    ("perf: Cleaned up various things", "1.0.1"),
    ("refactor: Cleaned up various things", "1.0.1"),
    ("revert: Cleaned up various things", "1.0.1"),
    ("style: Cleaned up various things", "1.0.1"),
    ("test: Cleaned up various things", "1.0.1"),
    ("feat(ref): Simple feature", "1.1.0"),
    ("feat(ref)!: Major update", "2.0.0"),
    ("feat: Major update\n\nSome descriptive text\n\nBREAKING CHANGE: A reason", "2.0.0"),
    ("feat: Major update\n\nSome descriptive text\n\nBREAKING CHANGE Missing colon", "1.1.0"),
    ("feat: Major update\n\nForgot to describe the change\n\nBREAKING CHANGE: ", "1.1.0"),
    ("feat: Major update\n\nBREAKING CHANGE: A reason", "2.0.0"),
    (
        "feat: Major update\n\nSome descriptive text\nWith a second line\n\nBREAKING CHANGE: A reason",
        "2.0.0",
    ),
]

#: The conventional-commit regexes from the upstream docs (version-increments page).
CONVENTIONAL_COMMIT_PATTERNS: dict[str, Any] = {
    "major_version_bump_message": (
        r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([\w\s-]*\))?"
        r"(!:|:.*\n\n((.+\n)+\n)?BREAKING CHANGE:\s.+)"
    ),
    "minor_version_bump_message": r"^(feat)(\([\w\s-]*\))?:",
    "patch_version_bump_message": (
        r"^(build|chore|ci|docs|fix|perf|refactor|revert|style|test)(\([\w\s-]*\))?:"
    ),
}


@pytest.mark.parametrize(("message", "expected"), CONVENTIONAL_COMMIT_CASES)
def test_can_use_conventional_commits_to_bump_version(message: str, expected: str) -> None:
    configuration = gitflow(
        branches={"main": {"mode": "ContinuousDeployment"}},
        strategies=["Mainline"],
        **CONVENTIONAL_COMMIT_PATTERNS,
    )
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit(message)
        f.assert_full_semver(expected, configuration)


def test_can_use_commit_messages_to_bump_version_base_version_tag_is_applied_to_same_commit() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:minor")
        f.assert_full_semver("1.1.0-1")
        f.apply_tag("2.0.0")
        f.make_a_commit("Hello")
        f.assert_full_semver("2.0.1-1")
