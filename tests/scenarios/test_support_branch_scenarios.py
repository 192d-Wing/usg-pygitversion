# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/SupportBranchScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_support_is_calculated_correctly() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.1.0")
        f.branch_to("release-2.0.0")
        f.make_commits(2)
        f.checkout("main")
        f.merge_no_ff("release-2.0.0")
        f.apply_tag("2.0.0")
        f.assert_full_semver("2.0.0")
        f.checkout("1.1.0")
        f.branch_to("support/1.0.0")
        f.assert_full_semver("1.1.0")
        f.branch_to("release/1.2.0")
        f.make_a_commit()
        f.assert_full_semver("1.2.0-beta.1+1")
        f.checkout("support/1.0.0")
        f.merge_no_ff("release/1.2.0")
        f.assert_full_semver("1.2.0-2")
        f.apply_tag("1.2.0")
        f.branch_to("hotfix/1.2.1")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+1")
        f.checkout("support/1.0.0")
        f.merge_no_ff("hotfix/1.2.1")
        f.assert_full_semver("1.2.1-2")


def test_when_support_is_branched_and_tagged_from_another_support_ensure_new_minor_is_used() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit()
        f.branch_to("Support-1.2.0")
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.branch_to("Support-1.3.0")
        f.apply_tag("1.3.0")
        f.make_commits(2)
        f.assert_full_semver("1.3.1-2")


def test_when_support_is_branched_from_main_with_specific_tag() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", configuration)
        f.apply_tag("1.4.0-rc")
        f.make_a_commit()
        f.branch_to("support/1")
        f.assert_full_semver("1.4.0-2", configuration)


def test_when_support_is_branched_from_main_with_specific_tag_on_commit() -> None:
    configuration = gitflow()
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.1-1", configuration)
        f.apply_tag("1.4.0-rc")
        f.branch_to("support/1")
        f.assert_full_semver("1.4.0-1", configuration)
