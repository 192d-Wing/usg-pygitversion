# SPDX-License-Identifier: MIT
r"""``{Placeholder}`` template expansion.

Ports ``StringFormatWithExtension`` and ``LabelTokenizer`` from 6.8.2. Used
for branch labels (``{BranchName}``) and the assembly format strings.

Grammar inside braces: one or more alternatives separated by ``??``. Each
alternative is a quoted literal ``"text"``, an integer literal, an
environment lookup ``env:NAME[:format]`` or a member ``Name[:format]``. The
first alternative that yields a value wins; a literal always yields.
Formats for string values are ``u`` (upper), ``l`` (lower), ``t`` (title),
``s`` (sentence) and ``c`` (PascalCase); other formats are ignored, as
upstream's ``TryFormat`` returns false for them and the raw value is used.

Validation (SI-10): member names must match ``[A-Za-z0-9_.]+`` and
environment names ``[A-Za-z0-9_:\\-.]+``; formats are capped at 50 chars.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

_EXPAND_TOKENS = re.compile(r"\{([^{}]+)\}")
_MEMBER_NAME = re.compile(r"^[A-Za-z0-9_.]+$")
_ENV_NAME = re.compile(r"^[A-Za-z0-9_:\-.]+$")


class TemplateError(ValueError):
    """A malformed template (upstream ``FormatException`` / ``ArgumentException``)."""


@dataclass(frozen=True, slots=True)
class _Token:
    name: str
    kind: str  # "literal" | "env" | "member"
    fmt: str | None = None


def _split_key_format(identifier: str) -> tuple[str, str | None]:
    parts = identifier.split(":")
    if len(parts) > 2:  # noqa: PLR2004
        msg = f"Invalid format string: {identifier}"
        raise TemplateError(msg)
    return (parts[0], parts[1]) if len(parts) == 2 else (identifier, None)  # noqa: PLR2004


def _tokenize(text: str) -> list[_Token]:  # noqa: PLR0915 -- one tokenizer, ported whole
    """Port of ``LabelTokenizer.ParseTokens`` (whitespace-tolerant, ``??`` separated)."""
    tokens: list[_Token] = []
    i = 0
    n = len(text)

    def skip_ws() -> None:
        nonlocal i
        while i < n and text[i].isspace():
            i += 1

    def parse_identifier() -> str:
        nonlocal i
        out: list[str] = []
        in_quotes = False
        if i < n and text[i] == '"':
            in_quotes = True
            out.append('"')
            i += 1
        while i < n:
            ch = text[i]
            if not in_quotes and ch == '"':
                raise TemplateError("Literal value was not correctly quoted")
            if ch == '"':
                out.append('"')
                i += 1
                return "".join(out)
            if not in_quotes and (ch.isspace() or ch == "?"):
                return "".join(out)
            if ch == "\\" and i + 1 < n and text[i + 1] == '"':
                out.append('"')
                i += 2
            else:
                out.append(ch)
                i += 1
        if in_quotes:
            raise TemplateError("Literal value is missing closing quote")
        return "".join(out)

    def parse_separator() -> bool:
        nonlocal i
        seen = 0
        while i < n and seen < 2:  # noqa: PLR2004
            if text[i] != "?":
                raise TemplateError("Expected '??' separator")
            seen += 1
            i += 1
        return seen == 2  # noqa: PLR2004

    skip_ws()
    separated = False
    while i < n:
        identifier = parse_identifier()
        skip_ws()
        if not identifier:
            raise TemplateError("Invalid format sequence, expected identifier")
        tokens.append(_to_token(identifier))
        separated = parse_separator()
        skip_ws()
    if separated:
        raise TemplateError("Invalid format sequence, expected identifier after '??' separator")
    return tokens


def _to_token(identifier: str) -> _Token:
    if identifier.lower().startswith("env:"):
        name, fmt = _split_key_format(identifier[4:])
        return _Token(name, "env", fmt)
    if len(identifier) >= 2 and identifier[0] == '"' and identifier[-1] == '"':  # noqa: PLR2004
        return _Token(identifier[1:-1], "literal")
    if re.fullmatch(r"[-+]?\d+", identifier):
        return _Token(identifier, "literal")
    name, fmt = _split_key_format(identifier)
    return _Token(name, "member", fmt)


def _format_string(value: str, fmt: str) -> str | None:
    """Port of ``StringFormatter.TryFormat``; ``None`` means "format not recognised"."""
    if not value.strip():
        return ""
    formatters: dict[str, Callable[[str], str]] = {
        "u": str.upper,
        "l": str.lower,
        "t": lambda v: v.lower().title(),
        "s": lambda v: v.upper() if len(v) == 1 else v[0].upper() + v[1:].lower(),
        "c": lambda v: "".join(p.capitalize() for p in re.split(r"[^A-Za-z0-9]+", v) if p),
    }
    formatter = formatters.get(fmt)
    return None if formatter is None else formatter(value)


def _sanitize_format(fmt: str) -> str:
    if not fmt.strip():
        raise TemplateError("Format string cannot be empty.")
    if len(fmt) > 50:  # noqa: PLR2004
        msg = f"Format string too long: '{fmt[:20]}...'"
        raise TemplateError(msg)
    if any(ch.isprintable() is False and ch != "\t" for ch in fmt):
        raise TemplateError("Format string contains invalid control characters")
    return fmt


def format_with(
    template: str, resolve: Callable[[str], str | None], environment: Mapping[str, str]
) -> str:
    """Expand every ``{...}`` in ``template``.

    Args:
        template: Text with placeholders.
        resolve: Member lookup; returns ``None`` for "no value", raises
            :class:`TemplateError` for an unknown member.
        environment: Environment variables for ``env:`` tokens.

    Raises:
        TemplateError: On a malformed placeholder or an unresolvable token
            with no fallback.
    """

    def evaluate(match: re.Match[str]) -> str:
        last_error: Exception | None = None
        for token in _tokenize(match.group(1)):
            if token.kind == "literal":
                return token.name
            try:
                if token.kind == "env":
                    if not _ENV_NAME.match(token.name):
                        msg = f"Invalid environment variable name: {token.name}"
                        raise TemplateError(msg)
                    value = environment.get(token.name)
                    if value is None:
                        msg = (
                            f"Environment variable {token.name} not found and no fallback provided"
                        )
                        raise TemplateError(msg)
                else:
                    if not _MEMBER_NAME.match(token.name):
                        msg = f"Invalid member name: {token.name}"
                        raise TemplateError(msg)
                    value = resolve(token.name)
                    if value is None:
                        continue
                if token.fmt:
                    formatted = _format_string(value, _sanitize_format(token.fmt))
                    if formatted is not None:
                        return formatted
                return value
            except TemplateError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return ""

    return _EXPAND_TOKENS.sub(evaluate, template)
