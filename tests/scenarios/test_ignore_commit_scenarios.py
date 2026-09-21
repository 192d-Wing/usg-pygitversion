# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/IgnoreCommitScenarios.cs`` (6.8.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from usg_pygitversion.errors import RepositoryError

from tests.scenarios.dsl import Scenario, gitflow, githubflow, trunkbased

pytestmark = pytest.mark.scenario


def test_should_throw_when_all_commits_are_ignored() -> None:
    with Scenario() as f:
        sha = f.make_a_commit()
        before = (f.commit_date(sha) + timedelta(days=365)).isoformat()
        configuration = gitflow(ignore={"commits-before": before})
        with pytest.raises(RepositoryError, match=r"No commits found on the current branch\."):
            f.get_version(configuration)


@pytest.mark.parametrize(
    ("next_version", "expected"),
    [(None, "0.0.1-1"), ("0.0.1", "0.0.1-1"), ("0.1.0", "0.1.0-1"), ("1.0.0", "1.0.0-1")],
)
def test_should_not_fallback_to_base_version_when_all_commits_are_not_ignored(
    next_version: str | None, expected: str
) -> None:
    with Scenario() as f:
        sha = f.make_a_commit()
        before = (f.commit_date(sha) - timedelta(days=365)).isoformat()
        root: dict[str, Any] = {"ignore": {"commits-before": before}}
        if next_version is not None:
            root["next_version"] = next_version
        f.assert_full_semver(expected, gitflow(**root))


def test_trunk_based_with_commit_parameter_then_version_should_be_correct() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2", trunkbased(), commit_id=b)


def test_trunk_based_with_ignore_configuration_for_commit_then_version_should_be_correct() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.3", trunkbased(ignore={"sha": [b]}))


def test_trunk_based_with_ignore_configuration_for_commit_b_and_commit_parameter_a() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2", trunkbased(ignore={"sha": [b]}), commit_id=c)


def test_trunk_based_with_ignore_configuration_for_commit_c_and_commit_parameter_c_then_commit_b_used() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.assert_full_semver("0.0.2", trunkbased(ignore={"sha": [c]}), commit_id=c)


def test_trunk_based_with_ignore_configuration_for_tagged_commit_then_tag_should_be_ignored() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.apply_tag("1.0.0")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.3", trunkbased(ignore={"sha": [c]}))


def test_trunk_based_with_ignore_configuration_before_commit_with_tag_then_tag_should_be_ignored() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.apply_tag("1.0.0")
        f.make_a_commit("D")
        before = (f.commit_date(c) + timedelta(seconds=1)).isoformat()
        f.assert_full_semver("0.0.1", trunkbased(ignore={"commits-before": before}))


@pytest.mark.parametrize(("prevent", "expected"), [(False, "1.0.1-0"), (True, "1.0.0")])
def test_trunk_based_with_ignore_configuration_of_commit_b_then_tag_should_be_considered(
    prevent: bool, expected: str
) -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        f.apply_tag("1.0.0")
        b = f.make_a_commit("B")
        configuration = trunkbased(
            ignore={"sha": [b]},
            branches={
                "main": {
                    "increment": "Patch",
                    "prevent_increment": {"when_current_commit_tagged": prevent},
                    "mode": "ContinuousDelivery",
                }
            },
        )
        f.assert_full_semver(expected, configuration)


@pytest.mark.parametrize(("prevent", "expected"), [(False, "1.0.1-0"), (True, "1.0.0")])
def test_trunk_based_with_commit_parameter_b_then_tag_should_be_considered(
    prevent: bool, expected: str
) -> None:
    with Scenario() as f:
        a = f.make_a_commit("A")
        f.apply_tag("1.0.0")
        f.make_a_commit("B")
        configuration = trunkbased(
            branches={
                "main": {
                    "increment": "Patch",
                    "prevent_increment": {"when_current_commit_tagged": prevent},
                    "mode": "ContinuousDelivery",
                }
            }
        )
        f.assert_full_semver(expected, configuration, commit_id=a)


def test_github_flow_with_commit_parameter_then_version_should_be_correct() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.1-2", githubflow(), commit_id=b)


def test_github_flow_with_ignore_configuration_for_commit_then_version_should_be_correct() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.1-3", githubflow(ignore={"sha": [b]}))


def test_github_flow_with_ignore_configuration_for_commit_b_and_commit_parameter_a() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.1-2", githubflow(ignore={"sha": [b]}), commit_id=c)


def test_github_flow_with_ignore_configuration_for_commit_c_and_commit_parameter_c_then_commit_b_used() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.assert_full_semver("0.0.1-2", githubflow(ignore={"sha": [c]}), commit_id=c)


def test_github_flow_with_ignore_configuration_for_tagged_commit_then_tag_should_be_ignored() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.apply_tag("1.0.0")
        f.make_a_commit("D")
        f.assert_full_semver("0.0.1-3", githubflow(ignore={"sha": [c]}))


def test_github_flow_with_ignore_configuration_before_commit_with_tag_then_tag_should_be_ignored() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_commit("B")
        c = f.make_a_commit("C")
        f.apply_tag("1.0.0")
        f.make_a_commit("D")
        before = (f.commit_date(c) + timedelta(seconds=1)).isoformat()
        f.assert_full_semver("0.0.1-1", githubflow(ignore={"commits-before": before}))


@pytest.mark.parametrize(("prevent", "expected"), [(False, "1.0.1-0"), (True, "1.0.0")])
def test_github_flow_with_ignore_configuration_of_commit_b_then_tag_should_be_considered(
    prevent: bool, expected: str
) -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        f.apply_tag("1.0.0")
        b = f.make_a_commit("B")
        configuration = githubflow(
            ignore={"sha": [b]},
            branches={"main": {"prevent_increment": {"when_current_commit_tagged": prevent}}},
        )
        f.assert_full_semver(expected, configuration)


@pytest.mark.parametrize(("prevent", "expected"), [(False, "1.0.1-0"), (True, "1.0.0")])
def test_github_flow_with_commit_parameter_b_then_tag_should_be_considered(
    prevent: bool, expected: str
) -> None:
    with Scenario() as f:
        a = f.make_a_commit("A")
        f.apply_tag("1.0.0")
        f.make_a_commit("B")
        configuration = githubflow(
            branches={"main": {"prevent_increment": {"when_current_commit_tagged": prevent}}}
        )
        f.assert_full_semver(expected, configuration, commit_id=a)


def test_github_flow_with_ignore_configuration_for_path_then_version_should_be_correct() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.make_a_commit("C")
        f.make_a_commit("D")
        ignored_path = f.git("diff-tree", "--no-commit-id", "--name-only", "-r", b)
        f.assert_full_semver("0.0.1-3", githubflow(ignore={"paths": [ignored_path]}))


def test_github_flow_with_ignore_configuration_for_tagged_commit_path_then_tag_should_be_ignored() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit("A")
        b = f.make_a_commit("B")
        f.apply_tag("1.0.0")
        f.make_a_commit("C")
        ignored_path = f.git("diff-tree", "--no-commit-id", "--name-only", "-r", b)
        f.assert_full_semver("0.0.1-2", githubflow(ignore={"paths": [ignored_path]}))
