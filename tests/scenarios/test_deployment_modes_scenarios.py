# SPDX-License-Identifier: MIT
"""Port of upstream ``ComparingTheBehaviorOfDifferentVersioningModes.cs`` (6.8.2)."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from pygitversion.config import GitVersionConfiguration

from tests.scenarios.dsl import Scenario, githubflow

pytestmark = pytest.mark.scenario


def _mode(mode: str) -> GitVersionConfiguration:
    return githubflow(
        label=None,
        mode=mode,
        branches={
            "main": {"increment": "Patch", "label": None, "is_main_branch": True, "mode": mode},
            "feature": {
                "increment": "Inherit",
                "label": "{BranchName}",
                "is_main_branch": False,
                "mode": mode,
            },
        },
    )


CD = _mode("ContinuousDeployment")
CDELIVERY = _mode("ContinuousDelivery")
MANUAL = _mode("ManualDeployment")


def _assert_all(f: Scenario, expected: Mapping[str, str]) -> None:
    f.assert_full_semver(expected["cd"], CD)
    f.assert_full_semver(expected["delivery"], CDELIVERY)
    f.assert_full_semver(expected["manual"], MANUAL)


def _e(cd: str, delivery: str, manual: str) -> dict[str, str]:
    return {"cd": cd, "delivery": delivery, "manual": manual}


def test_expected_behavior() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        _assert_all(f, _e("1.0.0", "1.0.0", "1.0.0"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-1", "1.0.1-1+1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-2", "1.0.1-1+2"))
        f.apply_tag("1.0.1-alpha.1")
        _assert_all(f, _e("1.0.1", "1.0.1-alpha.1", "1.0.1-alpha.1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-alpha.2", "1.0.1-alpha.2+1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-alpha.3", "1.0.1-alpha.2+2"))
        f.make_a_tagged_commit("1.0.1-beta.1")
        _assert_all(f, _e("1.0.1", "1.0.1-beta.1", "1.0.1-beta.1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-beta.2", "1.0.1-beta.2+1"))
        f.make_a_tagged_commit("1.0.1-beta.2")
        _assert_all(f, _e("1.0.1", "1.0.1-beta.2", "1.0.1-beta.2"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.1", "1.0.1-beta.3", "1.0.1-beta.3+1"))
        f.apply_tag("1.0.1")
        _assert_all(f, _e("1.0.1", "1.0.1", "1.0.1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.2", "1.0.2-1", "1.0.2-1+1"))
        f.apply_tag("1.0.2-1")
        _assert_all(f, _e("1.0.2", "1.0.2-1", "1.0.2-1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.2", "1.0.2-2", "1.0.2-2+1"))
        f.make_a_commit()
        _assert_all(f, _e("1.0.2", "1.0.2-3", "1.0.2-2+2"))


def test_main_release() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        _assert_all(f, _e("0.0.2", "0.0.2", "0.0.2"))


def test_merge_feature_to_main() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.branch_to("feature/test")
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-test.1", "0.0.3-test.1+1"))
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-test.2", "0.0.3-test.1+2"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("0.0.3", "0.0.3-3", "0.0.3-1+3"))


def test_merge_feature_to_main_with_previous_commits() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-1", "0.0.3-1+1"))
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-2", "0.0.3-1+2"))
        f.branch_to("feature/test")
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-test.3", "0.0.3-test.1+3"))
        f.make_a_commit()
        _assert_all(f, _e("0.0.3", "0.0.3-test.4", "0.0.3-test.1+4"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("0.0.3", "0.0.3-5", "0.0.3-1+5"))


def test_merge_feature_to_main_with_minor_minor_semver_increment() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.branch_to("feature/test")
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-test.1", "0.1.0-test.1+1"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-test.2", "0.1.0-test.1+2"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("0.1.0", "0.1.0-3", "0.1.0-1+3"))


def test_merge_feature_to_main_with_major_minor_semver_increment() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.branch_to("feature/test")
        f.make_a_commit("+semver: major")
        _assert_all(f, _e("1.0.0", "1.0.0-test.1", "1.0.0-test.1+1"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("1.0.0", "1.0.0-test.2", "1.0.0-test.1+2"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("1.0.0", "1.0.0-3", "1.0.0-1+3"))


def test_merge_feature_to_main_with_previous_commits_and_minor_minor_semver_increment() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-1", "0.1.0-1+1"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-2", "0.1.0-1+2"))
        f.branch_to("feature/test")
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-test.3", "0.1.0-test.1+3"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-test.4", "0.1.0-test.1+4"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("0.1.0", "0.1.0-5", "0.1.0-1+5"))


def test_merge_feature_to_main_with_previous_commits_and_minor_major_semver_increment() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("0.0.2")
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("0.1.0", "0.1.0-1", "0.1.0-1+1"))
        f.make_a_commit("+semver: major")
        _assert_all(f, _e("1.0.0", "1.0.0-2", "1.0.0-1+2"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("1.0.0", "1.0.0-3", "1.0.0-1+3"))
        f.branch_to("feature/test")
        f.make_a_commit("+semver: major")
        _assert_all(f, _e("1.0.0", "1.0.0-test.4", "1.0.0-test.1+4"))
        f.make_a_commit("+semver: minor")
        _assert_all(f, _e("1.0.0", "1.0.0-test.5", "1.0.0-test.1+5"))
        f.checkout("main")
        f.merge_no_ff("feature/test")
        f.delete_branch("feature/test")
        _assert_all(f, _e("1.0.0", "1.0.0-6", "1.0.0-1+6"))
