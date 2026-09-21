# SPDX-License-Identifier: MIT
"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.fixtures import RepositoryFixture
from tests.scenarios.dsl import _REAL_GITVERSION

# Variables that make the tool believe it runs on a build server (see
# pygitversion.buildagents). They are present on every GitHub Actions and
# GitLab runner, and build-server mode requires exactly one remote, which
# the throwaway test repositories never have. Tests that need an agent set
# these explicitly with ``monkeypatch``.
_BUILD_AGENT_VARIABLES = ("GITHUB_ACTIONS", "GITHUB_ENV", "GITLAB_CI")


@pytest.fixture(autouse=True)
def _local_build_environment() -> Iterator[None]:
    """Hide the CI runner's own build-agent variables so tests behave as locally.

    A private ``MonkeyPatch`` is used on purpose. Requesting the shared
    ``monkeypatch`` fixture here would instantiate it before every other
    fixture, so a test's ``monkeypatch.chdir(repo.path)`` would be undone
    only *after* ``repo`` deleted its directory, and Windows refuses to
    remove the process's current directory.
    """
    with pytest.MonkeyPatch.context() as patch:
        for name in _BUILD_AGENT_VARIABLES:
            patch.delenv(name, raising=False)
        yield


@pytest.fixture
def repo() -> Iterator[RepositoryFixture]:
    """A fresh, empty git repository on ``main``, removed after the test."""
    with RepositoryFixture() as fixture:
        yield fixture


@pytest.fixture(scope="session")
def real_gitversion() -> str:
    """Path to the real GitVersion binary, or skip the test.

    Used by tests marked ``differential`` (PLAN.md D6). The binary is
    optional locally and provided in CI via ``dotnet tool install``.
    """
    if _REAL_GITVERSION is None:
        pytest.skip("real gitversion binary not on PATH")
    return _REAL_GITVERSION
