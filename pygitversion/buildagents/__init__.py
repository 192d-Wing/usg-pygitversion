# SPDX-License-Identifier: MIT
"""Build-server integration (PLAN.md section 7).

Tier 1 agents are GitHub Actions and GitLab CI. Every other server is
served by the generic environment export in :mod:`envexport`.
"""

from __future__ import annotations

from pygitversion.buildagents.base import BuildAgent, LocalBuild, resolve
from pygitversion.buildagents.envexport import EnvExporter, Shell
from pygitversion.buildagents.github_actions import GitHubActions
from pygitversion.buildagents.gitlab_ci import GitLabCi

__all__ = [
    "BuildAgent",
    "EnvExporter",
    "GitHubActions",
    "GitLabCi",
    "LocalBuild",
    "Shell",
    "resolve",
]
