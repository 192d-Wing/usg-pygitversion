# SPDX-License-Identifier: MIT
"""Build-server integration (PLAN.md section 7).

Tier 1 agents are GitHub Actions and GitLab CI. Every other server is
served by the generic environment export in :mod:`envexport`.
"""

from __future__ import annotations

from usg_pygitversion.buildagents.base import BuildAgent, LocalBuild, resolve
from usg_pygitversion.buildagents.envexport import EnvExporter, Shell
from usg_pygitversion.buildagents.github_actions import GitHubActions
from usg_pygitversion.buildagents.gitlab_ci import GitLabCi

__all__ = [
    "BuildAgent",
    "EnvExporter",
    "GitHubActions",
    "GitLabCi",
    "LocalBuild",
    "Shell",
    "resolve",
]
