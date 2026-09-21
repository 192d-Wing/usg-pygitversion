# SPDX-License-Identifier: MIT
"""End-to-end tests for the CLI flow, including differential checks against the reference tool."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import pytest
from pygitversion import calculate
from pygitversion.cli.main import main

from tests.fixtures import RepositoryFixture
from tests.scenarios.dsl import _REAL_GITVERSION

needs_reference = pytest.mark.skipif(
    _REAL_GITVERSION is None, reason="reference gitversion binary not found"
)


def _reference(repo_path: Path, *args: str, env: dict[str, str] | None = None) -> str:
    assert _REAL_GITVERSION is not None
    result = subprocess.run(
        [_REAL_GITVERSION, *args],
        cwd=repo_path,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return result.stdout


def _prepare(repo: RepositoryFixture) -> None:
    repo.make_a_commit()
    repo.apply_tag("1.2.3")
    repo.make_a_commit()
    repo.branch_to("feature/foo")
    repo.make_a_commit()


def test_json_default_and_cache(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare(repo)
    assert main([str(repo.path)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["FullSemVer"] == "1.2.4-foo.1+2"
    cache_dir = repo.path / ".git" / "gitversion_cache"
    assert len(list(cache_dir.iterdir())) == 1
    assert main([str(repo.path), "/showvariable", "FullSemVer"]) == 0
    assert capsys.readouterr().out.strip() == "1.2.4-foo.1+2"
    assert main([str(repo.path), "/nocache", "/format", "{Major}.{Minor}"]) == 0
    assert capsys.readouterr().out.strip() == "1.2"


def test_showconfig_prints_yaml_and_blank_line(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.make_a_commit()
    repo.write_config("next-version: 4.5.6\n")
    assert main([str(repo.path), "/showconfig"]) == 0
    out = capsys.readouterr().out
    assert "next-version: 4.5.6\n" in out
    assert out.endswith("\n\n")


def test_env_output_is_evaluable(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare(repo)
    assert main([str(repo.path), "--output", "env"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("export GitVersion_")
    assert "{" not in out


def test_buildserver_gitlab_writes_properties(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(repo)
    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "feature/foo")
    monkeypatch.chdir(repo.path)
    assert main(["/output", "buildserver", "/nonormalize"]) == 0
    out = capsys.readouterr().out
    assert "Set Build Number for 'GitLabCi'." in out
    assert "INFO [" in out  # buildserver output mirrors the log to stdout, as upstream
    assert (repo.path / "gitversion.properties").is_file()


def test_logging_handlers_are_released_after_each_invocation(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A console handler bound to one invocation's stdout must not outlive it.

    Otherwise the next in-process log record is written to a stream that
    the caller (here, pytest's capture) has already closed.
    """
    _prepare(repo)
    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.chdir(repo.path)
    log_file = repo.path / "build.log"
    assert main(["/output", "buildserver", "/nonormalize", "/l", str(log_file)]) == 0
    assert "INFO [" in capsys.readouterr().out
    assert logging.getLogger("pygitversion").handlers == []
    assert log_file.read_text(encoding="utf-8").startswith("INFO [")


def test_buildserver_requires_one_remote(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(repo)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert main([str(repo.path), "/output", "buildserver"]) == 1
    assert "0 remote(s) have been detected" in capsys.readouterr().err


def test_public_api(repo: RepositoryFixture) -> None:
    _prepare(repo)
    variables = calculate(repo.path)
    assert variables.full_sem_ver == "1.2.4-foo.1+2"
    assert variables.as_dict()["BranchName"] == "feature/foo"
    assert calculate(repo.path, branch="main").full_sem_ver == "1.2.4-1"
    assert calculate(repo.path, overrides={"next-version": "9.0.0"}).full_sem_ver == "9.0.0-foo.1+2"


@needs_reference
def test_differential_json_dotenv_and_showconfig(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare(repo)
    for args in (
        ["/nocache"],
        ["/nocache", "/output", "dotenv"],
        ["/showconfig"],
        ["/nocache", "/format", "{SemVer}+{env:HOME}"],
    ):
        expected = _reference(repo.path, *args)
        assert main([str(repo.path), *args]) == 0
        assert capsys.readouterr().out == expected, args


@needs_reference
def test_differential_gitlab_buildserver(
    repo: RepositoryFixture, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(repo)
    env = {"GITLAB_CI": "true", "CI_COMMIT_REF_NAME": "feature/foo"}
    expected = [
        line
        for line in _reference(
            repo.path, "/output", "buildserver", "/nonormalize", "/nocache", env=env
        ).splitlines()
        if not line.lstrip().startswith(("INFO", "WARN", "DEBUG"))
    ]
    expected_properties = (repo.path / "gitversion.properties").read_text()
    (repo.path / "gitversion.properties").unlink()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo.path)
    assert main(["/output", "buildserver", "/nonormalize", "/nocache"]) == 0
    ours = [
        line
        for line in capsys.readouterr().out.splitlines()
        if not line.lstrip().startswith(("INFO", "WARN", "DEBUG"))
    ]
    assert ours == expected
    assert (repo.path / "gitversion.properties").read_text() == expected_properties
