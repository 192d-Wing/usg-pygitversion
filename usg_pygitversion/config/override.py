# SPDX-License-Identifier: MIT
"""Parse ``/overrideconfig key=value`` options. Ports 6.8.2 ``ParseOverrideConfig``.

At 6.8.2 only *root-level* keys with simple types are supported (strings,
enums, integers, booleans and the strategies list); ``branches.*``,
``prevent-increment``, ``ignore`` and ``merge-message-formats`` are not
addressable and are rejected with the upstream message. Keys are
lower-cased. Values may be quoted; surrounding quotes are removed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from usg_pygitversion.config.schema import ROOT_FIELDS
from usg_pygitversion.config.yaml_io import load_mapping
from usg_pygitversion.errors import UsageError

#: Field kinds that ``OverrideConfigurationOptionParser.IsSupportedPropertyType`` accepts.
_SIMPLE_KINDS = {"str", "int", "bool", "next-version", "strategies"}

SUPPORTED_KEYS: frozenset[str] = frozenset(
    key
    for key, _attr, kind in ROOT_FIELDS
    if kind.rstrip("!") in _SIMPLE_KINDS or kind.rstrip("!").startswith("enum:")
)


def _split_unquoted(text: str, separator: str) -> list[str]:
    """Split on ``separator`` outside quotes. Ports ``QuotedStringHelpers.SplitUnquoted``."""
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote is None and ch in ("'", '"'):
            quote = ch
        elif quote is not None and ch == quote:
            quote = None
        if ch == separator and quote is None:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _unquote(text: str) -> str:
    """Strip one layer of matching surrounding quotes. Ports ``UnquoteText``."""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):  # noqa: PLR2004
        return text[1:-1]
    return text


def _coerce_scalar(value: str) -> Any:
    """Interpret the value as a YAML scalar so ``true``/``5`` get their types.

    Upstream achieves this by serialising the merged dictionary to YAML and
    deserialising it into the typed model; parsing the scalar directly is
    equivalent for the supported simple types.
    """
    if value == "":
        return ""
    loaded = load_mapping(f"v: {value}", "override value")
    return loaded.get("v", value)


def parse_override_options(options: Iterable[str]) -> dict[str, Any]:
    """Turn ``["key=value", ...]`` into an override document.

    Raises:
        UsageError: For a malformed option or an unsupported key (messages
            mirror upstream's ``WarningException`` text).
    """
    result: dict[str, Any] = {}
    for option in options:
        pair = _split_unquoted(option, "=")
        if len(pair) != 2:  # noqa: PLR2004
            msg = (
                f"Could not parse /overrideconfig option: {option}. "
                "Ensure it is in format 'key=value'."
            )
            raise UsageError(msg)
        key = pair[0].lower()
        if key not in SUPPORTED_KEYS:
            msg = f"Could not parse /overrideconfig option: {option}. Unsupported key '{key}'."
            raise UsageError(msg)
        raw = _unquote(pair[1])
        # Quoted values stay strings (the user asked for a string); bare
        # values are interpreted as YAML scalars.
        result[key] = raw if raw != pair[1] else _coerce_scalar(raw)
    return result
