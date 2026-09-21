# SPDX-License-Identifier: MIT
"""Ports of ``VersionInMergedBranchNameScenarios.cs`` and ``VersionInCurrentBranchNameScenarios.cs``."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import GitFlowScenario, RemoteScenario, Scenario, gitflow

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


def test_merged_takes_version_from_name_of_remote_release_branch_in_origin() -> None:
    with RemoteScenario() as f:
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.local.fetch()
        f.local.merge_no_ff("origin/release/2.0.0")
        f.local.assert_full_semver("2.0.0-7")


def test_merged_does_not_take_version_from_name_of_remote_release_branch_in_custom_remote() -> None:
    with RemoteScenario() as f:
        f.local.rename_remote("origin", "upstream")
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.local.fetch("upstream")
        f.local.merge_no_ff("upstream/release/2.0.0")
        f.local.assert_full_semver("0.0.1-7")


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


def test_current_takes_version_from_name_of_remote_release_branch_in_origin() -> None:
    with RemoteScenario() as f:
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.local.fetch()
        f.local.checkout("origin/release/2.0.0")
        f.local.assert_full_semver("2.0.0-beta.1+6")


def test_current_does_not_take_version_from_name_of_remote_release_branch_in_custom_remote() -> (
    None
):
    with RemoteScenario() as f:
        f.local.rename_remote("origin", "upstream")
        f.branch_to("release/2.0.0")
        f.make_a_commit()
        f.local.fetch("upstream")
        f.local.checkout("upstream/release/2.0.0")
        f.local.assert_full_semver("0.0.1-upstream-release-2-0-0.1+6")
