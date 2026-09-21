# SPDX-License-Identifier: MIT
"""Build metadata attached to a semantic version (``+5.Branch.main.Sha.abc``).

Ports ``GitVersion.Core/SemVer/SemanticVersionBuildMetaData.cs`` (6.8.2). Upstream
carries a number of "source" fields on this type that the calculator fills
in (version source SHA, distance, increment, uncommitted changes). They are
modelled here so the variable provider (Phase 3) can populate them, but
only ``commits_since_tag``, ``branch`` and ``sha`` participate in equality,
exactly as upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Self

from pygitversion.semver import patterns
from pygitversion.semver.version_field import VersionField

if TYPE_CHECKING:
    from pygitversion.semver.version import SemanticVersion


@dataclass(frozen=True, slots=True, eq=False)
class BuildMetaData:
    """Build metadata for a version.

    Attributes:
        commits_since_tag: Number of commits since the version source.
        branch: Branch name the version was calculated on.
        sha: Full commit SHA.
        short_sha: Abbreviated SHA.
        other_metadata: Free-form trailing metadata.
        commit_date: Date of the commit.
        version_source_semver: Baseline version (legacy naming kept for JSON).
        version_source_sha: SHA used as the counting anchor.
        version_source_distance: Non-ignored commits beyond the anchor.
        uncommitted_changes: Count of uncommitted changes in the working tree.
        version_source_increment: Increment applied relative to the baseline.
    """

    commits_since_tag: int | None = None
    branch: str | None = None
    sha: str | None = None
    short_sha: str | None = None
    other_metadata: str | None = None
    commit_date: datetime | None = None
    version_source_semver: SemanticVersion | None = None
    version_source_sha: str | None = None
    version_source_distance: int = 0
    uncommitted_changes: int = 0
    version_source_increment: VersionField = VersionField.NONE

    @property
    def commits_since_version_source(self) -> int:
        """Alias of ``version_source_distance`` (upstream ``CommitsSinceVersionSource``)."""
        return self.version_source_distance

    @classmethod
    def empty(cls) -> Self:
        """Metadata with nothing set. Ports ``Empty``."""
        return cls()

    @classmethod
    def parse(cls, text: str | None) -> Self:
        """Parse ``4.Branch.main.Sha.abc.other`` style metadata. Ports ``Parse``.

        The pattern matches any string, so this never fails: unrecognised
        content lands in ``other_metadata`` with a leading dot stripped.
        """
        if not text:
            return cls()
        m = patterns.BUILD_METADATA.match(text)
        if m is None:  # pragma: no cover -- pattern matches everything
            return cls()
        commits: int | None = None
        distance = 0
        if m.group("BuildNumber") is not None:
            commits = int(m.group("BuildNumber"))
            distance = commits
        other = m.group("Other")
        return cls(
            commits_since_tag=commits,
            version_source_distance=distance,
            branch=m.group("BranchName"),
            sha=m.group("Sha"),
            other_metadata=other.lstrip(".") if other else None,
        )

    def with_(self, **changes: object) -> BuildMetaData:
        """Return a copy with fields replaced (``dataclasses.replace`` wrapper)."""
        return replace(self, **changes)  # type: ignore[arg-type]

    # -- equality ------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Equal on commits-since-tag, branch and SHA only, as upstream."""
        if not isinstance(other, BuildMetaData):
            return NotImplemented
        return (
            self.commits_since_tag == other.commits_since_tag
            and self.branch == other.branch
            and self.sha == other.sha
        )

    def __hash__(self) -> int:
        """Hash on the same three fields as equality."""
        return hash((self.commits_since_tag, self.branch, self.sha))

    # -- formatting ----------------------------------------------------------

    @staticmethod
    def _part(value: str) -> str:
        """Replace characters not valid in metadata with ``-``. Ports ``FormatMetaDataPart``."""
        return patterns.FORMAT_BUILD_METADATA.sub("-", value) if value else value

    def __str__(self) -> str:
        """Format ``b``: just the commit count (or empty)."""
        return self.to_string("b")

    def to_string(self, fmt: str = "b") -> str:
        """Format with a specifier. Ports ``ToString(format)``.

        * ``b``: build number only, e.g. ``5``
        * ``s``: build number and SHA, e.g. ``5.Sha.abc``
        * ``f``: full, e.g. ``5.Branch.main.Sha.abc.other``

        Raises:
            ValueError: For an unknown specifier.
        """
        f = (fmt or "b").lower()
        count = "" if self.commits_since_tag is None else str(self.commits_since_tag)
        if f == "b":
            return count
        sha_part = f".Sha.{self.sha}" if self.sha else ""
        if f == "s":
            return f"{count}{sha_part}".lstrip(".")
        if f == "f":
            branch_part = f".Branch.{self._part(self.branch)}" if self.branch else ""
            other_part = f".{self._part(self.other_metadata)}" if self.other_metadata else ""
            return f"{count}{branch_part}{sha_part}{other_part}".lstrip(".")
        msg = f"Unknown format '{fmt}'."
        raise ValueError(msg)
