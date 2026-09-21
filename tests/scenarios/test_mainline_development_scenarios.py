# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/MainlineDevelopmentScenarios.cs`` (6.8.2)."""

from __future__ import annotations

from typing import Any

import pytest
from usg_pygitversion.config.schema import GitVersionConfiguration

from tests.scenarios.dsl import RemoteScenario, Scenario, gitflow
from tests.scenarios.test_version_bumping_scenarios import CONVENTIONAL_COMMIT_PATTERNS

pytestmark = pytest.mark.scenario


def mainline(
    branches: dict[str, dict[str, Any]] | None = None, **root: Any
) -> GitVersionConfiguration:
    """``GetConfigurationBuilder()`` from the upstream suite plus overrides."""
    base: dict[str, dict[str, Any]] = {
        "main": {
            "is_main_branch": True,
            "increment": "Patch",
            "mode": "ContinuousDeployment",
            "source_branches": [],
        },
        "develop": {
            "is_main_branch": False,
            "increment": "Minor",
            "mode": "ContinuousDelivery",
            "source_branches": ["main"],
        },
        "feature": {
            "is_main_branch": False,
            "increment": "Minor",
            "mode": "ContinuousDelivery",
            "source_branches": ["main"],
        },
        "hotfix": {
            "is_main_branch": False,
            "increment": "Patch",
            "mode": "ContinuousDelivery",
            "regex": r"^hotfix[\/-](?<BranchName>.+)",
            "label": "{BranchName}",
            "source_branches": ["main"],
        },
        "pull-request": {
            "is_main_branch": False,
            "increment": "Inherit",
            "mode": "ContinuousDelivery",
            "source_branches": ["main"],
        },
    }
    for name, overrides in (branches or {}).items():
        base.setdefault(name, {}).update(overrides)
    return gitflow(branches=base, strategies=["Mainline"], **root)


def test_merged_feature_branches_to_main_implies_release() -> None:
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit("1")
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("feature/foo")
        f.make_a_commit("2")
        f.assert_full_semver("1.0.1-foo.1", c)
        f.make_a_commit("2.1")
        f.assert_full_semver("1.0.1-foo.2", c)
        f.checkout("main")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.0.1", c)

        f.branch_to("feature/foo2")
        f.make_a_commit("3 +semver: minor")
        f.assert_full_semver("1.1.0-foo2.1", c)
        f.checkout("main")
        f.merge_no_ff("feature/foo2")
        f.assert_full_semver("1.1.0", c)

        f.branch_to("feature/foo3")
        f.make_a_commit("4")
        f.checkout("main")
        f.merge_no_ff("feature/foo3")
        f.amend_head_message(" +semver: minor")
        f.assert_full_semver("1.2.0", c)

        f.branch_to("feature/foo4")
        f.make_a_commit("5 +semver: major")
        f.assert_full_semver("2.0.0-foo4.1", c)
        f.checkout("main")
        f.merge_no_ff("feature/foo4")
        f.assert_full_semver("2.0.0", c)

        f.make_a_commit("6 +semver: major")
        f.assert_full_semver("3.0.0", c)
        f.make_a_commit("7 +semver: minor")
        f.assert_full_semver("3.1.0", c)
        f.make_a_commit("8")
        f.assert_full_semver("3.1.1", c)

        f.branch_to("feature/foo5")
        f.make_a_commit("9 +semver: minor")
        f.assert_full_semver("3.2.0-foo5.1", c)
        f.checkout("main")
        f.merge_no_ff("feature/foo5")
        f.assert_full_semver("3.2.0", c)

        f.make_a_commit("10 +semver: minor")
        f.assert_full_semver("3.3.0", c)
        f.make_a_commit("11 +semver: none")
        f.assert_full_semver("3.3.1", c)


def test_verify_pull_requests_act_like_continuous_delivery_on_feature_branch() -> None:
    c = mainline()
    with Scenario() as f:
        f.make_a_commit("1")
        f.assert_full_semver("0.0.1", c)
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("2")
        f.assert_full_semver("1.0.1", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("1.1.0-foo.0", c)
        f.make_a_commit("3")
        f.make_a_commit("4")
        f.create_pull_request_ref("feature/foo", "main", pr_number=8, normalise=True)
        f.assert_full_semver("1.1.0-PullRequest8.3", c)


def test_verify_pull_requests_act_like_continuous_delivery_on_hotfix_branch() -> None:
    c = mainline()
    with Scenario() as f:
        f.make_a_commit("1")
        f.assert_full_semver("0.0.1", c)
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("2")
        f.assert_full_semver("1.0.1", c)
        f.branch_to("hotfix/foo")
        f.assert_full_semver("1.0.2-foo.0", c)
        f.make_a_commit("3")
        f.make_a_commit("4")
        f.create_pull_request_ref("hotfix/foo", "main", pr_number=8, normalise=True)
        f.assert_full_semver("1.0.2-PullRequest8.3", c)


def test_verify_forward_merge() -> None:
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit("1")
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to("feature/foo")
        f.make_a_commit()
        f.assert_full_semver("1.0.2-foo.1", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.2-foo.2", c)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.0.2", c)
        f.checkout("feature/foo")
        f.assert_full_semver("1.0.2-foo.2", c)
        f.merge_no_ff("main")
        f.assert_full_semver("1.0.3-foo.3", c)


def test_verify_develop_tracks_main_version() -> None:
    c = mainline()
    with Scenario() as f:
        f.make_a_commit("1")
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.assert_full_semver("1.1.0-alpha.0", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.checkout("main")
        f.merge_no_ff("develop")
        f.assert_full_semver("1.1.0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.2", c)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.1.1", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.2", c)


def test_verify_develop_feature_tracks_main_version() -> None:
    c = mainline({"feature": {"increment": "Minor"}})
    with Scenario() as f:
        f.make_a_commit("1")
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.assert_full_semver("1.1.0-alpha.0", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.checkout("main")
        f.merge_no_ff("develop")
        f.assert_full_semver("1.1.0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("1.1.0-foo.1", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-foo.2", c)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.1.1", c)
        f.checkout("feature/foo")
        f.assert_full_semver("1.1.0-foo.2", c)
        f.checkout("develop")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.1.0-alpha.3", c)


def test_verify_merging_main_to_feature_does_not_cause_branch_commits_to_increment_version() -> (
    None
):
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit("first in main")
        f.branch_to("feature/foo")
        f.make_a_commit("first in foo")
        f.checkout("main")
        f.make_a_commit("second in main")
        f.checkout("feature/foo")
        f.merge_no_ff("main")
        f.make_a_commit("second in foo")
        f.checkout("main")
        f.make_a_tagged_commit("1.0.0")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.0.1", c)


def test_verify_merging_main_to_feature_does_not_stop_main_commits_incrementing_version() -> None:
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit("first in main")
        f.branch_to("feature/foo")
        f.make_a_commit("first in foo")
        f.checkout("main")
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("third in main")
        f.checkout("feature/foo")
        f.merge_no_ff("main")
        f.make_a_commit("second in foo")
        f.checkout("main")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.0.2", c)


def test_verify_issue_1154_can_forward_merge_main_to_feature_branch() -> None:
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1", c)
        f.branch_to("feature/branch2")
        f.branch_to("feature/branch1")
        f.make_a_commit()
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff("feature/branch1")
        f.assert_full_semver("0.0.2", c)
        f.checkout("feature/branch2")
        f.make_a_commit()
        f.make_a_commit()
        f.make_a_commit()
        f.merge_no_ff("main")
        f.assert_full_semver("0.0.3-branch2.4", c)


def test_verify_merging_main_into_a_feature_branch_works_with_multiple_branches() -> None:
    c = mainline({"feature": {"increment": "Patch"}})
    with Scenario() as f:
        f.make_a_commit("first in main")
        f.branch_to("feature/foo")
        f.make_a_commit("first in foo")
        f.branch_to("feature/bar")
        f.make_a_commit("first in bar")
        f.checkout("main")
        f.make_a_commit("second in main")
        f.checkout("feature/foo")
        f.merge_no_ff("main")
        f.make_a_commit("second in foo")
        f.checkout("feature/bar")
        f.merge_no_ff("main")
        f.make_a_commit("second in bar")
        f.checkout("main")
        f.make_a_tagged_commit("1.0.0")
        f.merge_no_ff("feature/foo")
        f.merge_no_ff("feature/bar")
        f.assert_full_semver("1.0.2", c)


def test_merging_feature_branch_that_increments_minor_number_increments_minor_version_of_main() -> (
    None
):
    c = mainline({"feature": {"mode": "ContinuousDelivery", "increment": "Minor"}})
    with Scenario() as f:
        f.make_a_commit("first in main")
        f.make_a_tagged_commit("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.branch_to("feature/foo")
        f.make_a_commit("first in foo")
        f.make_a_commit("second in foo")
        f.assert_full_semver("1.1.0-foo.2", c)
        f.checkout("main")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.1.0", c)


def test_verify_increment_config_is_honoured() -> None:
    minor = gitflow(
        branches={
            "main": {"mode": "ContinuousDeployment", "increment": "None"},
            "feature": {"mode": "ContinuousDelivery", "increment": "None"},
        },
        strategies=["Mainline"],
    )
    with Scenario() as f:
        f.make_a_commit("1")
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("feature/foo")
        f.make_a_commit("2 +semver: minor")
        f.assert_full_semver("1.1.0-foo.1", minor)
        f.make_a_commit("2.1")
        f.assert_full_semver("1.1.0-foo.2", minor)
        f.checkout("main")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.1.0", minor)

        f.branch_to("feature/foo2")
        f.make_a_commit("3 +semver: patch")
        f.assert_full_semver("1.1.1-foo2.1", minor)
        f.checkout("main")
        f.merge_no_ff("feature/foo2")
        f.assert_full_semver("1.1.1", minor)

        f.branch_to("feature/foo3")
        f.make_a_commit("4")
        f.checkout("main")
        f.merge_no_ff("feature/foo3")
        f.amend_head_message(" +semver: patch")
        f.assert_full_semver("1.1.2", minor)

        c = mainline()
        f.branch_to("feature/foo4")
        f.make_a_commit("5 +semver: major")
        f.assert_full_semver("2.0.0-foo4.1", minor)
        f.checkout("main")
        f.merge_no_ff("feature/foo4")
        f.assert_full_semver("2.0.0", c)

        f.make_a_commit("6 +semver: major")
        f.assert_full_semver("3.0.0", minor)
        f.make_a_commit("7 +semver: minor")
        f.assert_full_semver("3.1.0", minor)
        f.make_a_commit("8 +semver: patch")
        f.assert_full_semver("3.1.1", minor)

        f.branch_to("feature/foo5")
        f.make_a_commit("9 +semver: patch")
        f.assert_full_semver("3.1.2-foo5.1", minor)
        f.checkout("main")
        f.merge_no_ff("feature/foo5")
        f.assert_full_semver("3.1.2", minor)

        f.make_a_commit("10 +semver: patch")
        f.assert_full_semver("3.1.3", minor)
        f.make_a_commit("11 +semver: none")
        f.assert_full_semver("3.1.3", minor)


def test_branch_without_merge_base_mainline_branch_is_found() -> None:
    c = mainline(
        {"unknown": {"mode": "ContinuousDelivery"}},
        assembly_file_versioning_scheme="MajorMinorPatchTag",
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1", c)
        f.branch_to("master")
        f.delete_branch("main")
        f.assert_full_semver("0.0.1", c)
        f.make_commits(2)
        f.assert_full_semver("0.0.3", c)
        f.branch_to("issue-branch")
        f.make_a_commit()
        f.assert_full_semver("0.0.4-issue-branch.1", c)


def test_given_a_remote_git_repository_with_commits_then_cloned_local_develop_should_match() -> (
    None
):
    c = mainline()
    with RemoteScenario() as f:
        f.assert_full_semver("0.0.5", c)
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        with f.clone() as local:
            local.assert_full_semver("0.1.0-alpha.0", c)


@pytest.mark.parametrize(
    "message",
    [
        "feat!: Break stuff +semver: none",
        "feat: Add stuff +semver: none",
        "fix: Fix stuff +semver: none",
    ],
)
def test_no_bump_message_takes_precedence_over_bump_message(message: str) -> None:
    c = mainline(**CONVENTIONAL_COMMIT_PATTERNS)
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit(message)
        f.assert_full_semver("1.0.1", c)
