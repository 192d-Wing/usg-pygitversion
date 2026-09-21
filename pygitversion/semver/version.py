"""The semantic version value type.

Ports ``GitVersion.Core/SemVer/SemanticVersion.cs`` including the three
increment modes (``Standard``, ``Force``, ``EnsureIntegrity``) and the
"alternative versions" rule used by the calculator.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field, replace
from enum import Enum, StrEnum

from pygitversion.dotnet import regex as dotnet_regex
from pygitversion.errors import GitVersionError
from pygitversion.semver import patterns
from pygitversion.semver.build_metadata import BuildMetaData
from pygitversion.semver.prerelease import PreReleaseTag
from pygitversion.semver.version_field import VersionField


class SemanticVersionFormat(StrEnum):
    """Parsing leniency. Ports ``SemanticVersionFormat``."""

    STRICT = "Strict"
    """Only fully SemVer 2.0 compliant strings."""
    LOOSE = "Loose"
    """Also 1-, 2- and 4-part versions, leading zeros, and any tag text."""

    @classmethod
    def parse(cls, text: str) -> SemanticVersionFormat:
        """Parse ``Strict``/``Loose`` case-insensitively."""
        for member in cls:
            if member.value.lower() == text.strip().lower():
                return member
        msg = f"unknown semantic-version-format {text!r}; expected Strict or Loose"
        raise ValueError(msg)


class IncrementMode(Enum):
    """How :meth:`SemanticVersion.increment` treats an existing pre-release."""

    STANDARD = "Standard"
    """On a pre-release, bump the pre-release number; otherwise bump the field."""
    FORCE = "Force"
    """Always bump the field, even on a pre-release."""
    ENSURE_INTEGRITY = "EnsureIntegrity"
    """Bump the pre-release number only when the field bump would be redundant."""


class VersionParseError(GitVersionError):
    """A string could not be parsed as a semantic version."""


@functools.total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class SemanticVersion:
    """An immutable semantic version.

    Attributes:
        major: Major component.
        minor: Minor component.
        patch: Patch component.
        prerelease: Pre-release tag (empty when none).
        build_metadata: Build metadata (empty when none).
    """

    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: PreReleaseTag = field(default_factory=PreReleaseTag)
    build_metadata: BuildMetaData = field(default_factory=BuildMetaData)

    # -- construction --------------------------------------------------------

    @classmethod
    def empty(cls) -> SemanticVersion:
        """``0.0.0`` with no tag or metadata. Ports ``Empty``."""
        return cls()

    @classmethod
    def parse(
        cls,
        text: str,
        tag_prefix_regex: str | None = None,
        fmt: SemanticVersionFormat = SemanticVersionFormat.STRICT,
    ) -> SemanticVersion:
        """Parse or raise. Ports ``Parse``.

        Raises:
            VersionParseError: If ``text`` is not a version.
        """
        result = cls.try_parse(text, tag_prefix_regex, fmt)
        if result is None:
            msg = f"Failed to parse {text} into a Semantic Version"
            raise VersionParseError(msg)
        return result

    @classmethod
    def try_parse(
        cls,
        text: str,
        tag_prefix_regex: str | None = None,
        fmt: SemanticVersionFormat = SemanticVersionFormat.STRICT,
    ) -> SemanticVersion | None:
        """Parse, returning ``None`` on failure. Ports ``TryParse``.

        Args:
            text: Candidate such as ``v1.2.3-beta.1+5``.
            tag_prefix_regex: .NET-syntax regex for an optional prefix to
                strip (upstream default ``[vV]?``). ``None`` means no prefix.
            fmt: Strict or loose grammar.
        """
        # Upstream builds "^({prefix})(?<version>.*)$" and matches it first.
        prefix = tag_prefix_regex or ""
        wrapper = dotnet_regex.compile(f"^({prefix})(?<version>.*)$")
        m = wrapper.match(dotnet_regex.bounded(text))
        if m is None:
            return None
        body = m.group("version")
        return (
            cls._parse_strict(body)
            if fmt is SemanticVersionFormat.STRICT
            else cls._parse_loose(body)
        )

    @classmethod
    def _parse_strict(cls, text: str) -> SemanticVersion | None:
        """Ports ``TryParseStrict``."""
        m = patterns.STRICT.match(text)
        if m is None:
            return None
        return cls(
            major=int(m.group("major")),
            minor=int(m.group("minor")) if m.group("minor") is not None else 0,
            patch=int(m.group("patch")) if m.group("patch") is not None else 0,
            prerelease=PreReleaseTag.parse(m.group("prerelease")),
            build_metadata=BuildMetaData.parse(m.group("buildmetadata")),
        )

    @classmethod
    def _parse_loose(cls, text: str) -> SemanticVersion | None:
        """Ports ``TryParseLoose``. A fourth numeric part becomes the commit count."""
        m = patterns.LOOSE.match(text)
        if m is None:
            return None
        metadata = BuildMetaData.parse(m.group("BuildMetaData"))
        fourth = m.group("FourthPart")
        if fourth is not None and metadata.commits_since_tag is None:
            metadata = metadata.with_(commits_since_tag=int(fourth))
        return cls(
            major=int(m.group("Major")),
            minor=int(m.group("Minor")) if m.group("Minor") is not None else 0,
            patch=int(m.group("Patch")) if m.group("Patch") is not None else 0,
            prerelease=PreReleaseTag.parse(m.group("Tag")),
            build_metadata=metadata,
        )

    # -- queries -------------------------------------------------------------

    @property
    def is_prerelease(self) -> bool:
        """True when a pre-release tag is present. Ports ``IsPreRelease``."""
        return self.prerelease.has_tag()

    def is_empty(self) -> bool:
        """True when equal to :meth:`empty`."""
        return self == SemanticVersion()

    def is_labeled_with(self, label: str) -> bool:
        """True when the label matches ``label``, ignoring case. Ports ``IsLabeledWith``."""
        return self.prerelease.has_tag() and self.prerelease.name.casefold() == label.casefold()

    def is_match_for_branch_specific_label(self, label: str | None) -> bool:
        """Ports ``IsMatchForBranchSpecificLabel``.

        True when this version has no tag at all, or no label is supplied,
        or the label matches.
        """
        untagged = self.prerelease.name == "" and self.prerelease.number is None
        return untagged or label is None or self.is_labeled_with(label)

    def with_(self, **changes: object) -> SemanticVersion:
        """Return a copy with fields replaced."""
        return replace(self, **changes)  # type: ignore[arg-type]

    # -- equality / ordering -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Equal on all five components (metadata equality is partial, see ``BuildMetaData``)."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
            and self.build_metadata == other.build_metadata
        )

    def __hash__(self) -> int:
        """Hash consistent with :meth:`__eq__`."""
        return hash((self.major, self.minor, self.patch, self.prerelease, self.build_metadata))

    def compare_to(self, other: SemanticVersion | None, *, include_prerelease: bool = True) -> int:
        """Three-way compare. Ports ``CompareTo(value, includePreRelease)``.

        ``None`` sorts lowest. Build metadata never participates.
        """
        if other is None:
            return 1
        for a, b in (
            (self.major, other.major),
            (self.minor, other.minor),
            (self.patch, other.patch),
        ):
            if a != b:
                return 1 if a > b else -1
        if not include_prerelease or self.prerelease == other.prerelease:
            return 0
        return 1 if self.prerelease.compare_to(other.prerelease) > 0 else -1

    def __lt__(self, other: SemanticVersion) -> bool:
        """Ordering via :meth:`compare_to` including the pre-release tag."""
        return self.compare_to(other) < 0

    def is_greater_than(
        self, other: SemanticVersion | None, *, include_prerelease: bool = True
    ) -> bool:
        """Ports ``IsGreaterThan``."""
        return self.compare_to(other, include_prerelease=include_prerelease) > 0

    def is_less_than(
        self, other: SemanticVersion | None, *, include_prerelease: bool = True
    ) -> bool:
        """Ports ``IsLessThan``."""
        return self.compare_to(other, include_prerelease=include_prerelease) < 0

    def is_equal_to(
        self, other: SemanticVersion | None, *, include_prerelease: bool = True
    ) -> bool:
        """Ports ``IsEqualTo``."""
        return self.compare_to(other, include_prerelease=include_prerelease) == 0

    # -- formatting ----------------------------------------------------------

    def __str__(self) -> str:
        """Format ``s``: ``1.2.3-beta.4``."""
        return self.to_string("s")

    def to_string(self, fmt: str = "s") -> str:
        """Format with a specifier. Ports ``ToString(format)``.

        * ``j``: ``1.2.3``
        * ``s``: ``1.2.3-beta.4`` (default)
        * ``t``: same as ``s``
        * ``f``: ``1.2.3-beta.4+5``
        * ``i``: ``1.2.3-beta.4+5.Branch.main.Sha.abc``

        Raises:
            ValueError: For an unknown specifier.
        """
        f = (fmt or "s").lower()
        core = f"{self.major}.{self.minor}.{self.patch}"
        if f == "j":
            return core
        if f in ("s", "t"):
            return f"{core}-{self.prerelease}" if self.prerelease.has_tag() else core
        if f == "f":
            meta = self.build_metadata.to_string("b")
            return f"{self.to_string('s')}+{meta}" if meta else self.to_string("s")
        if f == "i":
            meta = self.build_metadata.to_string("f")
            return f"{self.to_string('s')}+{meta}" if meta else self.to_string("s")
        msg = f"Unknown format '{fmt}'."
        raise ValueError(msg)

    # -- incrementing --------------------------------------------------------

    def with_label(self, label: str | None) -> SemanticVersion:
        """Change only the pre-release label. Ports ``WithLabel``."""
        return self.increment(VersionField.NONE, label, mode=IncrementMode.STANDARD)

    def increment(
        self,
        field: VersionField,
        label: str | None,
        *alternatives: SemanticVersion | None,
        mode: IncrementMode = IncrementMode.STANDARD,
    ) -> SemanticVersion:
        """Return the next version. Ports ``Increment(increment, label, mode, alternatives)``.

        Args:
            field: Which component to bump.
            label: New pre-release label; ``None`` keeps the existing one.
            *alternatives: Candidate versions from other strategies. If any
                is greater than the bumped core (ignoring pre-release), it
                replaces the core, and with ``field == NONE`` the pre-release
                number resets to 1.
            mode: See :class:`IncrementMode`.
        """
        has_tag = self.prerelease.has_tag()
        major, minor, patch, number = self._apply_increment(field, mode, has_tag)

        chosen, found = self._select_alternative_if_greater(
            SemanticVersion(major, minor, patch), alternatives
        )
        major, minor, patch = chosen.major, chosen.minor, chosen.patch
        if found and field is VersionField.NONE:
            number = 1

        return self._build_incremented(major, minor, patch, number, has_tag, label)

    def _apply_increment(
        self, field: VersionField, mode: IncrementMode, has_tag: bool
    ) -> tuple[int, int, int, int | None]:
        """Ports ``ApplyIncrement``. Returns (major, minor, patch, prerelease number)."""
        number = self.prerelease.number
        if field is VersionField.NONE:
            return (self.major, self.minor, self.patch, _plus_one(number))
        if field is VersionField.PATCH:
            integrity = self.patch != 0
            return self._increment_field(
                mode, has_tag, integrity, self.major, self.minor, self.patch + 1, number
            )
        if field is VersionField.MINOR:
            integrity = self.minor != 0 and self.patch == 0
            return self._increment_field(
                mode, has_tag, integrity, self.major, self.minor + 1, 0, number
            )
        integrity = self.major != 0 and self.minor == 0 and self.patch == 0
        return self._increment_field(mode, has_tag, integrity, self.major + 1, 0, 0, number)

    def _increment_field(
        self,
        mode: IncrementMode,
        has_tag: bool,
        integrity: bool,
        bumped_major: int,
        bumped_minor: int,
        bumped_patch: int,
        number: int | None,
    ) -> tuple[int, int, int, int | None]:
        """Ports ``IncrementField``."""
        if _should_increment_prerelease_number(mode, has_tag, integrity):
            return (self.major, self.minor, self.patch, _plus_one(number))
        return (bumped_major, bumped_minor, bumped_patch, 1 if number is not None else number)

    @staticmethod
    def _select_alternative_if_greater(
        version: SemanticVersion, alternatives: tuple[SemanticVersion | None, ...]
    ) -> tuple[SemanticVersion, bool]:
        """Ports ``SelectAlternativeIfGreater``."""
        found = False
        for alt in alternatives:
            if alt is None or not version.is_less_than(alt, include_prerelease=False):
                continue
            version = alt
            found = True
        return version, found

    def _build_incremented(
        self,
        major: int,
        minor: int,
        patch: int,
        number: int | None,
        has_tag: bool,
        label: str | None,
    ) -> SemanticVersion:
        """Ports ``BuildIncrementedVersion``."""
        if has_tag:
            name = self.prerelease.name
        else:
            number = 1
            name = ""
        if label is not None and name != label:
            number = 1
            name = label
        return replace(
            self,
            major=major,
            minor=minor,
            patch=patch,
            prerelease=PreReleaseTag(name, number, True),
        )


def _plus_one(value: int | None) -> int | None:
    """``long? + 1`` semantics: ``None`` stays ``None``."""
    return None if value is None else value + 1


def _should_increment_prerelease_number(
    mode: IncrementMode, has_tag: bool, integrity: bool
) -> bool:
    """Ports ``ShouldIncrementPreReleaseNumber``."""
    return has_tag and (
        mode is IncrementMode.STANDARD or (mode is IncrementMode.ENSURE_INTEGRITY and integrity)
    )
