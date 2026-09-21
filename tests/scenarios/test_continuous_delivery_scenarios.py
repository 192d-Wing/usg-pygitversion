# SPDX-License-Identifier: MIT
"""Port of upstream ``ContinuousDeliveryTestScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario

_CD = {"mode": "ContinuousDelivery"}
_CI_MAIN = {"label": "ci", "mode": "ContinuousDelivery"}


def test_should_use_the_fallback_version_on_main_when_no_versions_are_available() -> None:
    c = gitflow(mode="ContinuousDelivery", branches={"main": _CI_MAIN})
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-ci.1", c)


def test_should_use_the_fallback_version_on_develop_when_no_versions_are_available() -> None:
    c = gitflow(mode="ContinuousDelivery")
    with Scenario("develop") as f:
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.1", c)


def test_should_use_configured_next_version_on_main_when_no_higher_versions_available() -> None:
    c = gitflow(next_version="1.0.0", mode="ContinuousDelivery", branches={"main": _CI_MAIN})
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("1.0.0-ci.1", c)


def test_should_not_matter_when_configured_next_version_is_equal_to_the_tagged_version() -> None:
    c = gitflow(next_version="1.0.0", mode="ContinuousDelivery")
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.assert_full_semver("1.0.0", c)


def test_should_use_tagged_version_when_greater_than_configured_next_version() -> None:
    c = gitflow(next_version="1.0.0", mode="ContinuousDelivery")
    with Scenario() as f:
        f.make_a_tagged_commit("1.1.0")
        f.assert_full_semver("1.1.0", c)


def test_should_calculate_the_correct_version_when_merging_from_main_to_feature_branch() -> None:
    c = gitflow(mode="ContinuousDelivery", branches={"main": _CI_MAIN, "feature": _CD})
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-ci.1", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("0.0.1-just-a-test.1", c)
        f.make_a_commit()
        f.assert_full_semver("0.0.1-just-a-test.2", c)
        f.checkout("main")
        f.assert_full_semver("0.0.1-ci.1", c)
        f.merge_no_ff("feature/just-a-test")
        f.assert_full_semver("0.0.1-ci.3", c)
        f.delete_branch("feature/just-a-test")
        f.assert_full_semver("0.0.1-ci.3", c)


def test_should_calculate_the_correct_version_when_merging_from_develop_to_feature_branch() -> None:
    c = gitflow(mode="ContinuousDelivery", branches={"develop": _CD, "feature": _CD})
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("0.1.0-just-a-test.1", c)
        f.make_a_commit()
        f.assert_full_semver("0.1.0-just-a-test.2", c)
        f.checkout("develop")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.merge_no_ff("feature/just-a-test")
        f.assert_full_semver("0.1.0-alpha.3", c)
        f.delete_branch("feature/just-a-test")
        f.assert_full_semver("0.1.0-alpha.3", c)


def test_should_calculate_the_correct_version_when_merging_from_release_to_feature_branch() -> None:
    c = gitflow(mode="ContinuousDelivery", branches={"main": _CD, "release": _CD, "feature": _CD})
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("1.0.0-just-a-test.1", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-just-a-test.2", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1", c)
        f.merge_no_ff("feature/just-a-test")
        f.assert_full_semver("1.0.0-beta.3", c)
        f.delete_branch("feature/just-a-test")
        f.assert_full_semver("1.0.0-beta.3", c)


_NO_TRACK = {"track_merge_target": False}


def test_should_fallback_to_the_version_on_develop_when_release_has_been_canceled() -> None:
    c = gitflow(
        branches={"main": {**_CI_MAIN, **_NO_TRACK}, "develop": _NO_TRACK, "release": _NO_TRACK}
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-ci.1", c)
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.2", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+3", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+4", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.4", c)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.6", c)


def test_should_consider_the_merge_commit_from_main_to_develop_when_release_merged_and_tagged() -> (
    None
):
    c = gitflow(
        branches={"main": {**_CI_MAIN, **_NO_TRACK}, "develop": _NO_TRACK, "release": _NO_TRACK}
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-ci.1", c)
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.2", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+3", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+4", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.checkout("main")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.0.0-ci.5", c)
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.merge_no_ff("main")
        f.assert_full_semver("1.1.0-alpha.2", c)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.2", c)
