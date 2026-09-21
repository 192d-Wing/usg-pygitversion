# SPDX-License-Identifier: MIT
"""Port of upstream ``CompareTheDifferentWhenUsingMainlineVersionStrategyWithGitHubFlow.cs`` (6.8.2).

Every scenario runs twice: once with the default GitHubFlow strategies and
once with ``Mainline``. Without Mainline the test tags each release manually.
"""

from __future__ import annotations

import pytest
from pygitversion.config.schema import GitVersionConfiguration

from tests.scenarios.dsl import Scenario, githubflow

pytestmark = pytest.mark.scenario


def configuration_for(use_mainline: bool) -> GitVersionConfiguration:
    """``configurationBuilder.WithVersionStrategy(VersionStrategies.Mainline)`` or plain."""
    return githubflow(strategies=["Mainline"]) if use_mainline else githubflow()


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature1(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-1", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.branch_to("feature/foo")
        f.assert_full_semver("0.0.3-foo.1+0", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.3-foo.1+1", c)
        f.apply_tag("0.0.3-foo.1")
        f.assert_full_semver("0.0.3-foo.2+0", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.3-foo.2+1", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.0.3-foo.2+2", c)
        f.merge_to("main")
        f.assert_full_semver("0.0.3-4", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_merge_main_to_feature2(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("feature/foo")
        f.assert_full_semver("0.0.2-foo.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-foo.1+1", c)
        f.checkout("main")
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-1", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.merge_to("feature/foo")
        f.assert_full_semver("0.0.3-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.3-foo.1+3", c)
        f.apply_tag("0.0.3-foo.1")
        f.assert_full_semver("0.0.3-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.0.3-foo.2+1", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-foo.2+2", c)
        f.merge_to("main")
        f.assert_full_semver("0.0.3-6", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_pull_request(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("feature/foo")
        f.assert_full_semver("0.0.2-foo.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-foo.1+1", c)
        f.checkout("main")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.0.2-PullRequest2.2", c)
        f.checkout("main")
        f.delete_branch("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.0.2-2", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_release_and_feature_branch1(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("2.0.0-beta.1+1", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("2.0.0-foo.1+1", c)
        f.make_a_commit("C")
        f.assert_full_semver("2.0.0-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("2.0.0-foo.1+3", c)
        f.apply_tag("2.0.0-foo.1")
        f.assert_full_semver("2.0.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("2.0.0-foo.2+1", c)
        f.checkout("release/2.0.0")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("2.0.0-PullRequest2.5", c)
        f.checkout("feature/foo")
        f.merge_to("release/2.0.0")
        f.delete_branch("feature/foo")
        f.assert_full_semver("2.0.0-beta.1+5", c)
        f.merge_to("main")
        f.delete_branch("release/2.0.0")
        f.assert_full_semver("2.0.0-6", c)
        if not use_mainline:
            f.apply_tag("2.0.0")
        f.make_a_commit("F")
        f.assert_full_semver("2.0.1-1", c)


@pytest.mark.parametrize(
    ("use_mainline", "release_branch"),
    [
        (False, "release/next"),
        (True, "release/next"),
        (False, "release/0.0.0"),
        (True, "release/0.0.0"),
        (False, "release/0.0.1"),
        (True, "release/0.0.1"),
        (True, "release/0.0.2"),
    ],
)
def test_ensure_release_and_feature_branch2(use_mainline: bool, release_branch: str) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to(release_branch)
        f.assert_full_semver("0.0.2-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-beta.1+1", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.0.2-foo.1+1", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2-foo.1+3", c)
        f.apply_tag("0.0.2-foo.1")
        f.assert_full_semver("0.0.2-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.0.2-foo.2+1", c)
        f.checkout(release_branch)
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.0.2-PullRequest2.5", c)
        f.checkout("feature/foo")
        f.merge_to(release_branch)
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.0.2-beta.1+5", c)
        f.merge_to("main")
        f.delete_branch(release_branch)
        f.assert_full_semver("0.0.2-6", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_release_branch1(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("2.0.0-beta.1+1", c)
        f.checkout("main")
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-1", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.merge_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("2.0.0-beta.1+3", c)
        f.make_a_commit("E")
        f.assert_full_semver("2.0.0-beta.1+4", c)
        f.apply_tag("2.0.0-beta.1")
        f.assert_full_semver("2.0.0-beta.2+0", c)
        f.make_a_commit("F")
        f.assert_full_semver("2.0.0-beta.2+1", c)
        f.merge_to("main")
        f.delete_branch("release/2.0.0")
        f.assert_full_semver("2.0.0-6", c)
        if not use_mainline:
            f.apply_tag("2.0.0")
        f.make_a_commit("G")
        f.assert_full_semver("2.0.1-1", c)


@pytest.mark.parametrize(
    ("use_mainline", "release_branch"),
    [
        (False, "release/next"),
        (True, "release/next"),
        (False, "release/0.0.0"),
        (True, "release/0.0.0"),
        (False, "release/0.0.1"),
        (True, "release/0.0.1"),
        (False, "release/0.0.2"),
        (True, "release/0.0.2"),
    ],
)
def test_ensure_release_branch2(use_mainline: bool, release_branch: str) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to(release_branch)
        f.assert_full_semver("0.0.2-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-beta.1+1", c)
        f.checkout("main")
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-1", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.merge_to(release_branch)
        f.assert_full_semver("0.0.3-beta.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.3-beta.1+3", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.0.3-beta.1+4", c)
        f.apply_tag("0.0.3-beta.1")
        f.assert_full_semver("0.0.3-beta.2+0", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-beta.2+1", c)
        f.merge_to("main")
        f.delete_branch(release_branch)
        f.assert_full_semver("0.0.3-6", c)
        if not use_mainline:
            f.apply_tag("0.0.3")
        f.make_a_commit("G")
        f.assert_full_semver("0.0.4-1", c)
