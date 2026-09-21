"""Git reference names in canonical and friendly forms.

Ports ``GitVersion.Core/Git/ReferenceName.cs`` exactly, including the
pull-request prefixes and the ``origin/`` stripping rules used by branch
matching.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

LOCAL_BRANCH_PREFIX = "refs/heads/"
REMOTE_TRACKING_BRANCH_PREFIX = "refs/remotes/"
TAG_PREFIX = "refs/tags/"
_ORIGIN_PREFIX = "origin/"
_PULL_REQUEST_PREFIXES: tuple[str, ...] = (
    "refs/pull/",
    "refs/pull-requests/",
    "refs/remotes/pull/",
    "refs/remotes/pull-requests/",
)


@functools.total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class ReferenceName:
    """A reference such as ``refs/heads/main``.

    Attributes:
        canonical: Full name (``refs/heads/main``).
        friendly: Shortened (``main``, ``origin/main``, ``v1.0``).
        without_origin: Friendly with a leading ``origin/`` removed for
            remote branches.
        without_remote: Friendly with any remote name removed.
        is_local_branch: ``refs/heads/`` reference.
        is_remote_branch: ``refs/remotes/`` reference.
        is_tag: ``refs/tags/`` reference.
        is_pull_request: One of the known pull-request ref namespaces.
    """

    canonical: str
    friendly: str = field(init=False)
    without_origin: str = field(init=False)
    without_remote: str = field(init=False)
    is_local_branch: bool = field(init=False)
    is_remote_branch: bool = field(init=False)
    is_tag: bool = field(init=False)
    is_pull_request: bool = field(init=False)

    def __post_init__(self) -> None:
        """Derive every view from ``canonical``."""
        c = self.canonical
        set_ = object.__setattr__  # frozen dataclass
        set_(self, "is_local_branch", c.startswith(LOCAL_BRANCH_PREFIX))
        set_(self, "is_remote_branch", c.startswith(REMOTE_TRACKING_BRANCH_PREFIX))
        set_(self, "is_tag", c.startswith(TAG_PREFIX))
        set_(self, "is_pull_request", c.startswith(_PULL_REQUEST_PREFIXES))
        set_(self, "friendly", self._shorten())
        set_(self, "without_origin", self._remove_origin())
        set_(self, "without_remote", self._remove_remote())

    # -- construction --------------------------------------------------------

    @classmethod
    def try_parse(cls, canonical: str) -> ReferenceName | None:
        """Return a reference if ``canonical`` has a known prefix, else ``None``."""
        if canonical.startswith(
            (
                LOCAL_BRANCH_PREFIX,
                REMOTE_TRACKING_BRANCH_PREFIX,
                TAG_PREFIX,
                *_PULL_REQUEST_PREFIXES,
            )
        ):
            return cls(canonical)
        return None

    @classmethod
    def parse(cls, canonical: str) -> ReferenceName:
        """Parse a canonical name or raise. Ports ``Parse``.

        Raises:
            ValueError: If ``canonical`` lacks a recognised prefix.
        """
        ref = cls.try_parse(canonical)
        if ref is None:
            msg = f"{canonical!r} is not a canonical reference name"
            raise ValueError(msg)
        return ref

    @classmethod
    def from_branch_name(cls, name: str) -> ReferenceName:
        """Accept ``main`` or ``refs/heads/main``. Ports ``FromBranchName``."""
        return cls.try_parse(name) or cls(LOCAL_BRANCH_PREFIX + name)

    @classmethod
    def from_tag_name(cls, name: str) -> ReferenceName:
        """Always prefix with ``refs/tags/``. Ports ``FromTagName``.

        Raises:
            ValueError: If ``name`` is empty.
        """
        if not name:
            raise ValueError("tag name must not be empty")
        return cls(TAG_PREFIX + name)

    # -- derived views -------------------------------------------------------

    def _shorten(self) -> str:
        if self.is_local_branch:
            return self.canonical[len(LOCAL_BRANCH_PREFIX) :]
        if self.is_remote_branch:
            return self.canonical[len(REMOTE_TRACKING_BRANCH_PREFIX) :]
        if self.is_tag:
            return self.canonical[len(TAG_PREFIX) :]
        return self.canonical

    def _remove_origin(self) -> str:
        if (
            self.is_remote_branch
            and not self.is_pull_request
            and self.friendly.startswith(_ORIGIN_PREFIX)
        ):
            return self.friendly[len(_ORIGIN_PREFIX) :]
        return self.friendly

    def _remove_remote(self) -> str:
        if self.is_remote_branch and not self.is_pull_request:
            idx = self.friendly.find("/")
            if idx >= 0:
                return self.friendly[idx + 1 :]
        return self.friendly

    # -- comparison ----------------------------------------------------------

    def equivalent_to(self, name: str | None) -> bool:
        """True when ``name`` matches canonical, friendly or origin-stripped form, ignoring case."""
        if name is None:
            return False
        n = name.casefold()
        return n in (
            self.canonical.casefold(),
            self.friendly.casefold(),
            self.without_origin.casefold(),
        )

    def __eq__(self, other: object) -> bool:
        """Equal on canonical name."""
        if not isinstance(other, ReferenceName):
            return NotImplemented
        return self.canonical == other.canonical

    def __hash__(self) -> int:
        """Hash on canonical name."""
        return hash(self.canonical)

    def __lt__(self, other: ReferenceName) -> bool:
        """Order by canonical name."""
        return self.canonical < other.canonical

    def __str__(self) -> str:
        """The friendly name."""
        return self.friendly
