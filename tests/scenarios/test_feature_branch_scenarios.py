# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/FeatureBranchScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_should_inherit_increment_correctly_with_multiple_possible_parents_and_weirdly_named_develop_branch() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("development")
        f.branch_to("feature/JIRA-123")
        f.make_commits(1)
        f.checkout("development")
        f.merge_ff("feature/JIRA-123")
        f.branch_to("feature/JIRA-124")
        f.make_commits(1)
        f.assert_full_semver("1.1.0-JIRA-124.1+2")


def test_branch_created_after_fast_forward_merge_should_inherit_correctly() -> None:
    configuration = gitflow(
        branches={
            "unstable": {
                "increment": "Minor",
                "regex": "unstable",
                "source_branches": [],
                "is_source_branch_for": ["feature"],
            }
        }
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("unstable")
        f.branch_to("feature/JIRA-123")
        f.make_commits(1)
        f.checkout("unstable")
        f.merge_ff("feature/JIRA-123")
        f.branch_to("feature/JIRA-124")
        f.make_commits(1)
        f.assert_full_semver("1.1.0-JIRA-124.1+2", configuration)


def test_should_not_use_number_in_feature_branch_as_pre_release_number_off_develop() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.branch_to("feature/JIRA-123")
        f.make_commits(5)
        f.assert_full_semver("1.1.0-JIRA-123.1+5")


def test_should_not_use_number_in_feature_branch_as_pre_release_number_off_main() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("feature/JIRA-123")
        f.make_commits(5)
        f.assert_full_semver("1.0.1-JIRA-123.1+5")


@pytest.mark.parametrize("branch", ["feature-test", "features/test"])
def test_feature_branch_naming_variants(branch: str) -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to(branch)
        f.make_commits(5)
        f.assert_full_semver("1.0.1-test.1+5")


def test_when_two_feature_branch_point_to_the_same_commit() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.branch_to("feature/feature1")
        f.make_a_commit()
        f.branch_to("feature/feature2")
        f.assert_full_semver("0.1.0-feature2.1+2")


def test_should_be_possible_to_merge_develop_for_a_long_running_branch_where_develop_and_main_are_equal() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("v1.0.0")
        f.branch_to("develop")
        f.branch_to("feature/longrunning")
        f.make_a_commit()
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("main")
        f.merge_ff("develop")
        f.apply_tag("v1.1.0")
        f.checkout("feature/longrunning")
        f.merge_ff("develop")
        configuration = gitflow(
            mode="ContinuousDelivery", branches={"feature": {"mode": "ContinuousDelivery"}}
        )
        f.assert_full_semver("1.2.0-longrunning.2", configuration)


def test_can_use_branch_name_off_a_release_branch() -> None:
    configuration = gitflow(
        branches={"release": {"label": "build"}, "feature": {"label": "{BranchName}"}}
    )
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/0.3.0")
        f.make_a_tagged_commit("v0.3.0-build.1")
        f.make_a_commit()
        f.branch_to("feature/PROJ-1")
        f.make_a_commit()
        f.assert_full_semver("0.3.0-PROJ-1.1+4", configuration)


@pytest.mark.parametrize(
    ("label", "feature_name", "regex", "expected_label"),
    [
        ("alpha", "JIRA-123", r"^features?[\/-](?<BranchName>.+)", "alpha"),
        ("alpha.{BranchName}", "JIRA-123", r"^features?[\/-](?<BranchName>.+)", "alpha.JIRA-123"),
        (
            "{BranchName}-of-task-number-{TaskNumber}",
            "4711_this-is-a-feature",
            r"^features?[\/-](?<TaskNumber>\d+)_(?<BranchName>.+)",
            "this-is-a-feature-of-task-number-4711",
        ),
        (
            "{BranchName}",
            "4711_this-is-a-feature",
            r"^features?[\/-](?<BranchName>.+)",
            "4711-this-is-a-feature",
        ),
        ("{BranchName}.xyz", "x_y.7.z", r"^features?[\/-](?<BranchName>.+)", "x-y-7-z.xyz"),
        (
            "{BranchName}",
            "yourname/dash-separated-words",
            r".*\/(?<BranchName>[^\/]+)$",
            "dash-separated-words",
        ),
        (
            "{X}.{Z}-{Y}.{X}-{Z}.{X}",
            "xxxyyz",
            r"^features?[\/-](?<X>x+)(?<Y>y+)(?<Z>z+)$",
            "xxx.z-yy.xxx-z.xxx",
        ),
    ],
)
def test_should_use_configured_label(
    label: str, feature_name: str, regex: str, expected_label: str
) -> None:
    configuration = gitflow(branches={"feature": {"label": label, "regex": regex}})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to(f"feature/{feature_name}")
        f.make_commits(5)
        f.assert_full_semver(f"1.0.1-{expected_label}.1+5", configuration)


def test_branch_created_after_finish_release_should_inherit_and_increment_from_last_main_commit_tag() -> (
    None
):
    with GitFlowScenario("0.1.0") as f:
        f.assert_full_semver("0.2.0-alpha.1")
        f.branch_to("release/0.2.0")
        f.assert_full_semver("0.2.0-beta.1+1")
        f.checkout("main")
        f.merge_no_ff("release/0.2.0")
        f.apply_tag("0.2.0")
        f.assert_full_semver("0.2.0")
        f.checkout("develop")
        f.merge_no_ff("release/0.2.0")
        # Upstream removes "release/2.0.0", which does not exist; the call is a no-op there.
        f.make_a_commit()
        f.assert_full_semver("0.3.0-alpha.1")
        f.branch_to("feature/TEST-1")
        f.make_a_commit()
        f.assert_full_semver("0.3.0-TEST-1.1+2")


def test_should_pick_up_version_from_develop_after_release_branch_created() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1")
        f.branch_to("feature/test")
        f.assert_full_semver("1.1.0-test.1+1")


def test_should_pick_up_version_from_develop_after_release_branch_merged_back() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("develop")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.2")
        f.branch_to("feature/test")
        f.assert_full_semver("1.1.0-test.1+2")


@pytest.mark.parametrize("feature_branch", ["feature/test", "misnamed"])
def test_when_main_tracks_release_branches_should_pick_up_version_from_main_after_release_branch_created(
    feature_branch: str,
) -> None:
    configuration = gitflow(branches={"main": {"tracks_release_branches": True}})
    label = feature_branch.rsplit("/", maxsplit=1)[-1]
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.0.1-1", configuration)
        f.branch_to(feature_branch)
        f.assert_full_semver(f"1.0.1-{label}.1+1", configuration)


@pytest.mark.parametrize("feature_branch", ["feature/test", "misnamed"])
def test_when_main_tracks_release_branches_should_pick_up_version_from_main_after_release_branch_merged_back(
    feature_branch: str,
) -> None:
    configuration = gitflow(branches={"main": {"tracks_release_branches": True}})
    label = feature_branch.rsplit("/", maxsplit=1)[-1]
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.0.1-2", configuration)
        f.branch_to(feature_branch)
        f.assert_full_semver(f"1.0.1-{label}.1+2", configuration)


def test_when_feature_branch_has_no_config_should_pick_up_version_from_develop_after_release_branch_created() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1")
        f.branch_to("misnamed")
        f.assert_full_semver("1.1.0-misnamed.1+1")


def test_when_feature_branch_has_no_config_should_pick_up_version_from_develop_after_release_branch_merged_back() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        f.checkout("develop")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.2")
        f.branch_to("misnamed")
        f.assert_full_semver("1.1.0-misnamed.1+2")


def test_pick_up_version_from_main_marked_with_is_tracks_release_branches() -> None:
    configuration = gitflow(
        mode="ManualDeployment",
        branches={
            "unknown": {"increment": "Patch", "tracks_release_branches": True},
            "main": {"label": "pre", "tracks_release_branches": True},
            "release": {"label": "rc"},
        },
    )
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/0.10.0")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("0.10.0-rc.1+3", configuration)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("0.10.1-pre.1+1", configuration)
        f.branch_to("MyFeatureD")
        f.assert_full_semver("0.10.1-MyFeatureD.1+1", configuration)


def test_should_have_a_greater_semver_after_develop_is_merged_into_feature() -> None:
    configuration = gitflow(
        assembly_versioning_scheme="Major",
        assembly_file_versioning_format="{MajorMinorPatch}.{env:WeightedPreReleaseNumber ?? 0}",
        commit_message_incrementing="Disabled",
        branches={
            "main": {"mode": "ContinuousDelivery"},
            "develop": {"prevent_increment": {"of_merged_branch": True}},
            "feature": {"label": "feat-{BranchName}", "mode": "ContinuousDelivery"},
        },
    )
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.apply_tag("16.23.0")
        f.make_a_commit()
        f.branch_to("feature/featX")
        f.make_a_commit()
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("feature/featX")
        f.merge_no_ff("develop")
        f.assert_full_semver("16.24.0-feat-featX.4", configuration)
