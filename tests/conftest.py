"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest

from tests.fixtures import RepositoryFixture


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
    path = shutil.which("gitversion")
    if path is None:
        pytest.skip("real gitversion binary not on PATH")
    return path
