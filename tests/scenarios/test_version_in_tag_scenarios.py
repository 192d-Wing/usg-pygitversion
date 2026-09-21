# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/VersionInTagScenarios.cs`` (6.8.2)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.scenarios.dsl import GitFlowScenario, Scenario, gitflow

pytestmark = pytest.mark.scenario

_FORMAT = "{Major}.{Minor}.{Patch}.{WeightedPreReleaseNumber}"


def test_tag_pre_release_weight_not_configured_head_tagged_uses_default_weight() -> None:
    configuration = gitflow(assembly_file_versioning_format=_FORMAT)
    with Scenario() as f:
        f.make_a_tagged_commit("1.1.0")
        assert f.get_version(configuration)["AssemblySemFileVer"] == "1.1.0.60000"


def test_tag_pre_release_weight_configured_head_tagged_uses_configured_weight() -> None:
    configuration = gitflow(assembly_file_versioning_format=_FORMAT, tag_pre_release_weight=65535)
    with Scenario() as f:
        f.make_a_tagged_commit("1.1.0")
        assert f.get_version(configuration)["AssemblySemFileVer"] == "1.1.0.65535"


@pytest.mark.parametrize(("weight", "expected"), [(65535, "1.1.0.65535"), (None, "1.1.0.60000")])
def test_tag_pre_release_weight_gitflow_release_finished(weight: int | None, expected: str) -> None:
    root: dict[str, Any] = {"assembly_file_versioning_format": _FORMAT}
    if weight is not None:
        root["tag_pre_release_weight"] = weight
    configuration = gitflow(**root)
    with GitFlowScenario("1.0.0") as f:
        f.checkout("main")
        f.merge_no_ff("develop")
        f.checkout("develop")
        f.make_a_commit("Feature commit 1")
        f.branch_to("release/1.1.0")
        f.make_a_commit("Release commit 1")
        f.assert_full_semver("1.1.0-beta.1+3", configuration)
        f.checkout("main")
        f.merge_no_ff("release/1.1.0")
        f.apply_tag("1.1.0")
        assert f.get_version(configuration)["AssemblySemFileVer"] == expected
