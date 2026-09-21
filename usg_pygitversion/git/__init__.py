# SPDX-License-Identifier: MIT
"""Read-only access to a git repository through the ``git`` binary.

Design (PLAN.md D1, 9.3, 9.4):

* :mod:`usg_pygitversion.git.command` is the **only** place in the package that
  spawns a subprocess. Everything else goes through it.
* The repository is never modified: no ref updates, no checkout, no config
  writes, no fetch unless the caller explicitly opts in (Phase 5).
* Output is streamed and bounded; nothing loads unbounded history.
"""

from usg_pygitversion.git.command import GitCommand
from usg_pygitversion.git.models import Branch, Commit, Tag
from usg_pygitversion.git.refname import ReferenceName
from usg_pygitversion.git.repository import GitRepository

__all__ = ["Branch", "Commit", "GitCommand", "GitRepository", "ReferenceName", "Tag"]
