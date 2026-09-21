# SPDX-License-Identifier: MIT
"""Port of upstream ``CreatingAFeatureBranchFromAReleaseBranchScenario.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def _finish(f: Scenario, branch: str, merged: str, after_delete: str, after_commit: str) -> None:
    f.checkout("release/1.0.0")
    f.merge_no_ff(branch)
    f.assert_full_semver(merged, gitflow())
    f.delete_branch(branch)
    f.assert_full_semver(after_delete, gitflow())
    f.make_a_commit()
    f.assert_full_semver(after_commit, gitflow())


def test_feature_branched_from_main_and_first_release_but_not_second() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("1.0.0-just-a-test.1+1", c)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("0.0.1-2", c)
        f.branch_to("release/1.1.0")
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.checkout("feature/just-a-test")
        f.assert_full_semver("1.0.0-just-a-test.1+1", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-just-a-test.1+2", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        _finish(f, "feature/just-a-test", "1.0.0-beta.1+3", "1.0.0-beta.1+3", "1.0.0-beta.1+4")


def test_feature_not_like_release_when_branched_from_develop_and_first_release_but_not_second() -> (
    None
):
    c = gitflow()
    with Scenario("develop") as f:
        f.make_a_commit()
        f.assert_full_semver("0.1.0-alpha.1", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("1.1.0-just-a-test.1+0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.0", c)
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.branch_to("release/1.1.0")
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.checkout("feature/just-a-test")
        f.assert_full_semver("1.0.0-just-a-test.1+1", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-just-a-test.1+2", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        _finish(f, "feature/just-a-test", "1.0.0-beta.1+3", "1.0.0-beta.1+3", "1.0.0-beta.1+4")


def test_hotfix_branched_from_main_and_first_release_but_not_second() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.branch_to("hotfix/just-a-test")
        f.assert_full_semver("0.0.1-beta.1+1", c)
        f.checkout("main")
        f.make_a_commit()
        f.branch_to("release/1.1.0")
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.checkout("hotfix/just-a-test")
        f.assert_full_semver("0.0.1-beta.1+1", c)
        f.make_a_commit()
        f.assert_full_semver("0.0.1-beta.1+2", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        _finish(f, "hotfix/just-a-test", "1.0.0-beta.1+3", "1.0.0-beta.1+3", "1.0.0-beta.1+4")


def test_hotfix_branched_from_develop_and_first_release_but_not_second() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("develop")
        f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.branch_to("hotfix/just-a-test")
        f.assert_full_semver("0.0.1-beta.1+2", c)
        f.checkout("develop")
        f.make_a_commit()
        f.branch_to("release/1.1.0")
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.checkout("hotfix/just-a-test")
        f.assert_full_semver("0.0.1-beta.1+2", c)
        f.make_a_commit()
        f.assert_full_semver("0.0.1-beta.1+3", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        _finish(f, "hotfix/just-a-test", "1.0.0-beta.1+4", "1.0.0-beta.1+4", "1.0.0-beta.1+5")


@pytest.mark.parametrize(
    ("kind", "from_develop"),
    [("feature", False), ("feature", True), ("hotfix", False), ("hotfix", True)],
)
def test_branched_from_first_but_not_second_release_branch(kind: str, from_develop: bool) -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        if from_develop:
            f.branch_to("develop")
            f.make_a_commit()
        f.branch_to("release/1.0.0")
        f.make_a_commit()
        n = 3 if from_develop else 2
        f.assert_full_semver(f"1.0.0-beta.1+{n}", c)
        branch = f"{kind}/just-a-test"
        f.branch_to(branch)
        label = "just-a-test" if kind == "feature" else "beta"
        head = "1.0.0" if kind == "feature" else "0.0.1"
        f.assert_full_semver(f"{head}-{label}.1+{n}", c)
        f.checkout("main")
        f.make_a_commit()
        f.branch_to("release/1.1.0")
        f.checkout("release/1.0.0")
        f.assert_full_semver(f"1.0.0-beta.1+{n}", c)
        f.checkout(branch)
        f.assert_full_semver(f"{head}-{label}.1+{n}", c)
        f.make_a_commit()
        f.assert_full_semver(f"{head}-{label}.1+{n + 1}", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver(f"1.0.0-beta.1+{n}", c)
        _finish(
            f, branch, f"1.0.0-beta.1+{n + 2}", f"1.0.0-beta.1+{n + 2}", f"1.0.0-beta.1+{n + 3}"
        )


def test_feature_like_release_when_branched_from_release() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", c)
        f.branch_to("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+1", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-beta.1+2", c)
        f.branch_to("feature/just-a-test")
        f.assert_full_semver("1.0.0-just-a-test.1+2", c)
        f.make_a_commit()
        f.assert_full_semver("1.0.0-just-a-test.1+3", c)
        f.checkout("release/1.0.0")
        f.assert_full_semver("1.0.0-beta.1+2", c)
        _finish(f, "feature/just-a-test", "1.0.0-beta.1+4", "1.0.0-beta.1+4", "1.0.0-beta.1+5")


def test_merge_from_release_to_develop_like_release_never_existed_when_canceled() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", c)
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
        f.make_a_commit()
        f.assert_full_semver("1.1.0-alpha.7", c)


def test_only_track_commits_on_develop_for_next_release_when_release_shipped() -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", c)
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
        f.assert_full_semver("1.0.0-5", c)
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.merge_no_ff("main")
        f.assert_full_semver("1.1.0-alpha.2", c)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.1.0-alpha.2", c)


def test_should_not_consider_the_merge_commit_from_release_to_main_when_commit_has_not_been_tagged() -> (
    None
):
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", c)
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
        f.assert_full_semver("1.0.0-5", c)
        f.delete_branch("release/1.0.0")
        f.assert_full_semver("1.0.0-5", c)
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.checkout("develop")
        f.assert_full_semver("1.1.0-alpha.1", c)
        f.merge_no_ff("main")
        f.assert_full_semver("1.1.0-alpha.2", c)
