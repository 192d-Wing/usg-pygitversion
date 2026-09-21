# SPDX-License-Identifier: MIT
"""Provider: presets, layering, finalise, validate, file discovery and overrides.

Several cases are ports of upstream ``ConfigurationProviderTests``; the
default-configuration case is checked against a ``/showconfig`` capture
from the reference 6.8.2 binary.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pygitversion.config import (
    DeploymentMode,
    GitVersionConfiguration,
    IncrementStrategy,
    VersionStrategy,
    provide,
)
from pygitversion.config.locator import find_configuration_file, verify_unambiguous
from pygitversion.config.override import SUPPORTED_KEYS, parse_override_options
from pygitversion.config.provider import build
from pygitversion.config.workflows import KNOWN_WORKFLOWS, load_preset
from pygitversion.config.yaml_io import dump_mapping, load_mapping
from pygitversion.errors import ConfigurationError, UsageError

_ORACLE = Path(__file__).with_name("showconfig-default-6.8.2.yml")


def _oracle_text() -> str:
    lines = _ORACLE.read_text(encoding="utf-8").splitlines(keepends=True)
    body = "".join(line for line in lines if not line.startswith("#"))
    # The binary prints the YAML and then one extra newline from
    # Console.WriteLine; that final newline is the CLI's job (Phase 5).
    return body.rstrip("\n") + "\n"


def test_default_configuration_matches_reference_showconfig() -> None:
    # No config file: must equal what the real binary prints, byte for byte.
    assert dump_mapping(build().to_mapping()) == _oracle_text()


@pytest.mark.parametrize("workflow", KNOWN_WORKFLOWS)
def test_each_workflow_round_trips_through_the_model(workflow: str) -> None:
    # Ports upstream WorkflowsTests: model -> yaml equals the approved file.
    cfg = build({"workflow": workflow})
    expected = dict(load_preset(workflow))
    expected["workflow"] = workflow
    assert dump_mapping(cfg.to_mapping()) == dump_mapping(
        GitVersionConfiguration.from_mapping(expected).to_mapping()
    )
    assert cfg.workflow == workflow


def test_unknown_workflow_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unknown workflow"):
        build({"workflow": "Custom/v9"})
    with pytest.raises(ConfigurationError, match="unknown workflow"):
        build({"workflow": "../../etc/passwd"})


def test_file_overrides_preset_and_override_overrides_file() -> None:
    cfg = build({"tag-prefix": "file", "next-version": "1.0"}, {"tag-prefix": "cli"})
    assert cfg.tag_prefix == "cli"
    assert cfg.next_version == "1.0"
    # Untouched preset values survive layering.
    assert cfg.branches["develop"].label == "alpha"


def test_partial_branch_override_keeps_other_branch_values() -> None:
    # Verified against the binary: overriding main.label keeps main.regex.
    cfg = build({"branches": {"main": {"label": "xyz"}}})
    assert cfg.branches["main"].label == "xyz"
    assert cfg.branches["main"].regex == "^master$|^main$"
    assert cfg.branches["main"].increment is IncrementStrategy.PATCH


def test_lists_replace_rather_than_extend() -> None:
    cfg = build({"branches": {"feature": {"source-branches": ["main"]}}})
    assert cfg.branches["feature"].source_branches == ("main",)
    cfg = build({"strategies": ["Mainline"]})
    assert cfg.strategies == (VersionStrategy.MAINLINE,)


def test_new_branch_requires_regex_with_upstream_message() -> None:
    with pytest.raises(
        ConfigurationError,
        match=r"Branch configuration 'custom' is missing required configuration 'regex'",
    ):
        build({"branches": {"custom": {"label": "c"}}})


def test_source_branches_must_exist() -> None:
    with pytest.raises(
        ConfigurationError,
        match=r"defines these 'source-branches' that are not configured: '\[nope\]'",
    ):
        build({"branches": {"custom": {"regex": "^c", "source-branches": ["nope", "main"]}}})


def test_is_source_branch_for_is_folded_into_targets() -> None:
    cfg = build({"branches": {"custom": {"regex": "^c", "is-source-branch-for": ["feature"]}}})
    assert "custom" in cfg.branches["feature"].source_branches
    with pytest.raises(ConfigurationError, match="is-source-branch-for"):
        build({"branches": {"custom": {"regex": "^c", "is-source-branch-for": ["nope"]}}})


def test_can_remove_label_and_next_version_forms() -> None:
    # Ports CanRemoveLabel / NextVersionCanBeInteger / ...CanHavePatch.
    cfg = build({"branches": {"release": {"label": ""}}, "next-version": 2})
    assert cfg.branches["release"].label == ""
    assert cfg.next_version == "2.0"
    assert build({"next-version": "2.118998723"}).next_version == "2.118998723"
    assert build({"next-version": "2.12.654651698"}).next_version == "2.12.654651698"


def test_mode_root_override_applies_to_all_branches_via_effective(tmp_path: Path) -> None:
    (tmp_path / "GitVersion.yml").write_text("mode: ContinuousDeployment\n", encoding="utf-8")
    cfg = provide(tmp_path)
    assert cfg.mode is DeploymentMode.CONTINUOUS_DEPLOYMENT


# -- locator ------------------------------------------------------------------


def test_find_configuration_file_order_and_case(tmp_path: Path) -> None:
    assert find_configuration_file(tmp_path) is None
    (tmp_path / ".gitversion.YAML").write_text("", encoding="utf-8")
    assert find_configuration_file(tmp_path) == tmp_path / ".gitversion.YAML"
    (tmp_path / "GitVersion.yml").write_text("", encoding="utf-8")
    assert find_configuration_file(tmp_path) == tmp_path / "GitVersion.yml"
    custom = tmp_path / "custom.yml"
    custom.write_text("", encoding="utf-8")
    assert find_configuration_file(tmp_path, "custom.yml") == custom
    assert find_configuration_file(tmp_path, str(custom)) == custom
    assert find_configuration_file(None) is None


def test_provide_prefers_working_directory_then_project_root(tmp_path: Path) -> None:
    root = tmp_path
    sub = root / "sub"
    sub.mkdir()
    (root / "GitVersion.yml").write_text("tag-prefix: root\n", encoding="utf-8")
    assert provide(sub, root).tag_prefix == "root"
    (sub / "GitVersion.yml").write_text("tag-prefix: sub\n", encoding="utf-8")
    assert provide(sub, root).tag_prefix == "sub"
    with pytest.raises(ConfigurationError, match="Ambiguous configuration file selection"):
        verify_unambiguous(sub, root, None)


def test_verify_unambiguous_explicit_missing(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    with pytest.raises(ConfigurationError, match="was not found at"):
        verify_unambiguous(sub, tmp_path, "nothere.yml")
    verify_unambiguous(sub, tmp_path, "GitVersion.yml")  # standard name: no error
    verify_unambiguous(tmp_path, tmp_path, "x.yml")  # same directory: no check


# -- overrides ----------------------------------------------------------------


def test_override_supported_keys_match_upstream_simple_types() -> None:
    assert "next-version" in SUPPORTED_KEYS
    assert "tag-prefix" in SUPPORTED_KEYS
    assert "strategies" in SUPPORTED_KEYS
    for unsupported in ("branches", "prevent-increment", "ignore", "merge-message-formats"):
        assert unsupported not in SUPPORTED_KEYS


def test_parse_override_options() -> None:
    doc = parse_override_options(
        ["Tag-Prefix=abc", "update-build-number=false", "tag-pre-release-weight=5", 'label="x=y"']
    )
    assert doc == {
        "tag-prefix": "abc",
        "update-build-number": False,
        "tag-pre-release-weight": 5,
        "label": "x=y",
    }
    cfg = build(None, doc)
    assert (cfg.tag_prefix, cfg.update_build_number, cfg.tag_pre_release_weight) == (
        "abc",
        False,
        5,
    )


@pytest.mark.parametrize(
    ("option", "message"),
    [
        ("novalue", "Ensure it is in format 'key=value'"),
        ("branches.main.label=x", "Unsupported key 'branches.main.label'"),
        ("a=b=c", "Ensure it is in format 'key=value'"),
    ],
)
def test_parse_override_errors(option: str, message: str) -> None:
    with pytest.raises(UsageError, match=message):
        parse_override_options([option])


def test_load_mapping_reads_real_preset_files() -> None:
    for workflow in KNOWN_WORKFLOWS:
        assert "branches" in load_mapping(dump_mapping(load_preset(workflow)))
