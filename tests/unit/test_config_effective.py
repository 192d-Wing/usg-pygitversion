# SPDX-License-Identifier: MIT
"""Effective configuration: branch matching, inheritance and label expansion.

Ports the relevant cases of upstream ``ConfigurationExtensionsTests``.
"""

from __future__ import annotations

import pytest
from usg_pygitversion.config import (
    DeploymentMode,
    EffectiveConfiguration,
    IncrementStrategy,
    get_branch_configuration,
    get_effective_configuration,
)
from usg_pygitversion.config.effective import is_release_branch
from usg_pygitversion.config.provider import build
from usg_pygitversion.git import ReferenceName


@pytest.mark.parametrize(
    ("branch", "expected_label"),
    [
        ("main", ""),
        ("master", ""),
        ("develop", "alpha"),
        ("release/1.0", "beta"),
        ("feature/foo", "{BranchName}"),
        ("hotfix-x", "beta"),
        ("support/1.x", ""),
        ("pull/12/head", "PullRequest{Number}"),
        ("something-else", "{BranchName}"),  # unknown, matched last
    ],
)
def test_get_branch_configuration_matches_gitflow(branch: str, expected_label: str) -> None:
    cfg = build()
    assert get_branch_configuration(cfg, branch).label == expected_label


def test_remote_branch_names_are_matched_without_origin() -> None:
    cfg = build()
    ref = ReferenceName("refs/remotes/origin/develop")
    assert get_branch_configuration(cfg, ref).label == "alpha"


def test_unmatched_branch_gets_empty_configuration() -> None:
    cfg = build({"branches": {"unknown": {"regex": "^never$"}}})
    branch = get_branch_configuration(cfg, "zzz")
    assert branch.regex == ""
    assert branch.increment is IncrementStrategy.INHERIT


def test_effective_configuration_defaults_and_inheritance() -> None:
    cfg = build()
    main = get_effective_configuration(cfg, "main")
    assert main.increment is IncrementStrategy.PATCH
    assert main.mode is DeploymentMode.CONTINUOUS_DELIVERY  # from root
    assert main.prevent_increment_of_merged_branch is True
    assert main.prevent_increment_when_current_commit_tagged is True  # root default
    assert main.is_main_branch
    assert main.pre_release_weight == 55000
    assert main.tag_pre_release_weight == 60000
    assert main.commit_date_format == "yyyy-MM-dd"

    # feature inherits Increment=Inherit from root when no parent is given.
    feature = get_effective_configuration(cfg, "feature/x")
    assert feature.increment is IncrementStrategy.INHERIT
    assert feature.mode is DeploymentMode.MANUAL_DEPLOYMENT
    # With a parent effective configuration, Inherit resolves to the parent's.
    feature_from_develop = get_effective_configuration(
        cfg, "feature/x", get_effective_configuration(cfg, "develop")
    )
    assert feature_from_develop.increment is IncrementStrategy.MINOR
    assert feature_from_develop.label == "{BranchName}"  # own label kept
    assert feature_from_develop.tracks_release_branches is True  # inherited


def test_effective_configuration_requires_root_values() -> None:
    cfg = build({"tag-pre-release-weight": None})
    with pytest.raises(Exception, match="tag-pre-release-weight"):
        EffectiveConfiguration.create(cfg, get_branch_configuration(cfg, "main"))


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("feature/foo_bar", "foo-bar"),
        ("feature/Foo.Bar/baz", "Foo-Bar-baz"),
        ("pull/42/merge", "PullRequest42"),
        ("develop", "alpha"),
        ("main", ""),
    ],
)
def test_branch_specific_label(branch: str, expected: str) -> None:
    cfg = build()
    effective = get_effective_configuration(cfg, branch)
    assert effective.branch_specific_label(ReferenceName.from_branch_name(branch)) == expected


def test_branch_specific_label_override_and_env() -> None:
    label = '{BranchName}-{env:BUILD ?? "local"}-{env:USER}'
    cfg = build({"branches": {"feature": {"label": label}}})
    effective = get_effective_configuration(cfg, "feature/x")
    assert effective.branch_specific_label("feature/x", None, {"USER": "me"}) == "x-local-me"
    assert effective.branch_specific_label("feature/x", "feature/y", {"USER": "me"}) == "y-local-me"
    # An unresolvable template returns the raw label, as upstream.
    assert effective.branch_specific_label("feature/x", None, {}) == label
    assert get_effective_configuration(cfg, "main").branch_specific_label("main") == ""


def test_is_release_branch() -> None:
    cfg = build()
    assert is_release_branch(cfg, "release/2.0")
    assert is_release_branch(cfg, "hotfix/1.0.1")
    assert not is_release_branch(cfg, "develop")
