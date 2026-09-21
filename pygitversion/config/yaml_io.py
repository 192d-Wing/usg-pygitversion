# SPDX-License-Identifier: MIT
"""YAML reading and writing with GitVersion's exact conventions.

Reading (SI-10, SI-16):

* ``yaml.safe_load`` only, through a loader whose scalar resolution follows
  YAML 1.2 core like the reference implementation (VYaml): ``true``/``false``
  are booleans but ``yes``/``no``/``on``/``off`` are plain strings, which the
  typed schema then rejects for boolean keys with a clear message. The
  reference binary rejects ``update-build-number: yes`` (verified), so this
  matches. Timestamps are not auto-converted; ``commits-before`` is parsed
  by the schema.
* Documents are capped at :data:`MAX_DOCUMENT_BYTES`.
* The top level must be a mapping; anything else is rejected.

Writing: a small emitter that reproduces the reference ``/showconfig``
output byte for byte (block style, two-space indent, sequences indented
under their key, ``[]``/``{}`` for empties, double-quoted strings only when
needed, ``''`` for the empty string). Verified against the three vendored
6.8.2 workflow files and a captured ``/showconfig``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import yaml

from pygitversion.errors import ConfigurationError

#: Upper bound on a configuration document (SI-10). Real files are < 10 KiB.
MAX_DOCUMENT_BYTES = 1024 * 1024


class _Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 core-schema scalar resolution."""


# Drop every implicit resolver, then re-add the 1.2 core set we want.
_Loader.yaml_implicit_resolvers = {}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""]
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?(?:0|[1-9][0-9]*)|0o[0-7]+|0x[0-9a-fA-F]+)$"),
    list("-+0123456789"),
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
        r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
    ),
    list("-+0123456789."),
)


def load_mapping(text: str, source: str = "configuration") -> dict[str, Any]:
    """Parse a YAML document that must be a mapping with string keys.

    Args:
        text: Document content.
        source: Name used in error messages (a file path, "override", ...).

    Returns:
        The mapping, or ``{}`` for an empty document.

    Raises:
        ConfigurationError: On oversize input, invalid YAML, or a non-mapping
            top level.
    """
    if len(text.encode("utf-8", "surrogatepass")) > MAX_DOCUMENT_BYTES:
        msg = f"{source} exceeds the {MAX_DOCUMENT_BYTES} byte limit"
        raise ConfigurationError(msg)
    try:
        document = yaml.load(text, Loader=_Loader)  # noqa: S506 -- _Loader derives from SafeLoader
    except yaml.YAMLError as exc:
        msg = f"{source} is not valid YAML: {exc}"
        raise ConfigurationError(msg) from exc
    if document is None:
        return {}
    if not isinstance(document, Mapping):
        msg = f"{source} must be a YAML mapping at the top level"
        raise ConfigurationError(msg)
    return {str(key): value for key, value in document.items()}


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

#: Plain scalars that would be read back as something other than a string.
_LOOKS_TYPED = re.compile(
    r"^(?:true|false|null|~|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|0o[0-7]+|0x[0-9a-fA-F]+|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$",
    re.IGNORECASE,
)
#: Characters anywhere in a scalar that force double quoting. Derived by
#: probing the reference binary's ``/showconfig`` with candidate labels:
#: ``> * ! % @ ` & # , [ ] { } | \ : " '`` quote; ``( ) = + . ? $ - / ;``
#: and interior spaces do not, and neither does a leading ``-``, ``?`` or ``(``.
_NEEDS_QUOTE_ANY = frozenset("[]{},|\\:#\"'>*!%@`&\n\t\r")


def _scalar(value: object) -> str:
    """Render a scalar in the reference style."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if text == "":
        return "''"
    if (
        text[0].isspace()
        or text[-1].isspace()
        or any(ch in _NEEDS_QUOTE_ANY for ch in text)
        or _LOOKS_TYPED.match(text)
    ):
        escaped = (
            text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        )
        return f'"{escaped}"'
    return text


def _is_container(value: object) -> bool:
    return isinstance(value, Mapping | Sequence) and not isinstance(value, str | bytes)


def _emit_mapping(value: Mapping[Any, Any], indent: int, lines: list[str]) -> None:
    """Emit the entries of a mapping at ``indent`` spaces."""
    pad = " " * indent
    for key, item in value.items():
        k = _scalar(key)
        if _is_container(item):
            if not item:
                lines.append(f"{pad}{k}: {'{}' if isinstance(item, Mapping) else '[]'}")
            else:
                lines.append(f"{pad}{k}:")
                _emit(item, indent + 2, lines)
        else:
            lines.append(f"{pad}{k}: {_scalar(item)}")


def _emit_sequence(value: Sequence[Any], indent: int, lines: list[str]) -> None:
    """Emit the items of a sequence at ``indent`` spaces."""
    pad = " " * indent
    for item in value:
        # Nested containers inside sequences do not occur in GitVersion
        # configuration; render inline-flow to stay well-formed.
        rendered = _flow(item) if _is_container(item) else _scalar(item)
        lines.append(f"{pad}- {rendered}")


def _emit(value: object, indent: int, lines: list[str]) -> None:
    """Emit the children of a mapping or sequence at ``indent`` spaces."""
    if isinstance(value, Mapping):
        _emit_mapping(value, indent, lines)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        _emit_sequence(value, indent, lines)


def _flow(value: object) -> str:
    """Flow-style rendering for the (unused) nested-container case."""
    if isinstance(value, Mapping):
        return "{" + ", ".join(f"{_scalar(k)}: {_flow(v)}" for k, v in value.items()) + "}"
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    return _scalar(value)


def dump_mapping(mapping: Mapping[str, object]) -> str:
    """Render ``mapping`` as YAML in the reference ``/showconfig`` style.

    Returns:
        Text ending in a single newline (``""`` for an empty mapping).
    """
    lines: list[str] = []
    _emit(mapping, 0, lines)
    return "\n".join(lines) + ("\n" if lines else "")
