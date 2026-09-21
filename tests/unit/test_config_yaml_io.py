# SPDX-License-Identifier: MIT
"""YAML loader (YAML 1.2 scalars, limits) and emitter (reference formatting)."""

from __future__ import annotations

from importlib import resources

import pytest
from usg_pygitversion.config.yaml_io import MAX_DOCUMENT_BYTES, dump_mapping, load_mapping
from usg_pygitversion.errors import ConfigurationError


def test_load_scalars_follow_yaml_1_2_core() -> None:
    doc = load_mapping("a: true\nb: yes\nc: 5\nd: 2.10\ne: ~\nf: 2020-01-01\ng: '5'\n")
    assert doc == {"a": True, "b": "yes", "c": 5, "d": 2.1, "e": None, "f": "2020-01-01", "g": "5"}


def test_load_empty_and_non_mapping() -> None:
    assert load_mapping("") == {}
    assert load_mapping("# just a comment\n") == {}
    with pytest.raises(ConfigurationError, match="mapping at the top level"):
        load_mapping("- a\n- b\n")


def test_load_invalid_yaml_and_size_cap() -> None:
    with pytest.raises(ConfigurationError, match="not valid YAML"):
        load_mapping("a: [unclosed\n")
    with pytest.raises(ConfigurationError, match="byte limit"):
        load_mapping("a: " + "x" * MAX_DOCUMENT_BYTES)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("alpha", "alpha"),
        ("", "''"),
        ("{BranchName}", '"{BranchName}"'),
        ("[vV]?", '"[vV]?"'),
        ("^master$|^main$", '"^master$|^main$"'),
        ("^dev(elop)?(ment)?$", "^dev(elop)?(ment)?$"),
        ("(?<BranchName>.+)", '"(?<BranchName>.+)"'),
        (r"\+semver:\s?(fix|patch)", r'"\\+semver:\\s?(fix|patch)"'),
        ("yyyy-MM-dd", "yyyy-MM-dd"),
        ("2.1", '"2.1"'),
        ("true", '"true"'),
        ("-ab", "-ab"),
        ("?ab", "?ab"),
        ("a>b", '"a>b"'),
        ("a<b", "a<b"),
        ("a*b", '"a*b"'),
        ("a#b", '"a#b"'),
        ("a,b", '"a,b"'),
        ("it's", '"it\'s"'),
        (" lead", '" lead"'),
        ("1.2.3", "1.2.3"),
        ("null", '"null"'),
        ("0x1F", '"0x1F"'),
        (5, "5"),
        (True, "true"),
        (False, "false"),
    ],
)
def test_scalar_quoting_matches_reference(value: object, expected: str) -> None:
    assert dump_mapping({"k": value}) == f"k: {expected}\n"


def test_containers_layout() -> None:
    doc = {"a": {"b": [], "c": {}, "d": ["x", "y"], "e": {"f": 1}}}
    assert dump_mapping(doc) == "a:\n  b: []\n  c: {}\n  d:\n    - x\n    - y\n  e:\n    f: 1\n"
    assert dump_mapping({}) == ""


@pytest.mark.parametrize("name", ["GitFlow-v1.yml", "GitHubFlow-v1.yml", "TrunkBased-preview1.yml"])
def test_presets_round_trip_byte_for_byte(name: str) -> None:
    # load -> dump must reproduce upstream's approved serialisation exactly,
    # which proves both the loader's typing and the emitter's formatting.
    text = (
        resources.files("usg_pygitversion.config.presets")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
    body = "".join(line for line in text.splitlines(keepends=True) if not line.startswith("#"))
    assert dump_mapping(load_mapping(body)) == body
