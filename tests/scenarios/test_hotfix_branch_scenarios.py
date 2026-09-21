# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/HotfixBranchScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_patch_latest_release_example() -> None:
    with GitFlowScenario("1.2.0") as f:
        f.checkout("main")
        f.branch_to("hotfix-1.2.1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+2")
        f.apply_tag("1.2.1-beta.1")
        f.assert_full_semver("1.2.1-beta.2+0")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.2+1")
        f.checkout("main")
        f.merge_no_ff("hotfix-1.2.1")
        f.assert_full_semver("1.2.1-4")
        f.apply_tag("1.2.1")
        f.assert_full_semver("1.2.1")
        f.checkout("develop")
        f.assert_full_semver("1.3.0-alpha.1")
        f.merge_no_ff("hotfix-1.2.1")
        f.assert_full_semver("1.3.0-alpha.2")


def _three_tags(f: GitFlowScenario) -> None:
    f.make_a_tagged_commit("1.0.0")
    f.make_a_tagged_commit("1.1.0")
    f.make_a_tagged_commit("2.0.0")


def test_can_take_version_from_hotfixes_branch() -> None:
    with GitFlowScenario(None, _three_tags) as f:
        f.create_branch("support-1.1", f.tag_target("1.1.0"))
        f.checkout("support-1.1")
        f.assert_full_semver("1.1.0")
        f.branch_to("hotfixes/1.1.1")
        f.assert_full_semver("1.1.1-beta.1+0")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-beta.1+1")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-beta.1+2")


def test_patch_older_release_example() -> None:
    with GitFlowScenario(None, _three_tags) as f:
        f.checkout("main")
        f.create_branch("support-1.1", f.tag_target("1.1.0"))
        f.checkout("support-1.1")
        f.assert_full_semver("1.1.0")
        f.branch_to("hotfix-1.1.1")
        f.assert_full_semver("1.1.1-beta.1+0")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-beta.1+1")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-beta.1+2")
        f.branch_to("feature/fix")
        f.assert_full_semver("1.1.1-fix.1+2")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-fix.1+3")
        f.create_pull_request_ref("feature/fix", "hotfix-1.1.1", pr_number=8, normalise=True)
        f.assert_full_semver("1.1.1-PullRequest8.4")
        f.checkout("hotfix-1.1.1")
        f.merge_no_ff("feature/fix")
        f.assert_full_semver("1.1.1-beta.1+4")
        f.checkout("support-1.1")
        f.merge_no_ff("hotfix-1.1.1")
        f.assert_full_semver("1.1.1-5")
        f.apply_tag("1.1.1")
        f.assert_full_semver("1.1.1")
        f.checkout("develop")
        f.assert_full_semver("2.1.0-alpha.1")
        f.merge_no_ff("support-1.1")
        f.assert_full_semver("2.1.0-alpha.7")


@pytest.mark.parametrize("delete_feature", [True, False])
def test_feature_on_hotfix_feature_branch(delete_feature: bool) -> None:
    configuration = gitflow(assembly_versioning_scheme="MajorMinorPatchTag")
    with Scenario() as f:
        f.make_a_commit("initial")
        f.branch_to("develop")
        f.branch_to("release/4.5.0")
        f.assert_full_semver("4.5.0-beta.1+1", configuration)
        f.make_a_commit("blabla")
        f.checkout("develop")
        f.merge_no_ff("release/4.5.0")
        f.checkout("main")
        f.merge_no_ff("release/4.5.0")
        f.branch_to("support/4.5")
        f.apply_tag("4.5.0")
        f.assert_full_semver("4.5.0", configuration)
        f.branch_to("hotfix/4.5.1")
        f.branch_to("feature/some-bug-fix")
        f.make_a_commit("blabla")
        f.checkout("hotfix/4.5.1")
        f.merge_no_ff("feature/some-bug-fix")
        if delete_feature:
            f.delete_branch("feature/some-bug-fix")
        f.assert_full_semver("4.5.1-beta.1+2", configuration)


def test_is_version_taken_from_hotfix_branch_name() -> None:
    configuration = gitflow()
    with GitFlowScenario("4.20.4") as f:
        f.checkout("develop")
        f.assert_full_semver("4.21.0-alpha.1", configuration)
        f.branch_to("release/4.21.1")
        f.assert_full_semver("4.21.1-beta.1+1", configuration)
        f.make_a_commit()
        f.assert_full_semver("4.21.1-beta.1+2", configuration)
        f.branch_to("hotfix/4.21.1")
        f.assert_full_semver("4.21.1-beta.1+2", configuration)
        f.make_a_commit()
        f.assert_full_semver("4.21.1-beta.1+3", configuration)
