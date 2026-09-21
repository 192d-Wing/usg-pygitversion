# SPDX-License-Identifier: MIT
"""Tests for the SemVer to PEP 440 mapping used to version the package itself."""

from __future__ import annotations

import pytest
from usg_pygitversion._pep440 import to_pep440


@pytest.mark.parametrize(
    ("semver", "expected"),
    [
        ("1.2.0", "1.2.0"),
        ("1.2.0-alpha.5", "1.2.0a5"),
        ("1.2.0-beta.3", "1.2.0b3"),
        ("1.2.0-rc.1", "1.2.0rc1"),
        ("1.2.0-beta", "1.2.0b0"),
        ("1.2.1-5", "1.2.1.dev5"),
        ("1.2.0-feature-x.4", "1.2.0.dev4"),
        ("1.2.0-PullRequest12.1", "1.2.0.dev1"),
        ("1.2.0-issue-branch.1", "1.2.0.dev1"),
    ],
)
def test_mapping(semver: str, expected: str) -> None:
    assert to_pep440(semver) == expected


@pytest.mark.parametrize("text", ["", "1.2", "1.2.0+5", "1.2.0-beta.3+meta", "v1.2.0"])
def test_rejects_non_semver(text: str) -> None:
    with pytest.raises(ValueError, match="cannot map"):
        to_pep440(text)


def test_orders_like_gitversion() -> None:
    packaging = pytest.importorskip("packaging.version")
    Version = packaging.Version  # noqa: N806 -- class alias

    ordered = [
        "1.2.0-feature-x.4",
        "1.2.0-alpha.5",
        "1.2.0-beta.3",
        "1.2.0-rc.1",
        "1.2.0",
        "1.2.1-5",
    ]
    mapped = [Version(to_pep440(v)) for v in ordered]
    assert mapped == sorted(mapped)
