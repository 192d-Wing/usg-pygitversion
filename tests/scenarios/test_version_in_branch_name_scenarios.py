# SPDX-License-Identifier: MIT
"""Ports of ``VersionInMergedBranchNameScenarios.cs`` and ``VersionInCurrentBranchNameScenarios.cs``.

Remote-repository cases need the clone/fetch fixture and land with Phase 5.
"""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow

pytestmark = pytest.mark.scenario


# -- merged branch name --------------------------------------------------------


def test_merged_takes_version_from_name_of_release_branch() -> None:
    with GitFlowScenario("1.0.0") as f:
        f.create_and_merge_branch_into_develop("release/2.0.0")
        f.assert_full_semver("2.1.0-alpha.2")


def test_merged_does_not_take_version_from_name_of_non_release_branch() -> None:
    with GitFlowScenario("1.0.0") as f:
        f.create_and_merge_branch_into_develop(
            "pull-request/improved-by-upgrading-some-lib-to-4.5.6"
        )
        f.create_and_merge_branch_into_develop(
            "hotfix/downgrade-some-lib-to-3.2.1-to-avoid-breaking-changes"
        )
        f.assert_full_semver("1.1.0-alpha.5")


@pytest.mark.parametrize("branch", ["release", "hotfix"])
def test_merged_does_not_take_version_from_branch_with_accidental_version(branch: str) -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to(f"{branch}/downgrade-some-lib-to-3.2.1")
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff(f"{branch}/downgrade-some-lib-to-3.2.1")
        f.assert_full_semver("1.0.1-2")


def test_merged_takes_version_from_name_of_branch_that_is_release_by_config() -> None:
    configuration = gitflow(branches={"support": {"is_release_branch": True}})
    with GitFlowScenario("1.0.0") as f:
        f.create_and_merge_branch_into_develop("support/2.0.0")
        f.assert_full_semver("2.1.0-alpha.2", configuration)


@pytest.mark.skip(reason="remote repository fixture lands in Phase 5")
def test_merged_takes_version_from_name_of_remote_release_branch_in_origin() -> None:
    pass


# -- current branch name -------------------------------------------------------


def test_current_takes_version_from_name_of_release_branch() -> None:
    with GitFlowScenario("1.0.0") as f:
        f.branch_to("release/2.0.0")
        f.assert_full_semver("2.0.0-beta.1+1")


def test_current_does_not_take_version_from_name_of_non_release_branch() -> None:
    with GitFlowScenario("1.0.0") as f:
        f.branch_to("feature/upgrade-power-level-to-9000.0.1")
        f.assert_full_semver("1.1.0-upgrade-power-level-to-9000-0-1.1+1")


def test_current_takes_version_from_name_of_branch_that_is_release_by_config() -> None:
    configuration = gitflow(branches={"support": {"is_release_branch": True}})
    with GitFlowScenario("1.0.0") as f:
        f.branch_to("support/2.0.0")
        f.assert_full_semver("2.0.0-1", configuration)


@pytest.mark.skip(reason="remote repository fixture lands in Phase 5")
def test_current_takes_version_from_name_of_remote_release_branch_in_origin() -> None:
    pass
