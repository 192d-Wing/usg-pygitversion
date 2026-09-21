"""The part of a version to increment.

Ports ``GitVersion.Core/SemVer/VersionField.cs``. The integer values are
ordered so that ``max()`` over a set of fields picks the biggest bump, which
is how upstream combines commit-message increments.
"""

from __future__ import annotations

from enum import IntEnum


class VersionField(IntEnum):
    """Identifies the position in a semantic version that should be incremented."""

    NONE = 0
    """No field is incremented; the pre-release number is bumped instead."""
    PATCH = 1
    """Increment the patch component."""
    MINOR = 2
    """Increment the minor component and reset patch to zero."""
    MAJOR = 3
    """Increment the major component and reset minor and patch to zero."""

    @classmethod
    def parse(cls, text: str) -> VersionField:
        """Parse an upstream name (``None``, ``Patch``, ``Minor``, ``Major``), case-insensitively.

        Raises:
            ValueError: If ``text`` is not a known field name.
        """
        lookup = {"none": cls.NONE, "patch": cls.PATCH, "minor": cls.MINOR, "major": cls.MAJOR}
        try:
            return lookup[text.strip().lower()]
        except KeyError:
            msg = f"unknown version field {text!r}; expected None, Patch, Minor or Major"
            raise ValueError(msg) from None

    @property
    def upstream_name(self) -> str:
        """The exact upstream spelling, used in JSON output (``VersionSourceIncrement``)."""
        return {0: "None", 1: "Patch", 2: "Minor", 3: "Major"}[int(self)]
