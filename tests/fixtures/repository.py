# SPDX-License-Identifier: MIT
"""A small DSL for building real git repositories in tests.

Ports the intent of upstream ``GitVersion.Testing/Fixtures/RepositoryFixtureBase``
(``MakeACommit``, ``MakeATaggedCommit``, ``BranchTo``, ``Checkout``,
``MergeTo``, ``ApplyTag`` ...). Scenario tests translated from the C# suite
read almost line for line against this class, which keeps the port
reviewable against upstream.

Design notes:

* Real repositories, real ``git``. The production code shells out to git,
  so the tests must too; a fake object model would test the wrong thing.
* Deterministic history. Author, committer, dates and time zone are fixed
  per commit so that SHAs are reproducible across machines and CI runs,
  which makes golden-file and differential tests stable.
* Hermetic. Every git call runs with a minimal environment: no user
  ``~/.gitconfig``, no global hooks, no credential helpers, ``LC_ALL=C``.
  This mirrors the hardening in the production ``GitCommand`` wrapper
  (PLAN.md 9.3) and stops a developer's local config from changing results.
* Resource-safe. The fixture is a context manager that owns a
  ``TemporaryDirectory``; nothing relies on ``__del__`` (PLAN.md 9.4).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Self


def _find_git() -> str:
    """Locate the git binary once at import time; the suite cannot run without it."""
    found = shutil.which("git")
    if found is None:  # pragma: no cover
        msg = "git binary not found on PATH; pygitversion tests require git"
        raise RuntimeError(msg)
    return found


_GIT: str = _find_git()

#: Fixed identity so commit SHAs are reproducible.
_AUTHOR_NAME = "GitVersion Test"
_AUTHOR_EMAIL = "test@example.invalid"
#: First commit timestamp; each subsequent commit is one minute later.
_EPOCH = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)


class RepositoryFixture:
    """A throw-away git repository with helpers that mirror upstream's fixture.

    Use as a context manager::

        with RepositoryFixture() as repo:
            repo.make_a_commit()
            repo.apply_tag("1.0.0")
            repo.branch_to("feature/x")
            repo.make_a_commit()
            assert repo.head_sha ...

    Args:
        default_branch: Name of the initial branch. Upstream fixtures default
            to ``main``.
    """

    def __init__(self, default_branch: str = "main") -> None:
        """Create the temporary directory and initialise an empty repository."""
        self._tmp = tempfile.TemporaryDirectory(prefix="pygitversion-test-")
        self.path = Path(self._tmp.name).resolve()
        self._clock = _EPOCH
        self._commit_count = 0
        self.default_branch = default_branch
        self.git("init", "--quiet", f"--initial-branch={default_branch}")
        # Repository-local config only; global/system config is disabled in env.
        self.git("config", "user.name", _AUTHOR_NAME)
        self.git("config", "user.email", _AUTHOR_EMAIL)
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> Self:
        """Return self; the repository is already initialised."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Remove the temporary directory."""
        self.close()

    def close(self) -> None:
        """Delete the repository. Safe to call more than once."""
        self._tmp.cleanup()

    # -- low-level ---------------------------------------------------------

    def git(self, *args: str, check: bool = True) -> str:
        """Run ``git`` inside the fixture and return stripped stdout.

        The environment is minimal and hermetic (see module docstring).
        Dates are injected for both author and committer so SHAs are stable.

        Args:
            *args: Arguments after ``git``.
            check: Raise on non-zero exit when true.

        Returns:
            Standard output with trailing whitespace removed.

        Raises:
            subprocess.CalledProcessError: If ``check`` and git fails.
        """
        stamp = self._clock.strftime("%Y-%m-%dT%H:%M:%S%z")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.path),  # no ~/.gitconfig leakage
            "LC_ALL": "C",
            "TZ": "UTC",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": _AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": _AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": _AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": _AUTHOR_EMAIL,
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_DATE": stamp,
        }
        # Windows needs SYSTEMROOT for subprocess creation.
        if os.name == "nt":  # pragma: no cover
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
        # Argument list, no shell, hermetic environment (see module docstring).
        result = subprocess.run(
            [_GIT, "-c", "core.hooksPath=" + os.devnull, *args],
            cwd=self.path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )
        return result.stdout.rstrip()

    def _tick(self) -> None:
        """Advance the fixture clock so each commit gets a distinct date."""
        self._clock += timedelta(minutes=1)

    # -- upstream-style helpers ---------------------------------------------

    @property
    def head_sha(self) -> str:
        """Full SHA of ``HEAD``."""
        return self.git("rev-parse", "HEAD")

    @property
    def current_branch(self) -> str:
        """Short name of the checked-out branch, or ``HEAD`` when detached.

        Uses ``symbolic-ref`` so it also works on a freshly initialised
        repository with no commits, where ``rev-parse HEAD`` fails.
        """
        name = self.git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        return name or "HEAD"

    def make_a_commit(self, message: str | None = None) -> str:
        """Create a commit touching a unique file. Returns its SHA.

        Mirrors upstream ``MakeACommit``. The file name is derived from a
        counter, so every commit changes the tree.
        """
        self._tick()
        self._commit_count += 1
        name = f"file{self._commit_count:04d}.txt"
        (self.path / name).write_text(f"commit {self._commit_count}\n", encoding="utf-8")
        self.git("add", "--", name)
        self.git("commit", "--quiet", "-m", message or f"Commit {self._commit_count}")
        return self.head_sha

    def amend_head_message(self, suffix: str) -> str:
        """Append ``suffix`` to the ``HEAD`` commit message (``AmendPreviousCommit``)."""
        message = self.git("log", "-1", "--format=%B").rstrip("\n")
        self.git("commit", "--quiet", "--amend", "-m", message + suffix)
        return self.head_sha

    def make_commits(self, count: int) -> list[str]:
        """Create ``count`` commits and return their SHAs in order."""
        return [self.make_a_commit() for _ in range(count)]

    def apply_tag(self, name: str, *, annotated: bool = False, message: str | None = None) -> None:
        """Tag ``HEAD``. Mirrors upstream ``ApplyTag``.

        Args:
            name: Tag name, e.g. ``v1.2.3`` or ``1.2.3-beta.1``.
            annotated: Create an annotated tag object rather than a lightweight ref.
            message: Annotation message (defaults to the tag name).
        """
        self._tick()
        if annotated:
            self.git("tag", "-a", name, "-m", message or name)
        else:
            self.git("tag", name)

    def make_a_tagged_commit(self, tag: str, message: str | None = None) -> str:
        """``make_a_commit`` followed by ``apply_tag``. Returns the commit SHA."""
        sha = self.make_a_commit(message)
        self.apply_tag(tag)
        return sha

    def branch_to(self, name: str) -> None:
        """Create ``name`` at ``HEAD`` and check it out. Mirrors upstream ``BranchTo``."""
        self.git("checkout", "--quiet", "-b", name)

    def create_branch(self, name: str, at: str | None = None) -> None:
        """Create ``name`` at ``at`` (default HEAD) without checkout. Mirrors ``CreateBranch``."""
        self.git("branch", name, *([at] if at else []))

    def commit_date(self, sha: str) -> datetime:
        """Committer date of ``sha`` as an aware datetime."""
        return datetime.fromisoformat(self.git("show", "-s", "--format=%cI", sha))

    def tag_target(self, tag: str) -> str:
        """SHA of the commit a tag points at (peeled)."""
        return self.git("rev-list", "-n", "1", tag)

    def create_pull_request_ref(
        self,
        source: str,
        target: str,
        pr_number: int = 2,
        *,
        normalise: bool = False,
        allow_fast_forward_merge: bool = False,
    ) -> str:
        """Mirrors ``CreatePullRequestRef``: a merge commit under ``refs/pull/<n>/merge``.

        The merge is made on a detached checkout of ``target``'s tip so the
        target branch itself does not move. With ``normalise`` a local branch
        ``pull/<n>/merge`` is created at the merge commit and checked out.
        """
        self.git("checkout", "--quiet", "--detach", target)
        self._tick()
        if allow_fast_forward_merge:
            self.git("merge", "--quiet", "--no-edit", "-m", f"Merge branch '{source}'", source)
        else:
            self.git(
                "merge", "--quiet", "--no-edit", "--no-ff", "-m", f"Merge branch '{source}'", source
            )
        sha = self.head_sha
        self.git("update-ref", f"refs/pull/{pr_number}/merge", sha)
        self.checkout(target)
        if normalise:
            self.git("checkout", "--quiet", "-b", f"pull/{pr_number}/merge", sha)
        return sha

    def checkout(self, ref: str) -> None:
        """Check out an existing branch, tag or SHA."""
        self.git("checkout", "--quiet", ref)

    def merge_to(self, target: str, *, source: str | None = None, no_ff: bool = True) -> str:
        """Merge ``source`` (default: current branch) into ``target``.

        Mirrors upstream ``MergeTo``: checks out ``target``, performs the
        merge with a conventional ``Merge branch '...'`` message so the
        ``MergeMessage`` strategy has something to parse, and returns the
        merge commit SHA. ``no_ff`` defaults to true because upstream
        scenarios rely on a merge commit existing.
        """
        src = source or self.current_branch
        self.checkout(target)
        self._tick()
        args = ["merge", "--quiet", "--no-edit"]
        if no_ff:
            args.append("--no-ff")
        args += ["-m", f"Merge branch '{src}' into {target}", src]
        self.git(*args)
        return self.head_sha

    def merge_no_ff(self, source: str) -> str:
        """Merge ``source`` into the current branch with a merge commit."""
        return self.merge_to(self.current_branch, source=source, no_ff=True)

    def merge_ff(self, source: str) -> str:
        """Merge ``source`` allowing fast-forward (libgit2 ``Repository.Merge`` default)."""
        self._tick()
        self.git("merge", "--quiet", "--no-edit", source)
        return self.head_sha

    def merge_commit_no_ff(self, sha: str) -> str:
        """Merge a specific commit with ``--no-ff`` and git's default message."""
        self._tick()
        self.git("merge", "--quiet", "--no-edit", "--no-ff", sha)
        return self.head_sha

    def delete_tag(self, name: str) -> None:
        """Delete a tag (``Repository.Tags.Remove``)."""
        self.git("tag", "-d", name)

    def delete_branch(self, name: str) -> None:
        """Delete a local branch (``-D``)."""
        self.git("branch", "-D", name)

    def branches(self) -> list[str]:
        """Short names of all local branches, sorted."""
        out = self.git("for-each-ref", "--format=%(refname:short)", "refs/heads")
        return sorted(line for line in out.splitlines() if line)

    def tags(self) -> list[str]:
        """All tag names, sorted."""
        out = self.git("for-each-ref", "--format=%(refname:short)", "refs/tags")
        return sorted(line for line in out.splitlines() if line)

    def write_config(self, yaml_text: str, filename: str = "GitVersion.yml") -> Path:
        """Write a ``GitVersion.yml`` (or other config file) into the repository."""
        target = self.path / filename
        target.write_text(yaml_text, encoding="utf-8")
        return target

    def log_oneline(self, *refs: str) -> Sequence[str]:
        """``git log --oneline`` for debugging failed scenarios."""
        return self.git("log", "--oneline", "--graph", "--decorate", *refs).splitlines()


@contextmanager
def repository(default_branch: str = "main") -> Iterator[RepositoryFixture]:
    """Function-style alternative to the class context manager."""
    with RepositoryFixture(default_branch) as repo:
        yield repo
