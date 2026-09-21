# SPDX-License-Identifier: MIT
"""Tests for build-agent detection, branch resolution and integration output."""

from __future__ import annotations

from pathlib import Path

from usg_pygitversion.buildagents import GitHubActions, GitLabCi, LocalBuild, resolve

from tests.unit.test_output import sample


def test_resolve_prefers_last_applicable_agent(tmp_path: Path) -> None:
    assert isinstance(resolve({}, tmp_path), LocalBuild)
    assert isinstance(resolve({"GITHUB_ACTIONS": "true"}, tmp_path), GitHubActions)
    assert isinstance(resolve({"GITHUB_ACTIONS": "true", "GITLAB_CI": "true"}, tmp_path), GitLabCi)
    assert isinstance(resolve({"GITHUB_ACTIONS": ""}, tmp_path), LocalBuild)


def test_github_actions_branch_and_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "github_env"
    agent = GitHubActions(
        {"GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main", "GITHUB_ENV": str(env_file)},
        tmp_path,
    )
    assert agent.current_branch() == "refs/heads/main"
    assert (
        GitHubActions(
            {"GITHUB_REF_TYPE": "tag", "GITHUB_REF": "refs/tags/v1"}, tmp_path
        ).current_branch()
        is None
    )
    lines: list[str] = []
    agent.write_integration(lines.append, sample())
    assert lines == [
        "Set Build Number for 'GitHubActions'.",
        "",
        "Set Output Variables for 'GitHubActions'.",
        "Writing version variables to $GITHUB_ENV file for 'GitHubActions'.",
    ]
    content = env_file.read_text().splitlines()
    assert "GitVersion_FullSemVer=1.2.4-1" in content
    assert not any(line.startswith("GitVersion_BuildMetaData=") for line in content)


def test_github_actions_without_env_file_warns(tmp_path: Path) -> None:
    lines: list[str] = []
    GitHubActions({"GITHUB_ACTIONS": "true"}, tmp_path).write_integration(
        lines.append, sample(), False
    )
    assert lines == [
        "Set Output Variables for 'GitHubActions'.",
        (
            "Unable to write GitVersion variables to $GITHUB_ENV because the environment "
            "variable is not set."
        ),
    ]


def test_gitlab_ci_branch_resolution(tmp_path: Path) -> None:
    assert (
        GitLabCi({"CI_COMMIT_TAG": "v1", "CI_COMMIT_REF_NAME": "v1"}, tmp_path).current_branch()
        is None
    )
    assert (
        GitLabCi(
            {"CI_MERGE_REQUEST_REF_PATH": "refs/merge-requests/1/head", "CI_COMMIT_REF_NAME": "x"},
            tmp_path,
        ).current_branch()
        == "refs/merge-requests/1/head"
    )
    assert (
        GitLabCi({"CI_COMMIT_REF_NAME": "feature/foo"}, tmp_path).current_branch() == "feature/foo"
    )


def test_gitlab_ci_integration_lines_and_properties_file(tmp_path: Path) -> None:
    lines: list[str] = []
    GitLabCi({"GITLAB_CI": "true"}, tmp_path).write_integration(lines.append, sample())
    assert lines[:3] == [
        "Set Build Number for 'GitLabCi'.",
        "1.2.4-1",
        "Set Output Variables for 'GitLabCi'.",
    ]
    assert lines[3] == "GitVersion_AssemblySemFileVer=v-AssemblySemFileVer"
    assert "GitVersion_BuildMetaData=" in lines
    assert lines[-1] == "Outputting variables to 'gitversion.properties' ... "
    properties = (tmp_path / "gitversion.properties").read_text().splitlines()
    assert properties == lines[3:-1]
