# SPDX-License-Identifier: MIT
"""GitHub Actions agent. Ports ``GitHubActions.cs``."""

from __future__ import annotations

from usg_pygitversion.buildagents.base import BuildAgent, Writer
from usg_pygitversion.buildagents.envexport import EnvExporter
from usg_pygitversion.calculation.variables import GitVersionVariables


class GitHubActions(BuildAgent):
    """Detected by ``GITHUB_ACTIONS``; exports through the ``$GITHUB_ENV`` file."""

    environment_variable = "GITHUB_ACTIONS"
    env_file_variable = "GITHUB_ENV"

    def set_build_number(self, variables: GitVersionVariables) -> str | None:  # noqa: ARG002
        """There is no equivalent in GitHub Actions."""
        return ""

    def set_output_variables(self, name: str, value: str | None) -> list[str]:  # noqa: ARG002
        """There is no equivalent in GitHub Actions."""
        return []

    def write_integration(
        self, writer: Writer, variables: GitVersionVariables, update_build_number: bool = True
    ) -> None:
        """Append ``GitVersion_<Name>=<value>`` lines to the ``$GITHUB_ENV`` file."""
        super().write_integration(writer, variables, update_build_number)
        env_file = self.environment.get(self.env_file_variable)
        if env_file is None:
            writer(
                f"Unable to write GitVersion variables to ${self.env_file_variable} "
                "because the environment variable is not set."
            )
            return
        writer(f"Writing version variables to ${self.env_file_variable} file for '{self.name}'.")
        EnvExporter().append_env_file(env_file, variables)

    def current_branch(self, using_dynamic_repos: bool = False) -> str | None:  # noqa: ARG002
        """``GITHUB_REF`` unless the workflow runs for a tag."""
        ref_type = self.environment.get("GITHUB_REF_TYPE", "")
        if ref_type.lower() == "tag":
            return None
        return self.environment.get("GITHUB_REF")
