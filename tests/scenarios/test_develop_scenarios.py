# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/DevelopScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow

pytestmark = pytest.mark.scenario

_CD = {"mode": "ContinuousDelivery"}


def test_when_develop_has_multiple_commits_specify_existing_commit_id() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.make_a_commit()
        third = f.make_a_commit()
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.3", commit_id=third)


def test_when_develop_has_multiple_commits_specify_non_existing_commit_id() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_commits(5)
        f.assert_full_semver("1.1.0-alpha.5", commit_id="non-existing-commit-id")


def test_when_develop_branched_from_tagged_commit_on_main_version_does_not_change() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.assert_full_semver("1.1.0-alpha.0")


def test_can_change_develop_tag_via_config() -> None:
    configuration = gitflow(branches={"develop": {"label": "alpha", "source_branches": []}})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", configuration)


def test_when_developer_branch_exists_dont_treat_as_develop() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("developer")
        f.make_a_commit()
        f.assert_full_semver("1.0.1-developer.1+1")


def test_when_develop_branched_from_main_minor_is_increased() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1")


def test_merging_release_branch_back_into_develop_with_merging_to_main_does_bump_develop_version() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release-2.0.0")
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.checkout("develop")
        f.merge_no_ff("release-2.0.0")
        f.assert_full_semver("2.1.0-alpha.2")


def test_can_handle_continuous_delivery() -> None:
    configuration = gitflow(branches={"develop": _CD})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_tagged_commit("1.1.0-alpha7")
        f.assert_full_semver("1.1.0-alpha.7", configuration)


def test_when_develop_branched_from_main_detached_head_minor_is_increased() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        commit = f.make_a_commit()
        f.make_a_commit()
        f.checkout(commit)
        f.assert_full_semver("1.1.0-alpha.1", only_tracked_branches=False)


def test_inherit_version_from_parent_release_branch() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.make_a_commit()
        f.checkout("develop")
        f.assert_full_semver("2.1.0-alpha.0")
        f.make_a_commit()
        f.assert_full_semver("2.1.0-alpha.1")
        f.merge_no_ff("release/2.0.0")
        f.assert_full_semver("2.1.0-alpha.4")
        f.branch_to("feature/MyFeature")
        f.make_a_commit()
        f.assert_full_semver("2.1.0-MyFeature.1+5")


def test_inherit_version_from_parent_release_branch_with_version2_instead_of_version3() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.create_branch("release/3.0.0")
        f.make_a_commit()
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+3")
        f.checkout("develop")
        f.assert_full_semver("3.1.0-alpha.1")
        f.make_a_commit()
        f.assert_full_semver("3.1.0-alpha.2")
        f.merge_no_ff("release/2.0.0")
        f.assert_full_semver("3.1.0-alpha.5")
        f.checkout("release/2.0.0")
        f.branch_to("feature/MyFeature")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-MyFeature.1+4")


def test_when_multiple_develop_branches_exist_and_current_branch_has_increment_inherit_policy_and_current_commit_is_a_merge() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.create_branch("bob_develop")
        f.create_branch("develop")
        f.create_branch("feature/x")
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("feature/x")
        f.make_a_commit()
        f.merge_no_ff("develop")
        f.assert_full_semver("1.1.0-x.1+3")


def test_tag_on_hotfix_should_not_affect_develop() -> None:
    with GitFlowScenario("1.2.0") as f:
        f.checkout("main")
        f.branch_to("hotfix-1.2.1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+1")
        f.apply_tag("1.2.1-beta.1")
        f.assert_full_semver("1.2.1-beta.2+0")
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("1.3.0-alpha.2")


def test_version_source_distance_should_not_go_down_upon_gitflow_release_finish() -> None:
    configuration = gitflow(branches={"main": _CD, "develop": _CD, "release": _CD})
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.1.0")
        f.branch_to("develop")
        f.make_a_commit("commit in develop - 1")
        f.assert_full_semver("1.2.0-alpha.1")
        f.branch_to("release/1.2.0")
        f.assert_full_semver("1.2.0-beta.1+1")
        f.checkout("develop")
        for i in range(2, 6):
            f.make_a_commit(f"commit in develop - {i}")
        f.assert_full_semver("1.3.0-alpha.4")
        f.checkout("release/1.2.0")
        for i in range(1, 4):
            f.make_a_commit(f"commit in release/1.2.0 - {i}")
        f.assert_full_semver("1.2.0-beta.1+4")
        f.checkout("main")
        f.merge_no_ff("release/1.2.0")
        f.apply_tag("1.2.0")
        f.checkout("develop")
        f.merge_no_ff("release/1.2.0")
        f.make_a_commit("commit in develop - 6")
        f.assert_full_semver("1.3.0-alpha.6")
        f.delete_branch("release/1.2.0")
        f.assert_full_semver("1.3.0-alpha.6", configuration)


def test_version_source_distance_should_not_go_down_upon_merging_feature_only_to_develop() -> None:
    configuration = gitflow(branches={"main": _CD, "develop": _CD, "release": _CD})
    with Scenario() as f:
        f.make_a_commit("commit in main - 1")
        f.apply_tag("1.1.0")
        f.branch_to("develop")
        f.make_a_commit("commit in develop - 1")
        f.assert_full_semver("1.2.0-alpha.1")
        f.branch_to("release/1.2.0")
        for i in range(1, 4):
            f.make_a_commit(f"commit in release - {i}")
        f.assert_full_semver("1.2.0-beta.1+4")
        f.apply_tag("1.2.0")
        f.checkout("develop")
        f.make_a_commit("commit in develop - 2")
        f.assert_full_semver("1.3.0-alpha.1")
        f.merge_no_ff("release/1.2.0")
        f.assert_full_semver("1.3.0-alpha.2")
        f.delete_branch("release/1.2.0")
        f.assert_full_semver("1.3.0-alpha.2", configuration)


def test_previous_pre_release_tag_should_be_respected_when_counting_commits() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_tagged_commit("1.0.0-alpha.3")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.0.0-alpha.5")


@pytest.mark.parametrize(
    "configuration_branches",
    [
        {
            "main": _CD,
            "develop": {**_CD, "prevent_increment": {"of_merged_branch": False}},
            "release": _CD,
        },
        None,
    ],
    ids=["prevent-false", "prevent-true"],
)
def test_when_prevent_increment_of_merged_branch_version_source_distance_should_not_go_down_when_merging_release_to_develop(
    configuration_branches: dict[str, dict[str, object]] | None,
) -> None:
    if configuration_branches is None:
        configuration = gitflow(
            mode="ContinuousDelivery",
            branches={"develop": {"prevent_increment": {"of_merged_branch": True}}},
        )
    else:
        configuration = gitflow(branches=configuration_branches)
    with Scenario() as f:
        release = "release/1.1.0"
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(1)
        f.branch_to(release)
        f.make_commits(3)
        f.checkout("main")
        f.merge_no_ff(release)
        f.apply_tag("v1.1.0")
        f.checkout("develop")
        f.make_commits(2)
        f.merge_no_ff(release)
        f.assert_full_semver("1.2.0-alpha.3")
        f.assert_full_semver("1.2.0-alpha.3", configuration)
        before = f.get_version(configuration)["Sha"]
        f.delete_branch(release)
        after = f.get_version(configuration)["Sha"]
        assert after == before
        f.assert_full_semver("1.2.0-alpha.3")
        f.assert_full_semver("1.2.0-alpha.3", configuration)


def test_when_prevent_increment_of_merged_branch_version_is_false_for_develop_distance_should_not_go_down_when_merging_hotfix_to_develop() -> (
    None
):
    configuration = gitflow(
        branches={
            "develop": {"prevent_increment": {"of_merged_branch": False}},
            "hotfix": {
                "prevent_increment": {"of_merged_branch": True},
                "regex": r"^(origin/)?hotfix[\/-]",
            },
        }
    )
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(1)
        f.checkout("develop")
        f.make_commits(3)
        f.assert_full_semver("1.1.0-alpha.4", configuration)
        release = "release/1.1.0"
        f.branch_to(release)
        f.make_commits(3)
        f.assert_full_semver("1.1.0-beta.1+7", configuration)
        f.checkout("main")
        f.merge_no_ff(release)
        f.apply_tag("v1.1.0")
        f.checkout("develop")
        f.make_commits(2)
        f.merge_no_ff(release)
        f.delete_branch(release)
        f.assert_full_semver("1.2.0-alpha.3", configuration)
        hotfix = "hotfix/1.1.1"
        f.checkout("main")
        f.branch_to(hotfix)
        f.make_commits(3)
        f.checkout("main")
        f.merge_no_ff(hotfix)
        f.apply_tag("v1.1.1")
        f.checkout("develop")
        f.make_commits(3)
        f.assert_full_semver("1.2.0-alpha.6", configuration)
        f.merge_no_ff(hotfix)
        f.assert_full_semver("1.2.0-alpha.7", configuration)
        f.delete_branch(hotfix)
        f.assert_full_semver("1.2.0-alpha.7", configuration)


def test_next_version_should_be_considered_on_the_main_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", gitflow())
        f.assert_full_semver("1.0.0-1", gitflow(next_version="1.0.0"))
        f.make_a_commit()
        f.assert_full_semver("0.0.1-2", gitflow())
        f.assert_full_semver("1.0.0-2", gitflow(next_version="1.0.0"))


def test_prevent_decrementation_of_versions_on_the_main_branch() -> None:
    with Scenario("develop") as f:
        configuration = gitflow(next_version="1.0.0")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+2", configuration)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", configuration)
        f.checkout("release/1.0.0")
        f.apply_tag("1.0.0-beta.1")
        f.assert_full_semver("1.0.0-beta.2+0", configuration)
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.2", configuration)
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.4", configuration)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.5", configuration)
        f.delete_tag("1.0.0-beta.1")
        f.branch_to("main")
        f.assert_full_semver("1.0.0-5", configuration)
        f.assert_full_semver("1.0.0-5", gitflow(next_version="1.0.0"))
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", configuration)


def test_tagged_version_from_the_main_branch_should_be_considered_even_if_it_is_newer() -> None:
    with Scenario("main") as f:
        f.make_a_tagged_commit("1.1.1")
        f.branch_to("develop")
        f.make_a_commit()
        f.merge_no_ff("main")
        f.apply_tag("9.9.9")
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("9.10.0-alpha.1", gitflow())
