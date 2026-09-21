# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/ReleaseBranchScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_no_merge_backs_to_develop_in_case_there_are_no_changes_in_release_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_commits(3)
        f.create_branch("release/1.0.0")
        f.checkout("main")
        f.merge_no_ff("release/1.0.0")
        f.apply_tag("1.0.0")
        f.checkout("develop")
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.0")


def test_no_merge_backs_to_develop_in_case_there_are_changes_in_release_branch() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_commits(3)
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff("release/1.0.0")
        f.apply_tag("1.0.0")
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.1")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.2")
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.2")


@pytest.mark.parametrize("branch", ["release-2.0.0", "releases/2.0.0"])
def test_can_take_version_from_release_branch(branch: str) -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.branch_to(branch)
        f.assert_full_semver("2.0.0-beta.1+5")
        f.make_commits(2)
        f.assert_full_semver("2.0.0-beta.1+7")


def test_can_take_pre_release_version_from_releases_branch_with_numeric_pre_release_tag() -> None:
    with Scenario() as f:
        f.make_commits(5)
        f.branch_to("releases/2.0.0")
        f.apply_tag("v2.0.0-beta.1")
        assert f.get_version()["FullSemVer"] == "2.0.0-beta.2+0"


def test_release_branch_with_next_version_set_in_config() -> None:
    configuration = gitflow(next_version="2.0.0")
    with Scenario() as f:
        f.make_commits(5)
        f.branch_to("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+5", configuration)
        f.make_commits(2)
        f.assert_full_semver("2.0.0-beta.1+7", configuration)


def test_can_take_version_from_release_branch_with_label_overridden() -> None:
    configuration = gitflow(branches={"release": {"label": "rc"}})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.branch_to("release-2.0.0")
        f.assert_full_semver("2.0.0-rc.1+5", configuration)
        f.make_commits(2)
        f.assert_full_semver("2.0.0-rc.1+7", configuration)


def test_can_handle_release_branch_with_stability() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.create_branch("develop")
        f.make_commits(5)
        f.branch_to("release-2.0.0-Final")
        f.assert_full_semver("2.0.0-beta.1+5")
        f.make_commits(2)
        f.assert_full_semver("2.0.0-beta.1+7")


def test_when_release_branch_off_develop_is_merged_into_main_and_develop_version_is_taken_with_it() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.create_branch("develop")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(4)
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.assert_full_semver("2.0.0-6")
        f.make_commits(2)
        f.assert_full_semver("2.0.0-8")


def test_when_release_branch_off_main_is_merged_into_main_version_is_taken_with_it() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(4)
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.assert_full_semver("2.0.0-6")


def test_main_versioning_continuous_correctly_after_merging_release_branch() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(4)
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.assert_full_semver("2.0.0-6")
        f.delete_branch("release-2.0.0")
        f.assert_full_semver("2.0.0-6")
        f.apply_tag("2.0.0")
        f.make_commits(1)
        f.assert_full_semver("2.0.1-1")


def test_when_release_branch_is_merged_into_develop_highest_version_is_taken_with_it() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.create_branch("develop")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(4)
        f.checkout("develop")
        f.merge_no_ff("release-2.0.0")
        f.branch_to("release-1.0.0")
        f.make_commits(4)
        f.checkout("develop")
        f.merge_no_ff("release-1.0.0")
        f.assert_full_semver("2.1.0-alpha.11")


def test_when_release_branch_is_merged_into_main_highest_version_is_taken_with_it() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(4)
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.branch_to("release-1.0.0")
        f.make_commits(4)
        f.checkout("main")
        f.merge_no_ff("release-1.0.0")
        f.assert_full_semver("2.0.0-11")


def test_when_release_branch_is_merged_into_main_highest_version_is_taken_with_it_even_with_more_than_two_active_branches() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(1)
        for version in ("3.0.0", "2.0.0", "1.0.0"):
            f.branch_to(f"release-{version}")
            f.make_commits(4)
            f.checkout("main")
            f.merge_no_ff(f"release-{version}")
        f.assert_full_semver("3.0.0-16")


def test_when_merging_release_back_to_dev_should_not_reset_beta_version() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.branch_to("develop")
        f.make_commits(1)
        f.assert_full_semver("1.1.0-alpha.1")
        f.branch_to("release-2.0.0")
        f.make_commits(1)
        f.assert_full_semver("2.0.0-beta.1+2")
        f.apply_tag("2.0.0-beta1")
        f.make_commits(1)
        f.assert_full_semver("2.0.0-beta.2+1")
        f.checkout("develop")
        f.merge_no_ff("release-2.0.0")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.2+1")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.2+2")


def test_hotfix_off_release_branch_should_not_reset_count() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.branch_to("develop")
        f.make_commits(1)
        f.branch_to("release-2.0.0")
        f.make_commits(1)
        f.assert_full_semver("2.0.0-beta.1+2", configuration)
        f.make_commits(4)
        f.assert_full_semver("2.0.0-beta.1+6", configuration)
        f.create_branch("hotfix-2.0.0")
        f.make_commits(2)
        f.checkout("release-2.0.0")
        f.merge_no_ff("hotfix-2.0.0")
        f.delete_branch("hotfix-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+8", configuration)


def test_merge_on_release_branch_should_not_reset_count() -> None:
    configuration = gitflow(assembly_versioning_scheme="MajorMinorPatchTag")
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.branch_to("develop")
        f.make_a_commit()
        f.create_branch("release/2.0.0")
        f.branch_to("release/2.0.0-xxx")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+2", configuration)
        f.checkout("release/2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+2", configuration)
        f.merge_no_ff("release/2.0.0-xxx")
        f.assert_full_semver("2.0.0-beta.1+4", configuration)


def test_commit_on_develop_after_release_branch_merge_to_develop_should_not_reset_count() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_commit("initial")
        f.branch_to("develop")
        f.branch_to("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1", configuration)
        f.make_a_commit("release 1")
        f.make_a_commit("release 2")
        f.assert_full_semver("2.0.0-beta.1+3", configuration)
        f.checkout("develop")
        f.merge_no_ff("release-2.0.0")
        f.checkout("release-2.0.0")
        f.make_a_commit("release 3 - after first merge")
        f.assert_full_semver("2.0.0-beta.1+4", configuration)
        f.checkout("develop")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+4", configuration)
        f.checkout("develop")
        f.make_a_commit("develop after merge")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+4", configuration)
        f.make_a_commit("release 4")
        f.make_a_commit("release 5")
        f.assert_full_semver("2.0.0-beta.1+6", configuration)
        f.checkout("develop")
        f.merge_no_ff("release-2.0.0")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+6", configuration)


def test_commit_between_merge_release_to_develop_should_not_reset_count() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_commit("initial")
        f.branch_to("develop")
        f.branch_to("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1", configuration)
        commit1 = f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+3", configuration)
        f.checkout("develop")
        f.merge_commit_no_ff(commit1)
        f.merge_no_ff("release-2.0.0")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+3", configuration)
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+5", configuration)


def test_release_branch_should_use_branch_name_version_despite_bump_in_previous_commit() -> None:
    configuration = gitflow(semantic_version_format="Loose")
    with Scenario() as f:
        f.make_a_tagged_commit("1.0")
        f.make_a_commit("+semver:major")
        f.make_a_commit()
        f.branch_to("release/2.0")
        f.assert_full_semver("2.0.0-beta.1+2", configuration)


def test_release_branch_with_a_commit_should_use_branch_name_version_despite_bump_in_previous_commit() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:major")
        f.make_a_commit()
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+3")


def test_release_branched_at_commit_with_semver_message_should_use_branch_name_version() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:major")
        f.branch_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1")


def test_feature_from_release_branch_should_not_reset_count() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_commit("initial")
        f.branch_to("develop")
        f.branch_to("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1", configuration)
        f.make_commits(10)
        f.assert_full_semver("2.0.0-beta.1+11", configuration)
        f.branch_to("feature/xxx")
        f.make_a_commit("feature 1")
        f.make_a_commit("feature 2")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+11", configuration)
        f.make_a_commit("release 11")
        f.assert_full_semver("2.0.0-beta.1+12", configuration)
        f.checkout("feature/xxx")
        f.make_a_commit("feature 3")
        f.checkout("release-2.0.0")
        f.assert_full_semver("2.0.0-beta.1+12", configuration)
        f.merge_no_ff("feature/xxx")
        f.assert_full_semver("2.0.0-beta.1+16", configuration)
        f.make_a_commit("release 13 - after feature merge")
        f.assert_full_semver("2.0.0-beta.1+17", configuration)


@pytest.mark.parametrize(("weight", "expected"), [(1000, "2.0.0.1001"), (None, "2.0.0.30001")])
def test_assembly_sem_file_ver_should_be_weighted_by_pre_release_weight(
    weight: int | None, expected: str
) -> None:
    branches = {"release": {"pre_release_weight": weight}} if weight is not None else None
    configuration = gitflow(
        branches=branches,
        assembly_file_versioning_format="{Major}.{Minor}.{Patch}.{WeightedPreReleaseNumber}",
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.branch_to("release-2.0.0")
        assert f.get_version(configuration)["AssemblySemFileVer"] == expected


@pytest.mark.parametrize("delete_feature", [True, False])
def test_feature_on_release_feature_branch(delete_feature: bool) -> None:
    configuration = gitflow(assembly_versioning_scheme="MajorMinorPatchTag")
    with Scenario() as f:
        f.make_a_commit("initial")
        f.branch_to("develop")
        f.branch_to("release/4.5.0")
        f.assert_full_semver("4.5.0-beta.1+1", configuration)
        f.branch_to("feature/some-bug-fix")
        f.make_a_commit("blabla")
        f.checkout("release/4.5.0")
        f.merge_no_ff("feature/some-bug-fix")
        if delete_feature:
            f.delete_branch("feature/some-bug-fix")
        f.assert_full_semver("4.5.0-beta.1+3", configuration)


@pytest.mark.parametrize(
    ("branch", "expected", "fmt"),
    [
        ("release/1.2.0", "1.2.0-beta.1+1", "Loose"),
        ("release/1.2.0", "1.2.0-beta.1+1", "Strict"),
        ("release/1.2", "1.2.0-beta.1+1", "Loose"),
        ("release/1", "1.0.0-beta.1+1", "Loose"),
    ],
)
def test_should_detect_version_in_release_branch(branch: str, expected: str, fmt: str) -> None:
    configuration = gitflow(semantic_version_format=fmt)
    with Scenario(branch) as f:
        f.make_a_commit()
        f.assert_full_semver(expected, configuration)
