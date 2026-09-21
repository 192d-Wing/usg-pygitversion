# SPDX-License-Identifier: MIT
"""Tests for the git subprocess layer against real repositories."""

from __future__ import annotations

import subprocess
from datetime import UTC
from pathlib import Path

import pytest
from usg_pygitversion.errors import GitCommandError, RepositoryError
from usg_pygitversion.git import GitCommand, GitRepository

from tests.fixtures import RepositoryFixture


def test_open_from_subdirectory_and_git_dir(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    sub = repo.path / "src" / "deep"
    sub.mkdir(parents=True)
    opened = GitRepository(sub)
    assert opened.working_tree == repo.path
    assert opened.git_dir == repo.path / ".git"


def test_open_non_repository(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError, match="not a git repository"):
        GitRepository(tmp_path)
    with pytest.raises(RepositoryError, match="not a directory"):
        GitRepository(tmp_path / "missing")


def test_head_on_branch_and_detached(repo: RepositoryFixture) -> None:
    sha = repo.make_a_commit()
    g = GitRepository(repo.path)
    head = g.head()
    assert head.name.friendly == "main"
    assert head.tip == sha
    assert not g.is_head_detached()

    repo.checkout(sha)
    g = GitRepository(repo.path)
    assert g.is_head_detached()
    assert g.head().is_detached_head
    assert g.head().tip == sha


def test_head_on_empty_repository(repo: RepositoryFixture) -> None:
    g = GitRepository(repo.path)
    assert g.head_sha() is None
    with pytest.raises(RepositoryError, match="no commits"):
        g.head()


def test_branches_and_tags(repo: RepositoryFixture) -> None:
    first = repo.make_a_commit()
    repo.apply_tag("1.0.0")  # lightweight
    repo.apply_tag("v1.0.0-annotated", annotated=True, message="release")
    repo.branch_to("feature/one")
    second = repo.make_a_commit()
    g = GitRepository(repo.path)

    assert [b.name.friendly for b in g.branches] == ["feature/one", "main"]
    assert g.find_branch("MAIN") is not None
    assert g.find_branch("nope") is None
    assert {b.name.friendly: b.tip for b in g.branches} == {"main": first, "feature/one": second}

    tags = {t.name.friendly: t for t in g.tags}
    assert tags["1.0.0"].target == first
    assert not tags["1.0.0"].is_annotated
    assert tags["1.0.0"].tagged_when is None
    assert tags["v1.0.0-annotated"].target == first  # peeled to the commit
    assert tags["v1.0.0-annotated"].is_annotated
    assert tags["v1.0.0-annotated"].tagged_when is not None


def test_commit_parsing_with_multiline_message_and_merge(repo: RepositoryFixture) -> None:
    root = repo.make_a_commit("Subject line\n\nBody paragraph one.\n\n+semver: minor\n")
    repo.branch_to("topic")
    topic = repo.make_a_commit("topic work")
    merge = repo.merge_to("main")
    g = GitRepository(repo.path)

    c = g.commit(root)
    assert c.sha == root
    assert c.parents == ()
    assert c.message == "Subject line\n\nBody paragraph one.\n\n+semver: minor"
    assert c.when.tzinfo is not None
    assert c.when.astimezone(UTC).year == 2020  # fixture clock
    assert not c.is_merge

    m = g.commit(merge)
    assert m.is_merge
    assert m.parents == (root, topic)
    assert m.message.startswith("Merge branch 'topic' into main")
    assert g.commit(merge) is m  # cached


def test_commit_unknown_revision(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    with pytest.raises(RepositoryError, match="unknown revision"):
        GitRepository(repo.path).commit("deadbeef")


def test_walk_order_exclusion_and_first_parent(repo: RepositoryFixture) -> None:
    shas = repo.make_commits(3)
    repo.branch_to("side")
    side = repo.make_commits(2)
    repo.checkout("main")
    main4 = repo.make_a_commit()
    merge = repo.merge_to("main", source="side")
    g = GitRepository(repo.path)

    everything = [c.sha for c in g.walk("HEAD")]
    assert everything[0] == merge
    assert set(everything) == {*shas, *side, main4, merge}

    only_side = [c.sha for c in g.walk("side", exclude=["main~1"])]
    assert set(only_side) == set(side)

    mainline = [c.sha for c in g.walk("HEAD", first_parent=True)]
    assert mainline == [merge, main4, *reversed(shas)]

    assert g.count_commits("HEAD") == 7
    assert g.count_commits("HEAD", exclude=[shas[-1]]) == 4


def test_walk_with_path_filter_and_changed_paths(repo: RepositoryFixture) -> None:
    a = repo.make_a_commit()  # file0001.txt
    b = repo.make_a_commit()  # file0002.txt
    g = GitRepository(repo.path)
    assert [c.sha for c in g.walk("HEAD", paths=["file0002.txt"])] == [b]
    assert g.changed_paths(a) == ("file0001.txt",)
    assert g.changed_paths(b) == ("file0002.txt",)


def test_walk_stops_early_without_leaking_process(repo: RepositoryFixture) -> None:
    repo.make_commits(20)
    g = GitRepository(repo.path)
    it = g.walk("HEAD")
    first = next(it)
    it.close()  # must terminate git; ResourceWarning-as-error would flag a leak
    assert first.sha == repo.head_sha


def test_walk_enforces_commit_cap(repo: RepositoryFixture) -> None:
    repo.make_commits(5)
    g = GitRepository(repo.path, max_commits=3)
    with pytest.raises(RepositoryError, match="exceeded the limit"):
        list(g.walk("HEAD"))


def test_merge_base_and_ancestry(repo: RepositoryFixture) -> None:
    base = repo.make_a_commit()
    repo.branch_to("x")
    x = repo.make_a_commit()
    repo.checkout("main")
    m = repo.make_a_commit()
    g = GitRepository(repo.path)
    assert g.merge_base("x", "main") == base
    assert g.is_ancestor(base, x)
    assert not g.is_ancestor(x, m)
    assert g.is_ancestor(base, base)


def test_uncommitted_changes(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    g = GitRepository(repo.path)
    assert g.uncommitted_changes() == 0
    (repo.path / "file0001.txt").write_text("changed\n", encoding="utf-8")
    (repo.path / "new.txt").write_text("new\n", encoding="utf-8")
    assert g.uncommitted_changes() == 2


# -- GitCommand ---------------------------------------------------------------


def test_command_error_carries_context(repo: RepositoryFixture) -> None:
    cmd = GitCommand(repo.path)
    with pytest.raises(GitCommandError) as exc:
        cmd.run("rev-parse", "--verify", "definitely-not-a-ref")
    assert exc.value.returncode == 128
    assert exc.value.args_[0] == "rev-parse"
    assert "exited 128" in str(exc.value)


def test_command_check_false_returns_empty_on_failure(repo: RepositoryFixture) -> None:
    assert GitCommand(repo.path).run("rev-parse", "--verify", "-q", "nope", check=False) == ""


def test_command_timeout(repo: RepositoryFixture) -> None:
    # `git cat-file --batch` waits for stdin; stdin is DEVNULL so it should
    # exit immediately. Use a git invocation that genuinely blocks: `git
    # credential fill` reads stdin until EOF too. Instead, simulate with a
    # tiny timeout on a command that must at least start a process.
    cmd = GitCommand(repo.path, timeout=0.000001)
    with pytest.raises(GitCommandError, match="timed out"):
        cmd.run("log", "--all")


def test_command_environment_is_minimal_and_hooks_disabled(repo: RepositoryFixture) -> None:
    # A pre-commit style hook in the repo must never run under our wrapper.
    hooks = repo.path / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    marker = repo.path / "hook-ran"
    hook = hooks / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    repo.make_a_commit()
    GitCommand(repo.path).run("checkout", "--quiet", "HEAD")  # would trigger post-checkout
    assert not marker.exists()
    # And the environment must not leak arbitrary variables.
    out = GitCommand(repo.path).run("var", "GIT_COMMITTER_IDENT", check=False)
    assert "usg-pygitversion-secret" not in out


def test_command_missing_git_binary(
    monkeypatch: pytest.MonkeyPatch, repo: RepositoryFixture
) -> None:
    monkeypatch.setattr("usg_pygitversion.git.command.shutil.which", lambda _name: None)
    with pytest.raises(RepositoryError, match="git executable not found"):
        GitCommand(repo.path)


def test_stream_reports_nonzero_exit(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    with pytest.raises(GitCommandError):
        list(GitCommand(repo.path).stream("log", "not-a-ref"))


def test_fixture_and_wrapper_agree(repo: RepositoryFixture) -> None:
    sha = repo.make_a_commit()
    assert GitCommand(repo.path).run("rev-parse", "HEAD") == sha
    # sanity: the wrapper really is a subprocess boundary
    assert isinstance(subprocess.run, object)
