# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/PullRequestScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, githubflow

pytestmark = pytest.mark.scenario


def test_ensure_pull_request_with_increment_major_on_main_and_minor_on_feature_branch() -> None:
    configuration = githubflow(
        branches={"main": {"increment": "Major"}, "feature": {"increment": "Minor"}}
    )
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("1.0.0-1", configuration)
        f.apply_tag("1.0.0")
        f.branch_to("feature/foo")
        f.make_a_commit("B")
        f.assert_full_semver("1.1.0-foo.1+1", configuration)
        f.checkout("main")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("2.0.0-PullRequest2.2", configuration)
        f.checkout("main")
        f.delete_branch("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("2.0.0-2", configuration)


def test_can_calculate_pull_request_changes() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.1.0")
        f.branch_to("feature/Foo")
        f.make_a_commit()
        f.create_pull_request_ref("feature/Foo", "main", normalise=True)
        f.assert_full_semver("0.1.1-PullRequest2.2")


def test_can_calculate_pull_request_changes_inheriting_config() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.1.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("feature/Foo")
        f.make_a_commit()
        f.create_pull_request_ref("feature/Foo", "develop", 44, normalise=True)
        f.assert_full_semver("0.2.0-PullRequest44.3")


def test_can_calculate_pull_request_changes_from_remote_repo() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.1.0")
        f.branch_to("feature/Foo")
        f.make_a_commit()
        f.create_pull_request_ref("feature/Foo", "main", normalise=True)
        f.assert_full_semver("0.1.1-PullRequest2.2")


def test_can_calculate_pull_request_changes_inheriting_config_from_remote_repo() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.1.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("feature/Foo")
        f.make_a_commit()
        f.create_pull_request_ref("feature/Foo", "develop", normalise=True)
        f.assert_full_semver("0.2.0-PullRequest2.3")


def test_can_calculate_pull_request_changes_when_there_are_multiple_merge_candidates() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.1.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("copyOfDevelop")
        f.branch_to("feature/Foo")
        f.make_a_commit()
        f.create_pull_request_ref("feature/Foo", "develop", normalise=True)
        f.assert_full_semver("0.2.0-PullRequest2.3")


def test_calculates_correct_version_after_release_branch_merged_to_main() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("one")
        f.branch_to("release/2.0.0")
        f.make_a_commit("two")
        f.make_a_commit("three")
        f.create_pull_request_ref("release/2.0.0", "main", normalise=True)
        f.assert_full_semver("2.0.0-PullRequest2.4")
