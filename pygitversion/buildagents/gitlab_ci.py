# SPDX-License-Identifier: MIT
"""GitLab CI agent. Ports ``GitLabCi.cs``."""

from __future__ import annotations

from pygitversion.buildagents.base import BuildAgent, Writer
from pygitversion.buildagents.envexport import write_lines
from pygitversion.calculation.variables import GitVersionVariables


class GitLabCi(BuildAgent):
    """Detected by ``GITLAB_CI``; writes ``gitversion.properties`` in the working directory."""

    environment_variable = "GITLAB_CI"
    properties_file = "gitversion.properties"

    def set_build_number(self, variables: GitVersionVariables) -> str | None:
        """GitLab has no build-number API; upstream prints ``FullSemVer``."""
        return variables.full_sem_ver

    def set_output_variables(self, name: str, value: str | None) -> list[str]:
        """One ``GitVersion_<Name>=<value>`` line (empty values included, as upstream)."""
        return [f"GitVersion_{name}={value or ''}"]

    def current_branch(self, using_dynamic_repos: bool = False) -> str | None:  # noqa: ARG002
        """Merge-request ref path, else the commit ref name; ``None`` for tag pipelines."""
        if self.environment.get("CI_COMMIT_TAG"):
            return None
        merge_request = self.environment.get("CI_MERGE_REQUEST_REF_PATH")
        if merge_request:
            return merge_request
        return self.environment.get("CI_COMMIT_REF_NAME")

    def write_integration(
        self, writer: Writer, variables: GitVersionVariables, update_build_number: bool = True
    ) -> None:
        """Console lines plus the properties file."""
        super().write_integration(writer, variables, update_build_number)
        writer(f"Outputting variables to '{self.properties_file}' ... ")
        write_lines(
            self.working_directory / self.properties_file, self.output_variable_lines(variables)
        )
