# SPDX-License-Identifier: MIT
"""Pre-release label and number of a semantic version (``beta.1``).

Ports ``GitVersion.Core/SemVer/SemanticVersionPreReleaseTag.cs``.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Self

from pygitversion.semver import patterns

_log = logging.getLogger("pygitversion.semver")


@functools.total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class PreReleaseTag:
    """The pre-release part of a version: a label and an optional number.

    Equality and ordering consider only ``name`` and ``number``;
    ``promote_tag_even_if_name_is_empty`` is a formatting hint, exactly as
    upstream's ``LambdaEqualityHelper(x => x.Name, x => x.Number)``.

    Attributes:
        name: The label, e.g. ``beta``. Empty for a bare number (``1.2.3-4``).
        number: The numeric suffix, or ``None``.
        promote_tag_even_if_name_is_empty: When true, a tag with an empty
            name but a number still counts as "having a tag".
    """

    name: str = ""
    number: int | None = None
    promote_tag_even_if_name_is_empty: bool = False

    # -- construction --------------------------------------------------------

    @classmethod
    def empty(cls) -> Self:
        """The empty tag (no name, no number). Ports ``Empty``."""
        return cls()

    @classmethod
    def parse(cls, text: str | None) -> Self:
        """Parse ``beta.3``, ``beta3``, ``3`` or ``beta`` into a tag.

        Ports ``SemanticVersionPreReleaseTag.Parse``. Upstream logs and
        returns ``Empty`` on failure rather than raising; the pattern can
        match any string so failure is theoretical, but the behaviour is kept.
        A name ending in ``-`` (e.g. ``beta-3``) is kept whole with no number,
        because ``1.2.3-beta-3`` is a single label under SemVer 2.0.
        """
        if not text:
            return cls()
        match = patterns.PRERELEASE_TAG.match(text)
        if match is None:  # pragma: no cover -- pattern matches everything
            _log.warning("unable to parse pre-release tag %r", text)
            return cls()
        name = match.group("name")
        number_text = match.group("number")
        number = int(number_text) if number_text is not None else None
        if name.endswith("-"):
            return cls(text, None, True)
        return cls(name, number, True)

    # -- queries -------------------------------------------------------------

    def has_tag(self) -> bool:
        """True when there is a name, or a number with the promote flag. Ports ``HasTag``."""
        return bool(self.name) or (
            self.number is not None and self.promote_tag_even_if_name_is_empty
        )

    # -- equality / ordering -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Equal when name and number match (name compared case-sensitively, as upstream)."""
        if not isinstance(other, PreReleaseTag):
            return NotImplemented
        return self.name == other.name and self.number == other.number

    def __hash__(self) -> int:
        """Hash on name and number only."""
        return hash((self.name, self.number))

    def compare_to(self, other: PreReleaseTag | None) -> int:
        """Three-way compare. Ports ``CompareTo``.

        Rules, in order:

        1. No tag sorts *after* a tag (a release beats its pre-releases).
        2. Names compare case-insensitively.
        3. Numbers compare with ``None`` lowest.

        Deviation note: upstream uses ``StringComparer.InvariantCultureIgnoreCase``,
        a linguistic comparison. Python compares case-folded code points.
        These agree for ASCII alphanumerics and ``-``/``.``, which is what
        SemVer permits in labels; see ``docs/deviations.md``.
        """
        other_has = other is not None and other.has_tag()
        if self.has_tag() != other_has:
            # Rule 1: the untagged (release) side sorts after the tagged side.
            return 1 if other_has else -1
        other_name = other.name if other is not None else ""
        a, b = self.name.casefold(), other_name.casefold()
        if a != b:
            return -1 if a < b else 1
        other_number = other.number if other is not None else None
        # Nullable.Compare: None is less than any value.
        left = -1 if self.number is None else self.number
        right = -1 if other_number is None else other_number
        return (left > right) - (left < right)

    def __lt__(self, other: PreReleaseTag) -> bool:
        """Ordering via :meth:`compare_to`."""
        return self.compare_to(other) < 0

    # -- formatting ----------------------------------------------------------

    def __str__(self) -> str:
        """Format ``t``: ``beta.1``, ``beta``, ``1`` or ``""``. Ports ``ToString``."""
        if self.number is None:
            return self.name
        return f"{self.number}" if not self.name else f"{self.name}.{self.number}"

    def to_string(self, fmt: str = "t") -> str:
        """Format with a specifier; only ``t`` exists. Ports ``ToString(format)``.

        Raises:
            ValueError: For any specifier other than ``t``.
        """
        if (fmt or "t").lower() != "t":
            msg = f"Unknown format '{fmt}'."
            raise ValueError(msg)
        return str(self)
