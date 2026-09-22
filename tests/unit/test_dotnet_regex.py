# SPDX-License-Identifier: MIT
"""Tests for the .NET-to-Python regex translation shim."""

from __future__ import annotations

import pytest
from usg_pygitversion.dotnet import regex as dotnet
from usg_pygitversion.errors import ConfigurationError


@pytest.mark.parametrize(
    ("dotnet_pattern", "python_pattern"),
    [
        (r"^features?[\/-](?<BranchName>.+)", r"^features?[\/-](?P<BranchName>.+)"),
        (r"(?'Number'\d+)", r"(?P<Number>\d+)"),
        (r"(?<a>x)\k<a>", r"(?P<a>x)(?P=a)"),
        (r"(?<a>x)\k'a'", r"(?P<a>x)(?P=a)"),
        (r"(?<=foo)bar", r"(?<=foo)bar"),  # lookbehind untouched
        (r"(?<!foo)bar", r"(?<!foo)bar"),
        (r"abc\z", r"abc\Z"),
        (r"abc\Z", r"abc(?=\n?\Z)"),
        (r"[vV]?", r"[vV]?"),
    ],
)
def test_translate(dotnet_pattern: str, python_pattern: str) -> None:
    assert dotnet.translate(dotnet_pattern) == python_pattern


@pytest.mark.parametrize(
    "bad",
    [r"(?<a-b>x)", r"(?<-a>x)", r"(?n)abc", r"(?in:abc)", r"\p{L}+"],
)
def test_rejects_unsupported(bad: str) -> None:
    with pytest.raises(ConfigurationError, match="not supported"):
        dotnet.translate(bad)


def test_rejects_overlong_pattern() -> None:
    with pytest.raises(ConfigurationError, match="limit"):
        dotnet.translate("a" * (dotnet.MAX_PATTERN_LENGTH + 1))


def test_compile_reports_both_forms_on_syntax_error() -> None:
    with pytest.raises(ConfigurationError, match=r"invalid regex .*translated to"):
        dotnet.compile(r"(?<name>unclosed")


def test_compile_is_case_insensitive_by_default_and_cached() -> None:
    dotnet.cache_clear()
    a = dotnet.compile(r"^releases?[\/-](?<BranchName>.+)")
    b = dotnet.compile(r"^releases?[\/-](?<BranchName>.+)")
    assert a is b
    m = a.match("RELEASE/1.2")
    assert m is not None
    assert m.group("BranchName") == "1.2"


def test_upstream_default_patterns_all_compile() -> None:
    # Every default from the GitFlow/v1 preset must translate cleanly.
    for pattern in [
        r"[vV]?",
        r"(?<version>[vV]?\d+(\.\d+)?(\.\d+)?).*",
        r"^master$|^main$",
        r"^dev(elop)?(ment)?$",
        r"^releases?[\/-](?<BranchName>.+)",
        r"^features?[\/-](?<BranchName>.+)",
        r"^(pull-requests|pull|pr)[\/-](?<Number>\d*)",
        r"^hotfix(es)?[\/-](?<BranchName>.+)",
        r"^support[\/-](?<BranchName>.+)",
        r"(?<BranchName>.+)",
        r"\+semver:\s?(breaking|major)",
        r"\+semver:\s?(none|skip)",
    ]:
        dotnet.compile(pattern)


def test_bounded_truncates() -> None:
    assert dotnet.bounded("abc", 2) == "ab"
    assert dotnet.bounded("abc", 3) == "abc"
    long = "x" * (dotnet.MAX_SUBJECT_LENGTH + 10)
    assert len(dotnet.bounded(long)) == dotnet.MAX_SUBJECT_LENGTH


@pytest.mark.parametrize(
    "pattern",
    [
        r"^(a+)+b$",
        r"(?:x*)*y",
        r"(\d+\.?)+$",  # the separator is optional
        r"(a+a)+",  # the separator can be eaten by the inner repeat
        r"(\w+\s?)+$",
        r"((?<n>[a-z]+)|q)+",  # a branch alternative that starts unbounded
        r"(a?b*)*c",  # optional lead-in, then unbounded
        r"(?=(a+)+b)",  # inside a lookahead
    ],
)
def test_rejects_nested_unbounded_quantifiers(pattern: str) -> None:
    # `(a+)+` is exponential in the subject; the stdlib engine cannot be
    # interrupted, so the shape is refused at compile time (SI-10).
    with pytest.raises(ConfigurationError, match="nests an unbounded quantifier"):
        dotnet.compile(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"^Merge (branch|tag) '(?<SourceBranch>[^']*)'(?: into (?<TargetBranch>[^\s]*))*",
        r"^Finish (?<SourceBranch>[^\s]*)(?: into (?<TargetBranch>[^\s]*))*",
        r"(?<version>[vV]?\d+(\.\d+)?(\.\d+)?).*",
        r"(?:\.[0-9a-zA-Z-]+)*",
        r"^(?<BranchName>[^\s]*)\s(?<Direction>[^\s]*)\s(?<TargetBranch>[^\s]*)",
        r"[vV]?",
        r"(a|b)+c",
        # The conventional-commit pattern from the upstream docs: `.` cannot
        # match the `\n` that ends every `(.+\n)` iteration.
        (
            r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([\w\s-]*\))?"
            r"(!:|:.*\n\n((.+\n)+\n)?BREAKING CHANGE:\s.+)"
        ),
        r"(.+\n)+",
        r"(\d+\.)+\d+",
        r"(\w+\s)+",
        r"([^,]+,)*[^,]+",
    ],
)
def test_accepts_repetitions_that_start_with_a_fixed_element(pattern: str) -> None:
    # Upstream's own defaults and ordinary patterns must keep compiling.
    dotnet.compile(pattern)
