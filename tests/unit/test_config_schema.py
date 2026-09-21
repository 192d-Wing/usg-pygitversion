# SPDX-License-Identifier: MIT
"""Typed schema: coercion, validation messages, inheritance and serialisation order."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from pygitversion.config import (
    BranchConfiguration,
    DeploymentMode,
    GitVersionConfiguration,
    IgnoreConfiguration,
    IncrementStrategy,
    PreventIncrementConfiguration,
    VersionStrategy,
)
from pygitversion.config.schema import BRANCH_FIELDS, ROOT_FIELDS
from pygitversion.errors import ConfigurationError


def test_field_tables_cover_upstream_declaration_order() -> None:
    assert [k for k, _, _ in BRANCH_FIELDS][:3] == ["mode", "label", "increment"]
    assert [k for k, _, _ in ROOT_FIELDS][-3:] == ["strategies", "branches", "ignore"]
    assert len({k for k, _, _ in ROOT_FIELDS}) == len(ROOT_FIELDS)


def test_enum_and_bool_and_int_coercion() -> None:
    cfg = GitVersionConfiguration.from_mapping(
        {
            "mode": "continuousdeployment",
            "update-build-number": "false",
            "tag-pre-release-weight": "10",
            "strategies": "Fallback, taggedcommit",
        }
    )
    assert cfg.mode is DeploymentMode.CONTINUOUS_DEPLOYMENT
    assert cfg.update_build_number is False
    assert cfg.tag_pre_release_weight == 10
    assert cfg.strategies == (VersionStrategy.FALLBACK, VersionStrategy.TAGGED_COMMIT)
    assert cfg.version_strategy == VersionStrategy.FALLBACK | VersionStrategy.TAGGED_COMMIT


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        ({"mode": "Sometimes"}, "invalid value 'Sometimes' for DeploymentMode"),
        ({"update-build-number": "yes"}, "expects true or false"),
        ({"tag-pre-release-weight": "many"}, "expects an integer"),
        ({"tag-pre-release-weight": True}, "expects an integer"),
        ({"strategies": ["Nope"]}, "unknown version strategy 'Nope'"),
        ({"branches": ["x"]}, "expects a mapping of branch configurations"),
        ({"branches": {"x": {"prevent-increment": 3}}}, "prevent-increment' expects a mapping"),
        ({"ignore": {"commits-before": "yesterday"}}, "expects a date/time"),
    ],
)
def test_rejections_name_the_key(doc: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        GitVersionConfiguration.from_mapping(doc)


def test_unknown_keys_are_ignored_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="pygitversion.config"):
        cfg = GitVersionConfiguration.from_mapping({"foo": 1, "branches": {"main": {"bar": 2}}})
    assert cfg.branches["main"] == BranchConfiguration()
    assert "ignoring unknown configuration key 'foo'" in caplog.text
    assert "ignoring unknown configuration key 'bar' in branches.main" in caplog.text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(2, "2.0"), ("2", "2.0"), (2.1, "2.1"), ("1.2.3", "1.2.3"), ("v1.0", "v1.0")],
)
def test_next_version_setter(raw: object, expected: str) -> None:
    assert GitVersionConfiguration.from_mapping({"next-version": raw}).next_version == expected


def test_ignore_configuration() -> None:
    cfg = IgnoreConfiguration.from_mapping(
        {"commits-before": "2020-01-02T03:04:05", "sha": ["a", "a", "b"], "paths": ["src/"]}
    )
    assert cfg.before == datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert cfg.shas == ("a", "b")
    assert not cfg.is_empty
    assert cfg.to_mapping() == {
        "commits-before": "2020-01-02T03:04:05Z",
        "sha": ["a", "b"],
        "paths": ["src/"],
    }
    assert IgnoreConfiguration().is_empty
    assert IgnoreConfiguration().to_mapping() == {"sha": [], "paths": []}


def test_branch_inherit_fills_only_unset_values() -> None:
    child = BranchConfiguration(
        increment=IncrementStrategy.INHERIT,
        label="feat",
        prevent_increment=PreventIncrementConfiguration(of_merged_branch=True),
        source_branches=("main",),
    )
    parent = BranchConfiguration(
        increment=IncrementStrategy.MINOR,
        mode=DeploymentMode.MANUAL_DEPLOYMENT,
        label="parent",
        regex="^p$",
        prevent_increment=PreventIncrementConfiguration(when_branch_merged=True),
        source_branches=("develop",),
        pre_release_weight=5,
    )
    merged = child.inherit(parent)
    assert merged.increment is IncrementStrategy.MINOR
    assert merged.mode is DeploymentMode.MANUAL_DEPLOYMENT
    assert merged.label == "feat"
    assert merged.regex == "^p$"
    assert merged.prevent_increment == PreventIncrementConfiguration(True, True, None)
    assert merged.source_branches == ("main",)  # not inherited, as upstream
    assert merged.pre_release_weight == 5


def test_is_match_is_search_and_case_insensitive() -> None:
    branch = BranchConfiguration(regex=r"^features?[\/-](?<BranchName>.+)")
    assert branch.is_match("Feature/abc")
    assert branch.is_match("features-abc")
    assert not branch.is_match("main")
    assert not BranchConfiguration(regex="").is_match("anything")
    assert not BranchConfiguration().is_match("anything")


def test_to_mapping_omits_none_and_keeps_declaration_order() -> None:
    cfg = GitVersionConfiguration.from_mapping(
        {"label": "x", "tag-prefix": "v", "mode": "ContinuousDelivery", "branches": {}}
    )
    assert list(cfg.to_mapping()) == [
        "mode", "label", "increment", "prevent-increment", "source-branches",
        "is-source-branch-for", "tag-prefix", "merge-message-formats",
        "update-build-number", "semantic-version-format", "strategies", "branches", "ignore",
    ]  # fmt: skip


def test_as_branch_and_empty_branch_configuration() -> None:
    cfg = GitVersionConfiguration.from_mapping({"label": "root", "increment": "Patch"})
    assert cfg.as_branch().label == "root"
    empty = GitVersionConfiguration.empty_branch_configuration()
    assert (empty.regex, empty.label, empty.increment) == (
        "",
        "{BranchName}",
        IncrementStrategy.INHERIT,
    )
