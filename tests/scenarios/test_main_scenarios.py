# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/MainScenarios.cs`` (GitVersion 6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_can_handle_manual_deployment() -> None:
    with Scenario() as f:
        configuration = gitflow(branches={"main": {"mode": "ManualDeployment"}})
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(2)
        f.assert_full_semver("1.0.1-1+2", configuration)


def test_can_handle_continuous_delivery() -> None:
    with Scenario() as f:
        configuration = gitflow(branches={"main": {"label": "ci", "mode": "ContinuousDelivery"}})
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(2)
        f.assert_full_semver("1.0.1-ci.2", configuration)


def test_can_handle_continuous_deployment() -> None:
    with Scenario() as f:
        configuration = gitflow(branches={"main": {"label": "ci", "mode": "ContinuousDeployment"}})
        f.make_a_tagged_commit("1.0.0")
        f.make_commits(2)
        f.assert_full_semver("1.0.1", configuration)


def test_given_a_repository_with_commits_but_no_tags_version_should_be_01() -> None:
    with Scenario() as f:
        f.make_commits(3)
        f.assert_full_semver("0.0.1-3")


def test_given_a_repository_with_commits_but_bad_tags_version_should_be_01() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("BadTag")
        f.make_commits(2)
        f.assert_full_semver("0.0.1-3")


def test_given_a_repository_with_commits_but_no_tags_with_detached_head_version_should_be_01() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("one")
        f.make_a_commit("two")
        commit = f.make_a_commit("three")
        f.make_a_commit()
        f.checkout(commit)
        f.assert_full_semver("0.0.1-3", only_tracked_branches=False)


def test_given_a_repository_with_tag_and_next_version_in_config_version_should_match() -> None:
    with Scenario() as f:
        configuration = gitflow(next_version="1.1.0")
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.assert_full_semver("1.1.0-5", configuration)


def test_given_a_repository_with_tag_and_a_next_version_and_no_commits_version_should_be_tag() -> (
    None
):
    with Scenario() as f:
        configuration = gitflow(next_version="1.1.0")
        f.make_a_tagged_commit("1.0.3")
        f.assert_full_semver("1.0.3")
        f.assert_full_semver("1.0.3", configuration)


def test_given_a_repository_with_tag_and_a_next_version_and_no_commits_version_should_be_tag2() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_a_commit()
        f.assert_full_semver("1.0.4-1")
        f.assert_full_semver("1.1.0-1", gitflow(next_version="1.1.0"))


def test_given_a_repository_with_tag_and_a_next_version_and_no_commits_version_should_be_tag3() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.assert_full_semver("1.0.3")
        f.assert_full_semver("1.0.3", gitflow(next_version="1.0.2"))


def test_given_a_repository_with_tag_and_a_next_version_and_no_commits_version_should_be_tag4() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_a_commit()
        f.assert_full_semver("1.0.4-1")
        f.assert_full_semver("1.0.4-1", gitflow(next_version="1.0.4"))


def test_given_a_repository_with_tag_and_no_next_version_version_should_be_tag_with_bumped_patch() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.make_commits(5)
        f.assert_full_semver("1.0.4-5")


def test_given_a_repository_with_tag_and_no_next_version_and_no_commits_version_should_be_tag() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.3")
        f.assert_full_semver("1.0.3")


def test_given_a_repository_with_tag_and_old_next_version_config_version_should_be_tag_with_bumped_patch() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.1.0")
        f.make_commits(5)
        f.assert_full_semver("1.1.1-5", gitflow(next_version="1.0.0"))


def test_given_a_repository_with_tag_and_old_next_version_config_and_no_commits_version_should_be_tag() -> (
    None
):
    with Scenario() as f:
        f.make_a_tagged_commit("1.1.0")
        f.assert_full_semver("1.1.0", gitflow(next_version="1.0.0"))


def test_can_specify_tag_prefixes() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("version-1.0.3")
        f.make_commits(5)
        f.assert_full_semver("1.0.4-5", gitflow(tag_prefix="version-"))


def test_can_specify_tag_prefixes_as_regex() -> None:
    with Scenario() as f:
        configuration = gitflow(tag_prefix="version-|[vV]?")
        f.make_a_tagged_commit("v1.0.3")
        f.make_commits(5)
        f.assert_full_semver("1.0.4-5", configuration)
        f.make_a_tagged_commit("version-1.0.5")
        f.make_commits(5)
        f.assert_full_semver("1.0.6-5", configuration)


def test_are_tags_not_adhering_to_tag_prefix_ignored() -> None:
    with Scenario() as f:
        configuration = gitflow(tag_prefix="")
        f.make_a_tagged_commit("version-1.0.3")
        f.make_commits(5)
        f.assert_full_semver("0.0.1-6", configuration)
        f.make_a_tagged_commit("bad/1.0.3")
        f.assert_full_semver("0.0.1-7", configuration)


def test_next_version_should_be_considered_on_the_development_branch() -> None:
    with Scenario("develop") as f:
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.1", gitflow())
        f.assert_full_semver("1.0.0-alpha.1", gitflow(next_version="1.0.0"))
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.2", gitflow())
        f.assert_full_semver("1.0.0-alpha.2", gitflow(next_version="1.0.0"))


def test_prevent_decrementation_of_versions_on_the_development_branch() -> None:
    with Scenario("develop") as f:
        configuration = gitflow(next_version="1.0.0")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", configuration)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", configuration)
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
        f.assert_full_semver("1.1.0-alpha.1", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.2", configuration)
        f.checkout("release/1.0.0")
        f.merge_no_ff("develop")
        f.assert_full_semver("1.0.0-beta.2+3", configuration)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", configuration)
        f.checkout("release/1.0.0")
        f.apply_tag("1.0.0-beta.2")
        f.assert_full_semver("1.0.0-beta.3+0", configuration)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", configuration)
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.3", configuration)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.6", configuration)
        f.git("tag", "-d", "1.0.0-beta.1")
        f.git("tag", "-d", "1.0.0-beta.2")
        f.assert_full_semver("1.1.0-alpha.6", configuration)
        f.assert_full_semver("1.1.0-alpha.6", gitflow(next_version="1.1.0"))


@pytest.mark.parametrize(
    ("track_merge_message", "expected"), [(True, "1.1.0-4"), (False, "1.0.1-4")]
)
def test_track_merge_message_should_be_considered_on_the_main_branch(
    track_merge_message: bool, expected: str
) -> None:
    with Scenario() as f:
        configuration = gitflow(branches={"main": {"track_merge_message": track_merge_message}})
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("release/1.1.0")
        f.make_a_commit()
        f.make_a_commit()
        f.assert_full_semver("1.1.0-beta.1+2", configuration)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.0.1-1", configuration)
        f.merge_no_ff("release/1.1.0")
        f.assert_full_semver(expected, configuration)
        f.delete_branch("release/1.1.0")
        f.assert_full_semver(expected, configuration)
