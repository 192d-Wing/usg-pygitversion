# SPDX-License-Identifier: MIT
"""Semantic version tests, driven by the upstream test table.

The data in ``semver_cases.py`` is converted mechanically from
``SemanticVersionTests.cs`` in GitVersion 6.8.2, so every assertion here is
one the reference implementation also passes. Hand-written tests below cover
behaviour the table does not reach.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from usg_pygitversion.semver import (
    BuildMetaData,
    IncrementMode,
    PreReleaseTag,
    SemanticVersion,
    SemanticVersionFormat,
    VersionField,
)
from usg_pygitversion.semver.version import VersionParseError

from tests.unit.semver_cases import CASES


def _cases(name: str) -> list[Any]:
    return [
        pytest.param(*args, expected, id=f"{name}-{i}")
        for i, (args, expected) in enumerate(CASES[name])
    ]


# ---------------------------------------------------------------------------
# Parsing, from upstream ValidateVersionParsing and ValidateInvalidVersionParsing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "text", "major", "minor", "patch", "label", "tag_number", "builds",
        "branch", "sha", "other", "full", "prefix", "fmt", "_expected",
    ),
    _cases("ValidateVersionParsing"),
)  # fmt: skip
def test_parse_valid(
    text: str,
    major: int,
    minor: int,
    patch: int,
    label: str,
    tag_number: int | None,
    builds: int | None,
    branch: str | None,
    sha: str | None,
    other: str | None,
    full: str | None,
    prefix: str | None,
    fmt: str,
    _expected: object,
) -> None:
    version = SemanticVersion.try_parse(text, prefix, SemanticVersionFormat.parse(fmt))
    assert version is not None, text
    assert (version.major, version.minor, version.patch) == (major, minor, patch)
    assert version.prerelease.name == label
    assert version.prerelease.number == tag_number
    assert version.build_metadata.commits_since_tag == builds
    assert version.build_metadata.branch == branch
    assert version.build_metadata.sha == sha
    assert version.build_metadata.other_metadata == other
    assert version.to_string("i") == (full if full is not None else text)


@pytest.mark.parametrize(("args", "_expected"), CASES["ValidateInvalidVersionParsing"])
def test_parse_invalid(args: tuple[object, ...], _expected: object) -> None:
    text = str(args[0])
    prefix = str(args[1]) if len(args) > 1 else None
    assert SemanticVersion.try_parse(text, prefix) is None
    with pytest.raises(VersionParseError):
        SemanticVersion.parse(text, prefix)


def test_version_sorting() -> None:
    assert SemanticVersion.parse("1.0.0") > SemanticVersion.parse("1.0.0-beta")
    assert SemanticVersion.parse("1.0.0-beta.2") > SemanticVersion.parse("1.0.0-beta.1")
    assert SemanticVersion.parse("1.0.0-beta.1") < SemanticVersion.parse("1.0.0-beta.2")


def test_to_string_invalid_format() -> None:
    with pytest.raises(ValueError, match="Unknown format"):
        SemanticVersion(1, 2, 3).to_string("invalid")


# ---------------------------------------------------------------------------
# Formatting, from the upstream ToString test groups.
# ---------------------------------------------------------------------------


def _build(
    major: int,
    minor: int,
    patch: int,
    name: str | None,
    number: int | None,
    builds: int | None,
    branch: str | None,
    sha: str | None,
    other: str | None,
) -> SemanticVersion:
    tag = PreReleaseTag(name, number, True) if name is not None else PreReleaseTag()
    meta = (
        BuildMetaData(commits_since_tag=builds, sha=sha, branch=branch, other_metadata=other)
        if builds is not None
        else BuildMetaData()
    )
    return SemanticVersion(major, minor, patch, tag, meta)


@pytest.mark.parametrize(
    ("group", "fmt"),
    [
        ("ToStringTests", None),
        ("ToStringWithSFormatTests", "s"),
        ("ToStringWithFormatJTests", "j"),
        ("ToStringWithFormatFTests", "f"),
        ("ToStringWithFormatITests", "i"),
    ],
)
def test_to_string_table(group: str, fmt: str | None) -> None:
    for args, expected in CASES[group]:
        version = _build(*args)  # type: ignore[arg-type]
        got = str(version) if fmt is None else version.to_string(fmt)
        assert got == expected, (group, args)


# ---------------------------------------------------------------------------
# Incrementing, from the twelve upstream WhenIncrementing groups of 96 cases each.
# ---------------------------------------------------------------------------

_MODE_BY_SUFFIX = {
    "InModeEnsureIntegrity": IncrementMode.ENSURE_INTEGRITY,
    "InModeForce": IncrementMode.FORCE,
}


def _mode_for(group: str) -> IncrementMode:
    for suffix, mode in _MODE_BY_SUFFIX.items():
        if group.endswith(suffix):
            return mode
    return IncrementMode.STANDARD


_INCREMENT_GROUPS = [g for g in CASES if g.startswith("WhenIncrementing")]


@pytest.mark.parametrize("group", _INCREMENT_GROUPS)
def test_increment_table(group: str) -> None:
    mode = _mode_for(group)
    failures: list[str] = []
    for args, expected in CASES[group]:
        value, field_name, label = args
        version = SemanticVersion.parse(str(value))
        result = version.increment(VersionField.parse(str(field_name)), label, mode=mode)  # type: ignore[arg-type]
        if result.to_string("i") != expected:
            failures.append(
                f"{value} +{field_name} label={label!r} -> {result.to_string('i')} != {expected}"
            )
    assert not failures, "\n".join(failures)


def test_increment_table_size() -> None:
    # Guard against the generator silently dropping cases.
    assert sum(len(CASES[g]) for g in _INCREMENT_GROUPS) == 12 * 96


# ---------------------------------------------------------------------------
# Alternative versions and label handling, not covered by the upstream table.
# ---------------------------------------------------------------------------


def test_increment_prefers_greater_alternative() -> None:
    base = SemanticVersion.parse("1.0.0")
    alt = SemanticVersion.parse("2.0.0")
    result = base.increment(VersionField.PATCH, "beta", alt)
    assert result.to_string("i") == "2.0.0-beta.1"


def test_increment_none_with_alternative_resets_number() -> None:
    base = SemanticVersion.parse("1.0.0-beta.5")
    alt = SemanticVersion.parse("1.1.0")
    result = base.increment(VersionField.NONE, None, alt)
    assert result.to_string("i") == "1.1.0-beta.1"


def test_with_label_changes_only_label() -> None:
    assert (
        SemanticVersion.parse("1.2.3-alpha.4").with_label("beta").to_string("i") == "1.2.3-beta.1"
    )


def test_label_queries() -> None:
    version = SemanticVersion.parse("1.2.3-Beta.1")
    assert version.is_labeled_with("beta")
    assert version.is_match_for_branch_specific_label("BETA")
    assert not version.is_match_for_branch_specific_label("alpha")
    assert SemanticVersion.parse("1.2.3").is_match_for_branch_specific_label("anything")


# ---------------------------------------------------------------------------
# Equality semantics: partial on metadata, as upstream.
# ---------------------------------------------------------------------------


def test_metadata_equality_ignores_short_sha_and_dates() -> None:
    a = BuildMetaData(commits_since_tag=1, branch="main", sha="abc", short_sha="a")
    b = BuildMetaData(commits_since_tag=1, branch="main", sha="abc", short_sha="zzz")
    assert a == b
    assert hash(a) == hash(b)
    assert a != BuildMetaData(commits_since_tag=2, branch="main", sha="abc")


def test_prerelease_equality_ignores_promote_flag() -> None:
    assert PreReleaseTag("beta", 1, True) == PreReleaseTag("beta", 1, False)
    assert PreReleaseTag("beta", 1) != PreReleaseTag("beta", 2)


def test_prerelease_compare_none_number_is_lowest() -> None:
    assert PreReleaseTag("beta", None) < PreReleaseTag("beta", 0)
    assert PreReleaseTag("alpha", 9).compare_to(PreReleaseTag("beta", 1)) < 0
    assert PreReleaseTag().compare_to(PreReleaseTag("beta", 1)) > 0


def test_build_metadata_formats() -> None:
    meta = BuildMetaData(commits_since_tag=5, branch="feature/x", sha="abc", other_metadata="o/p")
    assert meta.to_string("b") == "5"
    assert meta.to_string("s") == "5.Sha.abc"
    assert meta.to_string("f") == "5.Branch.feature-x.Sha.abc.o-p"
    with pytest.raises(ValueError, match="Unknown format"):
        meta.to_string("x")


# ---------------------------------------------------------------------------
# Property-based round-trip and ordering checks, SA-11 fuzzing.
# ---------------------------------------------------------------------------

# Labels must not end in a digit or a hyphen: upstream splits trailing digits
# into the number ("A0" -> "A.0") and keeps a trailing hyphen whole, so those
# inputs are not round-trippable by design.
_ident = st.from_regex(r"[A-Za-z][0-9A-Za-z-]{0,6}[A-Za-z]", fullmatch=True)
_num = st.integers(min_value=0, max_value=10**6)


@given(_num, _num, _num, st.one_of(st.none(), _ident), st.one_of(st.none(), _num))
def test_strict_roundtrip(
    major: int, minor: int, patch: int, name: str | None, number: int | None
) -> None:
    tag = (
        PreReleaseTag(name or "", number, True) if (name or number is not None) else PreReleaseTag()
    )
    version = SemanticVersion(major, minor, patch, tag)
    text = version.to_string("s")
    parsed = SemanticVersion.try_parse(text)
    assert parsed is not None, text
    assert parsed.to_string("s") == text


@given(st.lists(st.tuples(_num, _num, _num), min_size=2, max_size=6))
def test_ordering_is_consistent_with_tuples(parts: list[tuple[int, int, int]]) -> None:
    versions = [SemanticVersion(*p) for p in parts]
    assert [(v.major, v.minor, v.patch) for v in sorted(versions)] == sorted(parts)
