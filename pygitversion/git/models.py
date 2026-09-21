# SPDX-License-Identifier: MIT
"""Immutable value objects describing repository state.

Ports the shape of ``ICommit``, ``IBranch`` and ``ITag`` from
``GitVersion.Core/Git``. Only the fields the calculator reads are modelled.
Memory notes (PLAN.md 9.4): all types use ``__slots__`` via ``slots=True``,
parents are tuples not lists, and commit messages are stored once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pygitversion.git.refname import ReferenceName


@dataclass(frozen=True, slots=True)
class Commit:
    """A commit.

    Attributes:
        sha: Full 40-hex object id.
        parents: Parent SHAs in order (first parent first).
        when: Committer date, timezone-aware. Upstream's ``ICommit.When``.
        message: Full commit message (subject and body).
    """

    sha: str
    parents: tuple[str, ...]
    when: datetime
    message: str

    @property
    def short_sha(self) -> str:
        """First seven characters, as the ``ShortSha`` output variable."""
        return self.sha[:7]

    @property
    def is_merge(self) -> bool:
        """True for a commit with more than one parent."""
        return len(self.parents) > 1

    def __str__(self) -> str:
        """The short SHA."""
        return self.short_sha


@dataclass(frozen=True, slots=True)
class Branch:
    """A local or remote-tracking branch.

    Attributes:
        name: Reference name.
        tip: SHA the branch points at.
    """

    name: ReferenceName
    tip: str

    @property
    def is_remote(self) -> bool:
        """True for ``refs/remotes/`` branches."""
        return self.name.is_remote_branch

    @property
    def is_detached_head(self) -> bool:
        """True for the synthetic ``(no branch)`` used when HEAD is detached."""
        return self.name.canonical == DETACHED_HEAD_CANONICAL

    def __str__(self) -> str:
        """The friendly name."""
        return self.name.friendly


@dataclass(frozen=True, slots=True)
class Tag:
    """A tag, lightweight or annotated.

    Attributes:
        name: Reference name (``refs/tags/v1.0``).
        target: SHA of the *commit* the tag ultimately points at (annotated
            tags are peeled).
        is_annotated: True for annotated tag objects.
        tagged_when: Tagger date for annotated tags, else ``None``.
    """

    name: ReferenceName
    target: str
    is_annotated: bool
    tagged_when: datetime | None

    def __str__(self) -> str:
        """The friendly name."""
        return self.name.friendly


#: Canonical name used for a detached ``HEAD``; matches libgit2's
#: ``(no branch)`` which upstream relies on.
DETACHED_HEAD_CANONICAL = "(no branch)"
