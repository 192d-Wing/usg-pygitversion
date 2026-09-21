# SPDX-License-Identifier: MIT
"""Port of upstream ``CompareTheDifferentWhenUsingMainlineVersionStrategyWithGitFlow.cs`` (6.8.2).

Every scenario runs twice: once with the default GitFlow strategies and once
with ``Mainline``. Without Mainline the test tags each release manually. The
upstream file overloads ``EnsureReleaseAndFeatureBranch`` and
``EnsureReleaseBranch``; the two-argument overloads carry the
``_with_release_branch`` suffix here.
"""

from __future__ import annotations

import pytest
from usg_pygitversion.config.schema import GitVersionConfiguration

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def configuration_for(use_mainline: bool) -> GitVersionConfiguration:
    """``configurationBuilder.WithVersionStrategy(VersionStrategies.Mainline)`` or plain."""
    return gitflow(strategies=["Mainline"]) if use_mainline else gitflow()


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature(use_mainline: bool) -> None:
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
def test_ensure_merge_main_to_feature(use_mainline: bool) -> None:
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
def test_ensure_release_and_feature_branch(use_mainline: bool) -> None:
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
        (False, "release/0.0.2"),
        (True, "release/0.0.2"),
        (True, "release/0.1.0"),
    ],
)
def test_ensure_release_and_feature_branch_with_release_branch(
    use_mainline: bool, release_branch: str
) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to(release_branch)
        f.assert_full_semver("0.1.0-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-beta.1+1", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.1.0-foo.1+1", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.1.0-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-foo.1+3", c)
        f.apply_tag("0.1.0-foo.1")
        f.assert_full_semver("0.1.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.1.0-foo.2+1", c)
        f.checkout(release_branch)
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.1.0-PullRequest2.5", c)
        f.checkout("feature/foo")
        f.merge_to(release_branch)
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.1.0-beta.1+5", c)
        f.merge_to("main")
        f.delete_branch(release_branch)
        f.assert_full_semver("0.1.0-6", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("F")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_release_branch(use_mainline: bool) -> None:
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
        (True, "release/0.1.0"),
    ],
)
def test_ensure_release_branch_with_release_branch(use_mainline: bool, release_branch: str) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to(release_branch)
        f.assert_full_semver("0.1.0-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-beta.1+1", c)
        f.checkout("main")
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-1", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.merge_to(release_branch)
        f.assert_full_semver("0.1.0-beta.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-beta.1+3", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.1.0-beta.1+4", c)
        f.apply_tag("0.1.0-beta.1")
        f.assert_full_semver("0.1.0-beta.2+0", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.1.0-beta.2+1", c)
        f.merge_to("main")
        f.delete_branch(release_branch)
        f.assert_full_semver("0.1.0-6", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("G")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature_development_with_develop_branch(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.apply_tag("0.1.0-alpha.1")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.1.0-alpha.2", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.1.0-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-foo.1+3", c)
        f.apply_tag("0.1.0-foo.1")
        f.assert_full_semver("0.1.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.1.0-foo.2+1", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.1.0-foo.2+2", c)
        f.checkout("develop")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.1.0-PullRequest2.6", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("develop")
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.1.0-alpha.6", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("develop")
        f.assert_full_semver("0.1.0-PullRequest3.7", c)
        f.checkout("develop")
        f.delete_branch("pull/3/merge")
        f.merge_to("main")
        f.assert_full_semver("0.1.0-7", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("G")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature_development_with_develop_branch_fast(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.1.0-foo.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-foo.1+1", c)
        f.apply_tag("0.1.0-foo.1")
        f.assert_full_semver("0.1.0-foo.2+0", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.1.0-foo.2+1", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-foo.2+2", c)
        f.checkout("develop")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.1.0-PullRequest2.4", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("develop")
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.1.0-alpha.4", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("develop")
        f.assert_full_semver("0.1.0-PullRequest3.5", c)
        f.checkout("develop")
        f.delete_branch("pull/3/merge")
        f.merge_to("main")
        f.assert_full_semver("0.1.0-5", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("E")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_development_with_main_branch_fast(use_mainline: bool) -> None:
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
        f.apply_tag("0.0.2-foo.1")
        f.assert_full_semver("0.0.2-foo.2+0", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-foo.2+1", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2-foo.2+2", c)
        f.checkout("main")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.0.2-PullRequest2.4", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("main")
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.0.2-4", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_bug_fix_with_main_branch(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("hotfix/bar")
        f.assert_full_semver("0.0.2-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-beta.1+1", c)
        f.apply_tag("0.0.2-beta.1")
        f.assert_full_semver("0.0.2-beta.2+0", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-beta.2+1", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2-beta.2+2", c)
        f.checkout("main")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("hotfix/bar")
        f.assert_full_semver("0.0.2-PullRequest2.4", c)
        f.checkout("hotfix/bar")
        f.delete_branch("pull/2/merge")
        f.merge_to("main")
        f.delete_branch("hotfix/bar")
        f.assert_full_semver("0.0.2-4", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_bug_fix_with_develop_branch(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.branch_to("hotfix/foo")
        f.assert_full_semver("0.0.2-beta.1+1", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-beta.1+2", c)
        f.apply_tag("0.0.2-beta.1")
        f.assert_full_semver("0.0.2-beta.2+0", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2-beta.2+1", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.0.2-beta.2+2", c)
        f.checkout("develop")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("hotfix/foo")
        f.assert_full_semver("0.1.0-PullRequest2.5", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("hotfix/foo")
        f.assert_full_semver("0.0.2-PullRequest3.5", c)
        f.checkout("hotfix/foo")
        f.merge_to("main")
        f.delete_branch("hotfix/foo")
        f.assert_full_semver("0.0.2-5", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.make_a_commit("F")
        f.assert_full_semver("0.0.3-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_bug_fix_with_develop_branch_fast(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.branch_to("hotfix/foo")
        f.assert_full_semver("0.0.2-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.0.2-beta.1+1", c)
        f.apply_tag("0.0.2-beta.1")
        f.assert_full_semver("0.0.2-beta.2+0", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.0.2-beta.2+1", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.0.2-beta.2+2", c)
        f.checkout("develop")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("hotfix/foo")
        f.assert_full_semver("0.1.0-PullRequest2.4", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("hotfix/foo")
        # Upstream notes it expected "0.0.2-PullRequest3.4" but asserts this.
        f.assert_full_semver("0.1.0-PullRequest3.4", c)
        f.checkout("hotfix/foo")
        f.merge_to("main")
        f.delete_branch("hotfix/foo")
        f.assert_full_semver("0.0.2-4", c)
        if not use_mainline:
            f.apply_tag("0.0.2")
        f.make_a_commit("E")
        f.assert_full_semver("0.0.3-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature_development_with_release_next_branch(use_mainline: bool) -> None:  # noqa: PLR0915 -- mirrors the upstream walkthrough
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.branch_to("release/next")
        f.assert_full_semver("0.1.0-beta.1+1", c)
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("release/next")
        f.assert_full_semver("0.1.0-beta.1+1", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-beta.1+2", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.1.0-beta.1+3", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.1.0-foo.1+3", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-foo.1+4", c)
        f.apply_tag("0.1.0-foo.1")
        f.assert_full_semver("0.1.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.1.0-foo.2+1", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.1.0-foo.2+2", c)
        f.checkout("release/next")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.1.0-PullRequest2.7", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("release/next")
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.1.0-beta.1+7", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("release/next")
        f.assert_full_semver("0.1.0-PullRequest3.8", c)
        f.checkout("release/next")
        f.delete_branch("pull/3/merge")
        f.merge_to("main")
        f.delete_branch("release/next")
        f.assert_full_semver("0.1.0-8", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("G")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature_development_with_release_next_branch_fast(use_mainline: bool) -> None:
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.branch_to("release/next")
        f.assert_full_semver("0.1.0-beta.1+0", c)
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("release/next")
        f.assert_full_semver("0.1.0-beta.1+0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-beta.1+1", c)
        f.make_a_commit("C")
        f.assert_full_semver("0.1.0-beta.1+2", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("0.1.0-foo.1+2", c)
        f.make_a_commit("D")
        f.assert_full_semver("0.1.0-foo.1+3", c)
        f.apply_tag("0.1.0-foo.1")
        f.assert_full_semver("0.1.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("0.1.0-foo.2+1", c)
        f.make_a_commit("F")
        f.assert_full_semver("0.1.0-foo.2+2", c)
        f.checkout("release/next")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("0.1.0-PullRequest2.6", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("release/next")
        f.delete_branch("feature/foo")
        f.assert_full_semver("0.1.0-beta.1+6", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("release/next")
        f.assert_full_semver("0.1.0-PullRequest3.7", c)
        f.checkout("release/next")
        f.delete_branch("pull/3/merge")
        f.merge_to("main")
        f.delete_branch("release/next")
        f.assert_full_semver("0.1.0-7", c)
        if not use_mainline:
            f.apply_tag("0.1.0")
        f.make_a_commit("G")
        f.assert_full_semver("0.1.1-1", c)


@pytest.mark.parametrize("use_mainline", [False, True])
def test_ensure_feature_development_with_release100_branch(use_mainline: bool) -> None:  # noqa: PLR0915 -- mirrors the upstream walkthrough
    c = configuration_for(use_mainline)
    with Scenario() as f:
        f.make_a_commit("A")
        f.assert_full_semver("0.0.1-1", c)
        if not use_mainline:
            f.apply_tag("0.0.1")
        f.branch_to("develop")
        f.assert_full_semver("0.1.0-alpha.0", c)
        f.make_a_commit("B")
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.checkout("develop")
        f.make_a_commit()
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.make_a_commit("B")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.make_a_commit("C")
        f.assert_full_semver("1.0.0-beta.1+3", c)
        f.branch_to("feature/foo")
        f.assert_full_semver("1.0.0-foo.1+3", c)
        f.make_a_commit("D")
        f.assert_full_semver("1.0.0-foo.1+4", c)
        f.apply_tag("1.0.0-foo.1")
        f.assert_full_semver("1.0.0-foo.2+0", c)
        f.make_a_commit("E")
        f.assert_full_semver("1.0.0-foo.2+1", c)
        f.make_a_commit("F")
        f.assert_full_semver("1.0.0-foo.2+2", c)
        f.checkout("release/1.0.0")
        f.branch_to("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.assert_full_semver("1.0.0-PullRequest2.7", c)
        f.checkout("feature/foo")
        f.delete_branch("pull/2/merge")
        f.merge_to("release/1.0.0")
        f.delete_branch("feature/foo")
        f.assert_full_semver("1.0.0-beta.1+7", c)
        f.checkout("main")
        f.branch_to("pull/3/merge")
        f.merge_no_ff("release/1.0.0")
        f.assert_full_semver("1.0.0-PullRequest3.8", c)
        f.checkout("release/1.0.0")
        f.delete_branch("pull/3/merge")
        f.merge_to("main")
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.0.0-8", c)
        if not use_mainline:
            f.apply_tag("1.0.0")
        f.make_a_commit("G")
        f.assert_full_semver("1.0.1-1", c)
