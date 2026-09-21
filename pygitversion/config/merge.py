# SPDX-License-Identifier: MIT
"""Deep merge of configuration documents. Ports ``ConfigurationHelper.Merge``.

Mappings merge recursively; any other value (scalars *and lists*) replaces
the existing one. That list-replacement rule is upstream's and matters:
``source-branches: [x]`` in a user file replaces, not extends, the preset.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def clone(value: Any) -> Any:
    """Deep-copy mappings and lists so merges never alias preset data."""
    if isinstance(value, Mapping):
        return {key: clone(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone(item) for item in value]
    return value


def merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``base`` with ``override`` applied (a new dict; inputs untouched)."""
    result: dict[str, Any] = clone(base)
    _merge_into(result, override)
    return result


def _merge_into(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_into(current, value)
        else:
            target[key] = clone(value)
