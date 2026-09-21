# SPDX-License-Identifier: MIT
"""JSON (de)serialisation of the output variables. Ports ``VersionVariableSerializer``.

The reference tool writes ``System.Text.Json`` indented output with the
variables ordered alphabetically, integer-typed variables as JSON numbers
(``null`` when empty) and every other variable as a string (``""`` when
empty). The same document is written to the on-disk cache, so
:func:`from_json` must read back everything :func:`to_json` writes.
"""

from __future__ import annotations

import json

from usg_pygitversion.calculation.variables import AVAILABLE_VARIABLES, GitVersionVariables
from usg_pygitversion.errors import GitVersionError

#: Variables typed ``int?`` in upstream ``VersionVariablesJsonModel``.
INT_VARIABLES: frozenset[str] = frozenset(
    {
        "BuildMetaData",
        "CommitsSinceVersionSource",
        "Major",
        "Minor",
        "Patch",
        "PreReleaseNumber",
        "UncommittedChanges",
        "VersionSourceDistance",
        "WeightedPreReleaseNumber",
    }
)

#: Upper bound on a cache/JSON document we are willing to parse (SI-10).
MAX_JSON_LENGTH = 64 * 1024


def _json_value(name: str, value: str | None) -> int | str | None:
    if name in INT_VARIABLES:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError as exc:
            msg = f"variable {name!r} is not an integer"
            raise GitVersionError(msg) from exc
    return "" if value is None else value


def to_json(variables: GitVersionVariables) -> str:
    """Render the variables exactly like ``gitversion /output json``."""
    document = {name: _json_value(name, value) for name, value in sorted(variables)}
    # ensure_ascii=False mirrors System.Text.Json's UTF-8 output for branch names.
    return json.dumps(document, indent=2, ensure_ascii=False)


def from_json(text: str) -> GitVersionVariables:
    """Parse a document written by :func:`to_json` (or by the reference tool).

    Raises:
        GitVersionError: If the document is malformed or has unknown keys.
    """
    if len(text) > MAX_JSON_LENGTH:
        raise GitVersionError("variables document is too large")
    try:
        loaded = json.loads(text)
    except ValueError as exc:
        raise GitVersionError(f"variables document is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise GitVersionError("variables document must be a JSON object")
    values: dict[str, str | None] = {}
    for name in AVAILABLE_VARIABLES:
        if name not in loaded:
            raise GitVersionError(f"variables document is missing {name!r}")
        raw = loaded[name]
        if raw is None:
            values[name] = None
        elif isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise GitVersionError(f"variable {name!r} has an unexpected type")
        else:
            values[name] = str(raw)
    return GitVersionVariables(values)
