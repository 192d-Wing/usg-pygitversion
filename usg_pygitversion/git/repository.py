# SPDX-License-Identifier: MIT
"""Read-only repository facade over :class:`~usg_pygitversion.git.command.GitCommand`.

Ports the subset of ``IGitRepository`` that version calculation needs:
``Head``, ``Branches``, ``Tags``, commit lookup, commit walks, merge-base
and ancestry checks, and the uncommitted-changes count.

Memory (PLAN.md 9.4): commit walks stream from ``git log`` and stop after
``max_commits``; the per-SHA commit cache is bounded; refs are loaded once
per instance (a run is short-lived) and are small.

Security (AC-3, AC-6, SI-10): the repository is only ever read. Paths handed
to git are validated; ref names come from git itself or from callers who
already validated them, and are passed as discrete argv entries. Every
revision argument is preceded by ``--end-of-options`` (git >= 2.24) so a
value such as ``--output=<file>`` can never be parsed as an option, whatever
the caller did or did not validate.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Generator, Iterable, Iterator
from datetime import datetime
from pathlib import Path

from usg_pygitversion.errors import GitCommandError, RepositoryError
from usg_pygitversion.git.command import GitCommand
from usg_pygitversion.git.models import DETACHED_HEAD_CANONICAL, Branch, Commit, Tag
from usg_pygitversion.git.refname import ReferenceName

_log = logging.getLogger("usg_pygitversion.git")

#: Hard cap on commits visited in a single walk. Exceeding it is an error
#: rather than a memory blow-up (PLAN.md 9.4).
DEFAULT_MAX_COMMITS = 200_000

#: ``git log`` record format. NUL-separated fields, record terminated by a
#: second NUL so multi-line messages are unambiguous.
#:   %H  sha   %P parents   %cI committer date ISO-8601   %B raw body
_LOG_FORMAT = "--format=%H%x00%P%x00%cI%x00%B%x00"

#: Marker after which git treats every remaining argument as a revision or
#: path, never an option (SI-10). Placed before any revision that did not
#: originate from git itself.
_END_OF_OPTIONS = "--end-of-options"


class GitRepository:
    """A git working tree or bare repository opened for reading.

    Args:
        path: Any directory inside the working tree (or the ``.git`` dir).
        max_commits: Cap for commit walks.

    Raises:
        RepositoryError: If ``path`` is not inside a git repository.
    """

    def __init__(self, path: Path | str = ".", *, max_commits: int = DEFAULT_MAX_COMMITS) -> None:
        """Open the repository containing ``path``."""
        start = Path(path).resolve()
        if not start.is_dir():
            msg = f"{start} is not a directory"
            raise RepositoryError(msg)
        self.max_commits = max_commits
        probe = GitCommand(start)
        try:
            git_dir = probe.run("rev-parse", "--absolute-git-dir")
            toplevel = probe.run("rev-parse", "--show-toplevel", check=False)
        except GitCommandError as exc:
            msg = f"{start} is not a git repository"
            raise RepositoryError(msg) from exc
        self.git_dir = Path(git_dir).resolve()
        # Bare repositories have no toplevel; fall back to the git dir.
        self.working_tree = Path(toplevel).resolve() if toplevel else self.git_dir
        self.git = GitCommand(self.working_tree)
        self._commit_cache: dict[str, Commit] = {}

    # -- HEAD ----------------------------------------------------------------

    def head_sha(self) -> str | None:
        """SHA of ``HEAD``, or ``None`` for an empty repository."""
        out = self.git.run("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        return out or None

    def head(self) -> Branch:
        """The current branch, or the detached-HEAD sentinel. Ports ``IGitRepository.Head``.

        Raises:
            RepositoryError: On an empty repository (no commits).
        """
        sha = self.head_sha()
        if sha is None:
            raise RepositoryError("repository has no commits")
        symbolic = self.git.run("symbolic-ref", "--quiet", "HEAD", check=False)
        if symbolic:
            return Branch(ReferenceName(symbolic), sha)
        return Branch(ReferenceName(DETACHED_HEAD_CANONICAL), sha)

    def is_head_detached(self) -> bool:
        """True when ``HEAD`` does not point at a branch."""
        return not self.git.run("symbolic-ref", "--quiet", "HEAD", check=False)

    def remotes(self) -> tuple[str, ...]:
        """Configured remote names (``git remote``)."""
        out = self.git.run("remote")
        return tuple(line for line in out.splitlines() if line)

    # -- refs ----------------------------------------------------------------

    @functools.cached_property
    def branches(self) -> tuple[Branch, ...]:
        """All local and remote-tracking branches, sorted by canonical name."""
        out = self.git.run(
            "for-each-ref",
            "--format=%(refname)%00%(objectname)%00%(upstream)",
            "refs/heads/",
            "refs/remotes/",
        )
        result: list[Branch] = []
        for line in out.splitlines():
            if not line:
                continue
            refname, sha, upstream = line.split("\x00", 2)
            # Symbolic refs such as refs/remotes/origin/HEAD are not branches.
            if refname.endswith("/HEAD"):
                continue
            result.append(Branch(ReferenceName(refname), sha, is_tracking=bool(upstream)))
        return tuple(sorted(result, key=lambda b: b.name.canonical))

    @functools.cached_property
    def tags(self) -> tuple[Tag, ...]:
        """All tags with annotated tags peeled to their commit, sorted by name."""
        out = self.git.run(
            "for-each-ref",
            "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%(taggerdate:iso-strict)",
            "refs/tags/",
        )
        result: list[Tag] = []
        for line in out.splitlines():
            if not line:
                continue
            refname, objtype, objname, peeled, tagger_date = line.split("\x00", 4)
            annotated = objtype == "tag"
            target = peeled if annotated and peeled else objname
            when = datetime.fromisoformat(tagger_date) if annotated and tagger_date else None
            result.append(Tag(ReferenceName(refname), target, annotated, when))
        return tuple(sorted(result, key=lambda t: t.name.canonical))

    def find_branch(self, name: str) -> Branch | None:
        """Look up a branch by canonical, friendly or origin-less name."""
        for branch in self.branches:
            if branch.name.equivalent_to(name):
                return branch
        return None

    # -- commits -------------------------------------------------------------

    def commit(self, sha: str) -> Commit:
        """Load one commit by SHA (or any revision expression), cached.

        Raises:
            RepositoryError: If the revision does not resolve to a commit.
        """
        cached = self._commit_cache.get(sha)
        if cached is not None:
            return cached
        try:
            out = self.git.run("log", "-1", _LOG_FORMAT, _END_OF_OPTIONS, sha, "--")
        except GitCommandError as exc:
            msg = f"unknown revision {sha!r}"
            raise RepositoryError(msg) from exc
        commits = list(self._parse_log(out.split("\n")))
        if not commits:
            msg = f"unknown revision {sha!r}"
            raise RepositoryError(msg)
        commit = commits[0]
        self._remember(commit)
        return commit

    def _remember(self, commit: Commit) -> None:
        """Insert into the bounded commit cache (evicts arbitrarily when full)."""
        if len(self._commit_cache) >= self.max_commits:
            self._commit_cache.pop(next(iter(self._commit_cache)))
        self._commit_cache[commit.sha] = commit

    def walk(
        self,
        include: str | Iterable[str],
        exclude: Iterable[str] = (),
        *,
        first_parent: bool = False,
        paths: Iterable[str] = (),
        order: str = "default",
    ) -> Generator[Commit, None, None]:
        """Stream commits reachable from ``include`` but not ``exclude``.

        Equivalent to ``git log <include> ^<exclude>``. The default order is
        git's (reverse chronological by commit date), which matches
        libgit2's ``GIT_SORT_TIME`` that upstream's ``Branch.Commits`` uses.
        Stops after ``max_commits`` with an error rather than growing without
        bound.

        Args:
            include: Revision(s) to start from.
            exclude: Revision(s) whose ancestry is excluded.
            first_parent: Follow only first parents (mainline walks).
            paths: Restrict to commits touching these paths.
            order: ``"default"``, ``"date"`` (``--date-order``, upstream
                ``Topological | Time``) or ``"topo-reverse"``
                (``--topo-order --reverse``, upstream ``Topological | Reverse``).

        Yields:
            :class:`Commit` objects, newest first.

        Raises:
            RepositoryError: If the walk exceeds ``max_commits``.
        """
        includes = [include] if isinstance(include, str) else list(include)
        args = ["log", _LOG_FORMAT]
        if first_parent:
            args.append("--first-parent")
        if order == "date":
            args.append("--date-order")
        elif order == "topo-reverse":
            args += ["--topo-order", "--reverse"]
        elif order != "default":
            msg = f"unknown walk order {order!r}"
            raise ValueError(msg)
        args.append(_END_OF_OPTIONS)
        args += includes
        args += [f"^{rev}" for rev in exclude]
        args.append("--")
        args += list(paths)

        for count, commit in enumerate(self._parse_log(self.git.stream(*args)), start=1):
            if count > self.max_commits:
                msg = f"commit walk exceeded the limit of {self.max_commits} commits"
                raise RepositoryError(msg)
            self._remember(commit)
            yield commit

    @staticmethod
    def _parse_log(lines: Iterable[str]) -> Iterator[Commit]:
        """Parse NUL-delimited ``git log`` records from a line stream.

        Records are ``sha NUL parents NUL date NUL body NUL`` and the body may
        contain newlines, so lines are accumulated until four NULs have
        been seen.
        """
        buffer: list[str] = []
        nul_count = 0
        for line in lines:
            buffer.append(line)
            nul_count += line.count("\x00")
            if nul_count >= 4:  # noqa: PLR2004 -- four fields per record
                record = "\n".join(buffer)
                sha, parents, when, body = record.split("\x00", 3)
                body = body.rstrip("\x00\n")
                yield Commit(
                    sha=sha,
                    parents=tuple(parents.split()) if parents else (),
                    when=datetime.fromisoformat(when),
                    message=body,
                )
                buffer = []
                nul_count = 0

    # -- graph queries -------------------------------------------------------

    def merge_base(self, a: str, b: str) -> str | None:
        """Best common ancestor of two revisions, or ``None`` if unrelated."""
        out = self.git.run("merge-base", _END_OF_OPTIONS, a, b, check=False)
        return out or None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """True when ``ancestor`` is reachable from ``descendant``."""
        try:
            self.git.run("merge-base", "--is-ancestor", _END_OF_OPTIONS, ancestor, descendant)
        except GitCommandError as exc:
            if exc.returncode == 1:
                return False
            raise
        return True

    def count_commits(self, include: str, exclude: Iterable[str] = ()) -> int:
        """``git rev-list --count include ^exclude``."""
        args = [
            "rev-list",
            "--count",
            _END_OF_OPTIONS,
            include,
            *[f"^{rev}" for rev in exclude],
            "--",
        ]
        return int(self.git.run(*args) or "0")

    def changed_paths(self, sha: str) -> tuple[str, ...]:
        """Paths touched by a commit (against its first parent, or the empty tree for a root)."""
        out = self.git.run(
            "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", _END_OF_OPTIONS, sha
        )
        return tuple(line for line in out.splitlines() if line)

    # -- working tree --------------------------------------------------------

    def uncommitted_changes(self) -> int:
        """Number of modified, added, deleted or untracked entries.

        Ports ``IGitRepository.UncommittedChangesCount``. Returns 0 for a bare
        repository.
        """
        if self.working_tree == self.git_dir:
            return 0
        out = self.git.run("status", "--porcelain", "--untracked-files=all", "--no-renames")
        return sum(1 for line in out.splitlines() if line)
