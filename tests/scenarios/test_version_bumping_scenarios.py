# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/VersionBumpingScenarios.cs`` (6.8.2)."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, gitflow

pytestmark = pytest.mark.scenario


def test_applied_pre_release_label_causes_bump() -> None:
    configuration = gitflow(branches={"main": {"label": "pre", "source_branches": []}})
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0-pre.1")
        f.make_a_commit()
        f.assert_full_semver("1.0.0-pre.2", configuration)


def test_can_use_commit_messages_to_bump_version() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:minor")
        f.assert_full_semver("1.1.0-1")
        f.make_a_commit("+semver:major")
        f.assert_full_semver("2.0.0-2")


def test_can_use_commit_messages_to_bump_version_tag_takes_priority() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:major")
        f.assert_full_semver("2.0.0-1")
        f.apply_tag("1.1.0")
        f.assert_full_semver("1.1.0")
        f.make_a_commit()
        f.assert_full_semver("1.1.1-1")


@pytest.mark.skip(reason="uses the Mainline strategy, which lands in Phase 4")
def test_can_use_conventional_commits_to_bump_version() -> None:
    pass


def test_can_use_commit_messages_to_bump_version_base_version_tag_is_applied_to_same_commit() -> (
    None
):
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("+semver:minor")
        f.assert_full_semver("1.1.0-1")
        f.apply_tag("2.0.0")
        f.make_a_commit("Hello")
        f.assert_full_semver("2.0.1-1")
