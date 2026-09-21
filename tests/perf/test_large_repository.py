# SPDX-License-Identifier: MIT
"""Time and memory budget on a synthetic large repository (PLAN.md Phase 6, 9.4).

The repository is built with ``git fast-import`` so creating 50,000 commits
takes seconds. The budget test is marked ``memory`` and excluded from the
default CI matrix; it runs in its own job.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
from pygitversion import calculate

from tests.fixtures import RepositoryFixture

# ``resource`` is POSIX-only. Collection must still succeed on Windows, where
# the default matrix deselects this module by marker but imports it first.
resource = pytest.importorskip("resource", reason="resource module is POSIX-only")

pytestmark = pytest.mark.memory

COMMITS = int(os.environ.get("PYGITVERSION_PERF_COMMITS", "50000"))
TIME_BUDGET_SECONDS = float(os.environ.get("PYGITVERSION_PERF_SECONDS", "10"))
MEMORY_BUDGET_MB = int(os.environ.get("PYGITVERSION_PERF_MB", "512"))


def build_linear_history(repo: RepositoryFixture, commits: int, tag_at: int) -> None:
    """Create ``commits`` commits on ``main`` with tag ``1.0.0`` at ``tag_at``."""
    lines: list[str] = []
    stamp = 1_600_000_000
    for index in range(1, commits + 1):
        lines.append("commit refs/heads/main")
        lines.append(f"committer Test <test@example.com> {stamp + index} +0000")
        message = f"Commit {index}"
        lines.append(f"data {len(message)}")
        lines.append(message)
        lines.append(f"M 100644 inline file{index % 97}.txt")
        lines.append(f"data {len(str(index))}")
        lines.append(str(index))
        lines.append("")
        if index == tag_at:
            lines.append("reset refs/tags/1.0.0")
            lines.append("from refs/heads/main")
            lines.append("")
    script = "\n".join(lines) + "\n"
    subprocess.run(
        ["git", "fast-import", "--quiet"],
        cwd=repo.path,
        input=script.encode("utf-8"),
        check=True,
        timeout=600,
    )
    repo.git("checkout", "--quiet", "main")


def _max_rss_mb() -> float:
    # The annotation pins the type: ``resource`` is ``Any`` after importorskip.
    usage: int = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return usage / divisor


def test_large_linear_history_within_budget(repo: RepositoryFixture) -> None:
    build_linear_history(repo, COMMITS, tag_at=1000)
    before = _max_rss_mb()
    started = time.perf_counter()
    variables = calculate(repo.path)
    elapsed = time.perf_counter() - started
    grown = _max_rss_mb() - before
    assert variables.full_sem_ver == f"1.0.1-{COMMITS - 1000}"
    assert elapsed < TIME_BUDGET_SECONDS, f"took {elapsed:.1f}s for {COMMITS} commits"
    assert grown < MEMORY_BUDGET_MB, f"RSS grew by {grown:.0f} MB"
    print(f"\n{COMMITS} commits: {elapsed:.2f}s, RSS +{grown:.0f} MB")  # noqa: T201 -- perf report
