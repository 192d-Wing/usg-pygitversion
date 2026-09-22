# SPDX-License-Identifier: MIT
"""Template engine tests, mirroring upstream ``StringFormatWithExtensionTests``."""

from __future__ import annotations

import pytest
from usg_pygitversion.formatting import TemplateError, format_with, redact_secrets

_MEMBERS = {"Major": "1", "Minor": "2", "Empty": "", "Name": "hello world", "Missing": None}


def _resolve(name: str) -> str | None:
    if name not in _MEMBERS:
        msg = f"'{name}' is not a property"
        raise TemplateError(msg)
    return _MEMBERS[name]


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{Major}.{Minor}", "1.2"),
        ("v{Major}-{env:BUILD}", "v1-42"),
        ("{env:NOPE ?? Minor}", "2"),
        ('{env:NOPE ?? "quoted text"}', "quoted text"),
        ("{Missing ?? Major}", "1"),
        ("{Missing ?? 7}", "7"),
        ("{Name:u}", "HELLO WORLD"),
        ("{Name:l}", "hello world"),
        ("{Name:t}", "Hello World"),
        ("{Name:s}", "Hello world"),
        ("{Name:c}", "HelloWorld"),
        ("{Name:zz}", "hello world"),  # unknown format -> raw value, as upstream
        ("{Empty:u}", ""),
        ("no placeholders", "no placeholders"),
        ("{ Major }", "1"),  # whitespace tolerated
    ],
)
def test_format_with(template: str, expected: str) -> None:
    assert format_with(template, _resolve, {"BUILD": "42"}) == expected


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{Unknown}", "not a property"),
        ("{env:UNSET}", "not found and no fallback"),
        ('{"unterminated}', "missing closing quote"),
        ("{Major ??}", "expected identifier after"),
        ("{Major ? Minor}", "Expected '\\?\\?' separator"),
        ("{Major:a:b}", "Invalid format string"),
        ("{Major:" + "x" * 60 + "}", "too long"),
        ("{env:bad name}", "Expected '\\?\\?' separator"),
        ("{env:bad$name}", "Invalid environment variable name"),
        ("{bad-member}", "Invalid member name"),
    ],
)
def test_format_with_errors(template: str, message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        format_with(template, _resolve, {})


def test_first_resolvable_alternative_wins_and_errors_are_deferred() -> None:
    # An unknown first alternative is only an error if nothing later resolves.
    assert format_with("{Unknown ?? Minor}", _resolve, {}) == "2"
    with pytest.raises(TemplateError):
        format_with("{Unknown ?? AlsoUnknown}", _resolve, {})


def test_redact_secrets_withholds_credential_like_names() -> None:
    environment = {
        "HOME": "/home/ci",
        "BUILD_NUMBER": "7",
        "GITHUB_TOKEN": "ghs_x",
        "AWS_SECRET_ACCESS_KEY": "k",
        "DbPassword": "p",
        "api-key": "a",
        "NPM_AUTH": "n",
    }
    kept = redact_secrets(environment)
    assert kept == {"HOME": "/home/ci", "BUILD_NUMBER": "7"}
    # A withheld variable behaves exactly like an unset one for templates.
    assert format_with("{env:GITHUB_TOKEN ?? Minor}", _resolve, kept) == "2"
    with pytest.raises(TemplateError, match="not found"):
        format_with("{env:GITHUB_TOKEN}", _resolve, kept)
