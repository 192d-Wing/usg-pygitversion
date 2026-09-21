# SPDX-License-Identifier: MIT
"""Build-agent base class and resolver. Ports ``BuildAgentBase``/``BuildAgentResolver``.

The environment is injected as a mapping, never read from ``os.environ``
here, so every agent is unit-testable without a CI box.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path

from usg_pygitversion.calculation.variables import GitVersionVariables

_log = logging.getLogger("usg_pygitversion.buildagents")

Writer = Callable[[str], None]


class BuildAgent:
    """One CI system. Subclasses override the hooks they need."""

    #: Environment variable whose presence selects this agent.
    environment_variable: str = ""
    #: Whether this is the fallback used when nothing else applies.
    is_default: bool = False

    def __init__(self, environment: Mapping[str, str], working_directory: Path) -> None:
        """Bind to an environment and the directory files are written into."""
        self.environment = environment
        self.working_directory = working_directory

    @property
    def name(self) -> str:
        """Upstream uses the class name in its console messages."""
        return type(self).__name__

    def can_apply(self) -> bool:
        """Ports ``CanApplyToCurrentContext``: the detection variable is non-empty."""
        return bool(self.environment.get(self.environment_variable))

    def current_branch(self, using_dynamic_repos: bool = False) -> str | None:  # noqa: ARG002
        """Branch being built according to the CI environment, if known."""
        return None

    def prevent_fetch(self) -> bool:
        """Whether ``git fetch`` must be skipped on this agent."""
        return True

    def set_build_number(self, variables: GitVersionVariables) -> str | None:
        """Line that updates the CI build number, or ``None`` when unsupported."""
        raise NotImplementedError

    def set_output_variables(self, name: str, value: str | None) -> list[str]:
        """Lines exporting one variable to the CI system."""
        raise NotImplementedError

    def output_variable_lines(self, variables: GitVersionVariables) -> list[str]:
        """All export lines in variable order."""
        lines: list[str] = []
        for name, value in variables:
            lines.extend(self.set_output_variables(name, value))
        return lines

    def write_integration(
        self, writer: Writer, variables: GitVersionVariables, update_build_number: bool = True
    ) -> None:
        """Ports ``WriteIntegration``: emit the agent-specific console lines."""
        if update_build_number:
            writer(f"Set Build Number for '{self.name}'.")
            writer(self.set_build_number(variables) or "")
        writer(f"Set Output Variables for '{self.name}'.")
        for line in self.output_variable_lines(variables):
            writer(line)


class LocalBuild(BuildAgent):
    """The default agent: no CI detected, prints nothing extra."""

    is_default = True

    def can_apply(self) -> bool:
        """Always applies (it is the fallback)."""
        return True

    def prevent_fetch(self) -> bool:
        """Local builds never fetch either (PLAN.md 7.3)."""
        return True

    def set_build_number(self, variables: GitVersionVariables) -> str | None:  # noqa: ARG002
        """No build number concept."""
        return None

    def set_output_variables(self, name: str, value: str | None) -> list[str]:  # noqa: ARG002
        """Nothing to export."""
        return []


def resolve(
    environment: Mapping[str, str],
    working_directory: Path,
    agents: tuple[type[BuildAgent], ...] | None = None,
) -> BuildAgent:
    """Ports ``BuildAgentResolver.Resolve``: the last applicable agent wins.

    Detection failures are logged and skipped, never fatal.
    """
    from usg_pygitversion.buildagents.github_actions import GitHubActions  # noqa: PLC0415
    from usg_pygitversion.buildagents.gitlab_ci import GitLabCi  # noqa: PLC0415

    candidates = agents if agents is not None else (GitHubActions, GitLabCi)
    instance: BuildAgent = LocalBuild(environment, working_directory)
    for agent_type in candidates:
        agent = agent_type(environment, working_directory)
        try:
            if not agent.can_apply():
                continue
        except Exception as exc:
            _log.warning("Failed to check build agent '%s': %s", agent.name, exc)
            continue
        instance = agent
    _log.info("Applicable build agent found: '%s'.", instance.name)
    return instance
