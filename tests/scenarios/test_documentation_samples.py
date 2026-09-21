# SPDX-License-Identifier: MIT
"""Port of upstream ``DocumentationSamples.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario

pytestmark = pytest.mark.scenario


def test_gitflow_feature_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-alpha.1")
        f.branch_to("feature/myFeature")
        f.assert_full_semver("1.3.0-myFeature.1+1")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-myFeature.1+2")
        f.checkout("develop")
        f.merge_no_ff("feature/myFeature")
        f.assert_full_semver("1.3.0-alpha.3")


def test_gitflow_pull_request_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-alpha.1")
        f.branch_to("pull/2/merge")
        f.assert_full_semver("1.3.0-PullRequest2.1")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-PullRequest2.2")
        f.checkout("develop")
        f.merge_no_ff("pull/2/merge")
        f.assert_full_semver("1.3.0-alpha.3")


def test_gitflow_hotfix_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.checkout("main")
        f.branch_to("hotfix/1.2.1")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+2")
        f.apply_tag("1.2.1-beta.1")
        f.assert_full_semver("1.2.1-beta.2+0")
        f.checkout("main")
        f.merge_no_ff("hotfix/1.2.1")
        f.apply_tag("1.2.1")


def test_gitflow_minor_release() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.1")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.3.0")
        f.assert_full_semver("1.3.0-beta.1+1")
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("1.4.0-alpha.1")
        f.checkout("release/1.3.0")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-beta.1+2")
        f.apply_tag("1.3.0-beta.1")
        f.assert_full_semver("1.3.0-beta.2+0")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-beta.2+1")
        f.checkout("main")
        f.merge_no_ff("release/1.3.0")
        f.checkout("develop")
        f.merge_no_ff("release/1.3.0")
        f.checkout("main")
        f.apply_tag("1.3.0")
        f.assert_full_semver("1.3.0")
        f.checkout("develop")
        f.assert_full_semver("1.4.0-alpha.2")


def test_gitflow_major_release() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.3.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1")
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("2.1.0-alpha.1")
        f.checkout("release/2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+2")
        f.apply_tag("2.0.0-beta.1")
        f.assert_full_semver("2.0.0-beta.2+0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.2+1")
        f.checkout("main")
        f.merge_no_ff("release/2.0.0")
        f.checkout("develop")
        f.merge_no_ff("release/2.0.0")
        f.checkout("main")
        f.assert_full_semver("2.0.0-4")
        f.apply_tag("2.0.0")
        f.assert_full_semver("2.0.0")
        f.checkout("develop")
        f.assert_full_semver("2.1.0-alpha.2")


def test_gitflow_support_hotfix_release() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.3.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.checkout("main")
        f.apply_tag("2.0.0")
        f.checkout("1.3.0")
        f.branch_to("support/1.x")
        f.make_a_commit()
        f.assert_full_semver("1.3.1-1")
        f.branch_to("hotfix/1.3.1")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.3.1-beta.1+3")
        f.apply_tag("1.3.1-beta.1")
        f.assert_full_semver("1.3.1-beta.2+0")
        f.checkout("support/1.x")
        f.merge_no_ff("hotfix/1.3.1")
        f.assert_full_semver("1.3.1-4")
        f.apply_tag("1.3.1")
        f.assert_full_semver("1.3.1")


def test_gitflow_support_minor_release() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.3.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.checkout("main")
        f.apply_tag("2.0.0")
        f.checkout("1.3.0")
        f.branch_to("support/1.x")
        f.make_a_commit()
        f.apply_tag("1.3.1")
        f.branch_to("release/1.4.0")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.4.0-beta.1+2")
        f.apply_tag("1.4.0-beta.1")
        f.assert_full_semver("1.4.0-beta.2+0")
        f.checkout("support/1.x")
        f.merge_no_ff("release/1.4.0")
        f.assert_full_semver("1.4.0-3")
        f.apply_tag("1.4.0")
        f.assert_full_semver("1.4.0")


def test_github_flow_feature_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-1")
        f.branch_to("feature/myFeature")
        f.assert_full_semver("1.2.1-myFeature.1+1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-myFeature.1+2")
        f.checkout("main")
        f.merge_no_ff("feature/myFeature")
        f.assert_full_semver("1.2.1-3")


def test_github_flow_pull_request_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-1")
        f.branch_to("pull/2/merge")
        f.assert_full_semver("1.2.1-PullRequest2.1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-PullRequest2.2")
        f.checkout("main")
        f.merge_no_ff("pull/2/merge")
        f.assert_full_semver("1.2.1-3")


def test_github_flow_major_release() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.3.0")
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+1")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+2")
        f.apply_tag("2.0.0-beta.1")
        f.assert_full_semver("2.0.0-beta.2+0")
        version = f.get_version()
        assert version["CommitsSinceVersionSource"] == "0"
        assert version["VersionSourceDistance"] == "0"
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.2+1")
        f.checkout("main")
        f.merge_no_ff("release/2.0.0")
        f.assert_full_semver("2.0.0-4")
        f.apply_tag("2.0.0")
        f.assert_full_semver("2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.1-1")
