# SPDX-License-Identifier: MIT
"""Ports of the smaller upstream suites (6.8.2).

Covers OtherBranchScenarios, FallbackVersionStrategyScenarios,
GitflowScenarios, TagCheckoutScenarios, BranchWithoutCommitScenarios,
SwitchingToGitFlowScenarios and
SemVerOfAFeatureBranchStartedFromAReleaseBranchGetsDecrementedScenario.
"""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow, githubflow

pytestmark = pytest.mark.scenario


# -- OtherBranchScenarios ------------------------------------------------------


@pytest.mark.parametrize(
    ("tag_prefix", "first_tag", "after_first", "second_tag", "after_second", "after_commit"),
    [
        ("", "NotAVersion", "2.0.0-1", "1.9.0", "1.9.0", "1.9.1-1"),
        ("", "1.5.0", "1.5.0", "1.9.0", "1.9.0", "1.9.1-1"),
        ("prefix", "1.5.0", "2.0.0-1", "1.9.0", "2.0.0-1", "2.0.0-2"),
        ("prefix", "1.5.0", "2.0.0-1", "prefix1.9.0", "1.9.0", "1.9.1-1"),
        ("prefix", "prefix1.5.0", "1.5.0", "1.9.0", "1.5.0", "1.5.1-1"),
    ],
)
def test_can_use_commit_messages_to_bump_version_tags_take_priority_only_if_versions(
    tag_prefix: str,
    first_tag: str,
    after_first: str,
    second_tag: str,
    after_second: str,
    after_commit: str,
) -> None:
    configuration = gitflow(tag_prefix=tag_prefix)
    with Scenario() as f:
        f.make_a_tagged_commit(f"{tag_prefix}1.0.0")
        f.make_a_commit("+semver:major")
        f.assert_full_semver("2.0.0-1", configuration)
        f.apply_tag(first_tag)
        f.assert_full_semver(after_first, configuration)
        f.apply_tag(second_tag)
        f.assert_full_semver(after_second, configuration)
        f.make_a_commit()
        f.assert_full_semver(after_commit, configuration)


@pytest.mark.parametrize(
    ("tag_prefix", "label", "tag", "expected_before", "expected_after"),
    [
        ("", None, "1.9.0-1", "2.0.0-1+1", "1.9.0-1"),
        ("", "", "1.9.0-1", "2.0.0-1+1", "1.9.0-1"),
        ("", "foo", "1.9.0-1", "2.0.0-foo.1+1", "2.0.0-foo.1+1"),
        ("", "bar", "1.9.0-1", "2.0.0-bar.1+1", "2.0.0-bar.1+1"),
        ("prefix", None, "1.9.0-1", "2.0.0-1+1", "2.0.0-1+1"),
        ("prefix", "", "1.9.0-1", "2.0.0-1+1", "2.0.0-1+1"),
        ("prefix", "foo", "1.9.0-1", "2.0.0-foo.1+1", "2.0.0-foo.1+1"),
        ("prefix", "bar", "1.9.0-1", "2.0.0-bar.1+1", "2.0.0-bar.1+1"),
        ("", None, "2.1.0-1", "2.0.0-1+1", "2.1.0-1"),
        ("", "", "2.1.0-1", "2.0.0-1+1", "2.1.0-1"),
        ("", "foo", "2.1.0-1", "2.0.0-foo.1+1", "2.1.0-foo.1+1"),
        ("", "bar", "2.1.0-1", "2.0.0-bar.1+1", "2.1.0-bar.1+1"),
        ("prefix", None, "2.1.0-1", "2.0.0-1+1", "2.0.0-1+1"),
        ("prefix", "", "2.1.0-1", "2.0.0-1+1", "2.0.0-1+1"),
        ("prefix", "foo", "2.1.0-1", "2.0.0-foo.1+1", "2.0.0-foo.1+1"),
        ("prefix", "bar", "2.1.0-1", "2.0.0-bar.1+1", "2.0.0-bar.1+1"),
    ],
)
def test_when_tagging_a_commit_as_pre_release(
    tag_prefix: str, label: str | None, tag: str, expected_before: str, expected_after: str
) -> None:
    configuration = gitflow(
        label=None,
        tag_prefix=tag_prefix,
        branches={"main": {"label": label, "mode": "ManualDeployment"}},
    )
    with Scenario() as f:
        f.make_a_tagged_commit(f"{tag_prefix}1.0.0")
        f.make_a_commit("+semver:major")
        f.assert_full_semver(expected_before, configuration)
        f.apply_tag(tag)
        assert f.get_version(configuration)["FullSemVer"] == expected_after


def test_should_only_consider_tags_matching_of_current_branch() -> None:
    configuration = gitflow(branches={"develop": {"label": "snapshot"}, "release": {"label": "rc"}})
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.make_a_tagged_commit("0.1.2-snapshot.2")
        f.branch_to("release/0.1.2")
        f.assert_full_semver("0.1.2-rc.1+3", configuration)


def test_can_take_version_from_release_branch_with_custom_regex() -> None:
    configuration = gitflow(
        branches={"release": {"label": "{BranchName}", "regex": "(?<BranchName>.+)"}}
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.branch_to("release/2.0.0-LTS")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-LTS.1+6", configuration)


def test_can_take_version_from_hotfix_branch_with_custom_regex() -> None:
    configuration = gitflow(
        branches={"hotfix": {"label": "{BranchName}", "regex": "(?<BranchName>.+)"}}
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.branch_to("hotfix/1.0.5-LTS")
        f.make_a_commit()
        f.assert_full_semver("1.0.5-LTS.1+1", configuration)


def test_branches_with_illegal_chars_should_not_be_used_in_version_names() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.branch_to("issue/m/github-569")
        f.assert_full_semver("1.0.4-issue-m-github-569.1+5")


def test_should_not_get_version_from_feature_branch_if_not_merged() -> None:
    configuration = gitflow(branches={"develop": {"track_merge_target": False}})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0-unstable.0")
        f.branch_to("feature")
        f.make_a_tagged_commit("1.0.1-feature.1")
        f.checkout("main")
        f.branch_to("develop")
        f.make_a_commit()
        f.assert_full_semver("1.0.0-alpha.2", configuration)


@pytest.mark.parametrize(
    ("label", "branch_name", "expected"),
    [("alpha", "JIRA-123", "alpha"), ("alpha.{BranchName}", "JIRA-123", "alpha.JIRA-123")],
)
def test_label_is_branch_name_for_branches_without_prefixed_branch_name(
    label: str, branch_name: str, expected: str
) -> None:
    configuration = gitflow(
        branches={
            "other": {
                "increment": "Patch",
                "regex": "(?<BranchName>.+)",
                "source_branches": [],
                "label": label,
            }
        }
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to(branch_name)
        f.make_commits(5)
        f.assert_full_semver(f"1.0.1-{expected}.5", configuration)


# -- FallbackVersionStrategyScenarios ------------------------------------------


def _fallback(**main: object) -> object:
    return githubflow(
        strategies=["Fallback"], branches={"main": {"mode": "ManualDeployment", **main}}
    )


@pytest.mark.parametrize(
    ("increment", "expected"),
    [("None", "0.0.0-1+1"), ("Patch", "0.0.1-1+1"), ("Minor", "0.1.0-1+1"), ("Major", "1.0.0-1+1")],
)
def test_ensure_version_increment_on_main_will_be_used(increment: str, expected: str) -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver(expected, _fallback(increment=increment))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("increment", "expected"),
    [("None", "0.0.0-1+1"), ("Patch", "0.0.1-1+1"), ("Minor", "0.1.0-1+1"), ("Major", "1.0.0-1+1")],
)
def test_ensure_version_increment_on_message_will_be_used(increment: str, expected: str) -> None:
    with Scenario() as f:
        f.make_a_commit(f"+semver: {increment}")
        f.assert_full_semver(expected, _fallback(increment="None"))  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", [False, True])
def test_take_the_latest_commit_as_base_version(mode: bool) -> None:
    configuration = _fallback(
        increment="Major", track_merge_target=True, tracks_release_branches=False
    )
    with Scenario() as f:
        f.make_a_commit("A")
        f.branch_to("release/foo")
        f.checkout("main")
        f.make_a_commit("B")
        if mode:
            f.merge_to("release/foo")
            f.apply_tag("0.0.0")
            f.checkout("main")
        else:
            f.apply_tag("0.0.0")
        f.make_a_commit("C")
        if mode:
            f.apply_tag("0.0.1")
        else:
            f.merge_to("release/foo")
            f.apply_tag("0.0.1")
            f.checkout("main")
        f.make_a_commit("D")
        f.assert_full_semver("1.0.0-1+1", configuration)  # type: ignore[arg-type]


@pytest.mark.parametrize(("tracks", "expected"), [(False, "1.0.0-1+4"), (True, "1.0.0-1+2")])
def test_take_the_commit_branched_from_as_base_version_when_tracks_release_branches_is_true(
    tracks: bool, expected: str
) -> None:
    configuration = _fallback(
        increment="Major", track_merge_target=False, tracks_release_branches=tracks
    )
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        f.branch_to("release/foo")
        f.checkout("main")
        f.make_a_commit("C")
        f.checkout("release/foo")
        f.make_a_commit("D")
        f.apply_tag("0.0.0")
        f.checkout("main")
        f.make_a_commit("D")
        f.assert_full_semver(expected, configuration)  # type: ignore[arg-type]


# -- GitflowScenarios ----------------------------------------------------------


def test_gitflow_complex_example() -> None:  # noqa: PLR0915 -- mirrors the upstream walkthrough
    with GitFlowScenario("1.0.0") as f:
        f.assert_full_semver("1.1.0-alpha.1")
        f.branch_to("feature/f1")
        f.make_a_commit("added feature 1")
        f.assert_full_semver("1.1.0-f1.1+2")
        f.checkout("develop")
        f.merge_no_ff("feature/f1")
        f.delete_branch("feature/f1")
        f.assert_full_semver("1.1.0-alpha.3")
        f.branch_to("release/1.1.0")
        f.make_a_commit("release stabilization")
        f.assert_full_semver("1.1.0-beta.1+4")
        f.checkout("main")
        f.merge_no_ff("release/1.1.0")
        f.assert_full_semver("1.1.0-5")
        f.apply_tag("1.1.0")
        f.assert_full_semver("1.1.0")
        f.checkout("develop")
        f.merge_no_ff("release/1.1.0")
        f.delete_branch("release/1.1.0")
        f.assert_full_semver("1.2.0-alpha.1")
        f.branch_to("feature/f2")
        f.make_a_commit("added feature 2")
        f.assert_full_semver("1.2.0-f2.1+2")
        f.checkout("develop")
        f.merge_no_ff("feature/f2")
        f.delete_branch("feature/f2")
        f.assert_full_semver("1.2.0-alpha.3")
        f.branch_to("release/1.2.0")
        f.make_a_commit("release stabilization")
        f.assert_full_semver("1.2.0-beta.1+8")
        f.checkout("main")
        f.merge_no_ff("release/1.2.0")
        f.assert_full_semver("1.2.0-5")
        f.apply_tag("1.2.0")
        f.assert_full_semver("1.2.0")
        f.checkout("develop")
        f.merge_no_ff("release/1.2.0")
        f.delete_branch("release/1.2.0")
        f.assert_full_semver("1.3.0-alpha.1")
        f.checkout("main")
        f.branch_to("hotfix/hf")
        f.make_a_commit("added hotfix")
        f.assert_full_semver("1.2.1-beta.1+1")
        f.checkout("main")
        f.merge_no_ff("hotfix/hf")
        f.assert_full_semver("1.2.1-2")
        f.apply_tag("1.2.1")
        f.assert_full_semver("1.2.1")
        f.checkout("develop")
        f.merge_no_ff("hotfix/hf")
        f.delete_branch("hotfix/hf")
        f.assert_full_semver("1.3.0-alpha.2")


# -- TagCheckoutScenarios ------------------------------------------------------


def test_given_a_repository_with_single_commit_checked_out_at_tag() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.checkout("1.0.3")
        f.assert_full_semver("1.0.3")


def test_given_a_repository_with_single_commit_and_single_branch_checked_out_at_tag() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.branch_to("task1")
        f.checkout("1.0.3")
        f.assert_full_semver("1.0.3")


def test_given_a_repository_with_two_tags_and_a_develop_branch() -> None:
    with Scenario() as f:
        f.make_a_commit("init main")
        f.apply_tag("1.0")
        f.make_a_commit("hotfix")
        f.apply_tag("1.0.1")
        f.branch_to("develop")
        f.make_a_commit("new feature")
        f.checkout("1.0.1")
        f.branch_to("tags/1.0.1")
        f.assert_full_semver("1.0.1")


# -- BranchWithoutCommitScenarios ----------------------------------------------


def test_can_take_version_from_release_branch_without_commit() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        commit = f.make_a_commit()
        f.create_branch("release-4.0.123")
        f.checkout(commit)
        f.assert_full_semver(
            "4.0.123-beta.1+1",
            None,
            commit_id=commit,
            only_tracked_branches=False,
            target_branch="release-4.0.123",
        )


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("0.1.0-alpha.1", "1.0.0-beta.1+2"),
        ("1.0.0-alpha.1", "1.0.0-beta.1+2"),
        ("1.0.1-alpha.1", "1.0.1-beta.1+2"),
    ],
)
def test_branch_version_have_precedence_over_tag_version_if_version_greater_than_tag(
    tag: str, expected: str
) -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_tagged_commit(tag)
        f.branch_to("release/1.0.0")
        f.assert_full_semver(expected)


# -- SwitchingToGitFlowScenarios -----------------------------------------------


def test_when_develop_branched_from_main_with_legacy_version_tags_develop_can_use_reachable_tag() -> (
    None
):
    with Scenario() as f:
        f.make_commits(5)
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(2)
        f.branch_to("develop")
        f.assert_full_semver("1.1.0-alpha.2")


# -- SemVerOfAFeatureBranchStartedFromAReleaseBranchGetsDecrementedScenario ----


def test_should_pick_up_release_version_after_created_from_release() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.branch_to("release/1.1.0")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-beta.1+2")
        f.branch_to("feature/test")
        f.make_a_commit()
        f.assert_full_semver("1.1.0-test.1+3")
