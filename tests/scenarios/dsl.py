# SPDX-License-Identifier: MIT
"""Helpers that make ported upstream scenarios read like the C# originals.

Upstream pattern::

    using var fixture = new EmptyRepositoryFixture();
    var configuration = GitFlowConfigurationBuilder.New
        .WithBranch("main", b => b.WithDeploymentMode(DeploymentMode.ManualDeployment))
        .Build();
    fixture.Repository.MakeATaggedCommit("1.0.0");
    fixture.AssertFullSemver("1.0.1-1+2", configuration);

Port::

    with Scenario() as f:
        configuration = gitflow(branches={"main": {"mode": "ManualDeployment"}})
        f.make_a_tagged_commit("1.0.0")
        f.assert_full_semver("1.0.1-1+2", configuration)

``Scenario`` extends :class:`~tests.fixtures.RepositoryFixture` with the
assertion helper (ports ``GitRepositoryTestingExtensions.AssertFullSemver``)
and a differential check against the real ``gitversion`` binary when it is
installed (PLAN.md D6).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from typing import Any

from usg_pygitversion.calculation import calculate_variables
from usg_pygitversion.config import GitVersionConfiguration
from usg_pygitversion.config.provider import build
from usg_pygitversion.config.yaml_io import dump_mapping

from tests.fixtures.repository import RepositoryFixture


def _find_reference_binary() -> str | None:
    """Locate the real .NET ``gitversion``, skipping this project's own console script.

    ``GITVERSION_REFERENCE`` overrides the search. Otherwise every ``PATH``
    entry outside the active virtual environment is tried, first for
    ``dotnet-gitversion`` (the command a ``dotnet tool install`` of
    GitVersion.Tool registers) and then for a bare ``gitversion``.
    """
    explicit = os.environ.get("GITVERSION_REFERENCE")
    if explicit:
        return explicit
    venv = os.environ.get("VIRTUAL_ENV") or sys.prefix
    outside = os.pathsep.join(
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and not entry.startswith(venv)
    )
    for name in ("dotnet-gitversion", "gitversion"):
        found = shutil.which(name, path=outside)
        if found is not None:
            return found
    return None


_REAL_GITVERSION = _find_reference_binary()
_DIFFERENTIAL = os.environ.get("USG_PYGITVERSION_DIFFERENTIAL", "") not in ("", "0", "false")


def _hyphenate(value: Any) -> Any:
    """Recursively turn ``snake_case`` keys into the ``kebab-case`` YAML keys."""
    if isinstance(value, Mapping):
        return {str(k).replace("_", "-"): _hyphenate(v) for k, v in value.items()}
    return value


def configure(
    workflow: str | None = None,
    branches: Mapping[str, Mapping[str, Any]] | None = None,
    **root: Any,
) -> GitVersionConfiguration:
    """Build a configuration like ``<Workflow>ConfigurationBuilder.New.With...().Build()``.

    ``root`` keys are YAML keys with underscores allowed (``next_version``).
    ``None`` values delete the key (``WithNextVersion(null)``).
    """
    document: dict[str, Any] = {}
    if workflow is not None:
        document["workflow"] = workflow
    for key, value in root.items():
        document[key.replace("_", "-")] = _hyphenate(value)
    if branches:
        # Branch names themselves keep their underscores (e.g. "bob_develop").
        document["branches"] = {name: _hyphenate(cfg) for name, cfg in branches.items()}
    return build(document)


def gitflow(
    branches: Mapping[str, Mapping[str, Any]] | None = None, **root: Any
) -> GitVersionConfiguration:
    """``GitFlowConfigurationBuilder.New`` plus overrides."""
    return configure(None, branches, **root)


def githubflow(
    branches: Mapping[str, Mapping[str, Any]] | None = None, **root: Any
) -> GitVersionConfiguration:
    """``GitHubFlowConfigurationBuilder.New`` plus overrides."""
    return configure("GitHubFlow/v1", branches, **root)


def trunkbased(
    branches: Mapping[str, Mapping[str, Any]] | None = None, **root: Any
) -> GitVersionConfiguration:
    """``TrunkBasedConfigurationBuilder.New`` plus overrides."""
    return configure("TrunkBased/preview1", branches, **root)


def _norm(value: object) -> str:
    """Unify None and "" (the reference JSON writer emits null for empty strings)."""
    return "" if value is None else str(value)


class Scenario(RepositoryFixture):
    """A repository fixture with GitVersion assertions (``EmptyRepositoryFixture``)."""

    def clone(self) -> Scenario:
        """A fresh clone of this repository (``CloneRepository``); caller closes it."""
        return Scenario(clone_from=self)

    def create_and_merge_branch_into_develop(self, branch_name: str) -> None:
        """Ports ``CreateAndMergeBranchIntoDevelop`` from the merged-branch-name scenarios."""
        self.branch_to(branch_name)
        self.make_a_commit()
        self.checkout("develop")
        self.merge_no_ff(branch_name)

    def get_version(
        self,
        configuration: GitVersionConfiguration | None = None,
        *,
        commit_id: str | None = None,
        only_tracked_branches: bool = True,
        target_branch: str | None = None,
    ) -> dict[str, str | None]:
        """Ports ``GetVersion``: run the calculator with an isolated environment."""
        variables = calculate_variables(
            self.path,
            configuration=configuration if configuration is not None else gitflow(),
            commit_id=commit_id,
            only_tracked_branches=only_tracked_branches,
            target_branch=target_branch,
            environment={},
        )
        return variables.as_dict()

    def assert_full_semver(
        self,
        expected: str,
        configuration: GitVersionConfiguration | None = None,
        *,
        commit_id: str | None = None,
        only_tracked_branches: bool = True,
        target_branch: str | None = None,
    ) -> None:
        """Ports ``AssertFullSemver``; also checks the real binary when enabled."""
        variables = self.get_version(
            configuration,
            commit_id=commit_id,
            only_tracked_branches=only_tracked_branches,
            target_branch=target_branch,
        )
        actual = variables["FullSemVer"]
        if actual != expected:
            graph = "\n".join(self.log_oneline("--all"))
            msg = f"FullSemVer {actual!r} != {expected!r} on {self.current_branch}\n{graph}"
            raise AssertionError(msg)
        if _DIFFERENTIAL and _REAL_GITVERSION and commit_id is None and target_branch is None:
            self.assert_reference_agrees(configuration, variables)

    def assert_reference_agrees(
        self, configuration: GitVersionConfiguration | None, variables: Mapping[str, str | None]
    ) -> None:
        """Run the reference ``gitversion`` on this repository and compare all variables."""
        assert _REAL_GITVERSION is not None
        config_path = self.path / "GitVersion.yml"
        cfg = configuration if configuration is not None else gitflow()
        mapping = cfg.to_mapping()
        # to_mapping omits None, which the reference would read as "use the
        # preset default". Upstream tests set labels to null explicitly, so
        # spell those out as YAML nulls to keep the comparison faithful.
        if cfg.label is None:
            mapping["label"] = None
        branches = mapping.get("branches")
        if isinstance(branches, dict):
            for name, branch in cfg.branches.items():
                if branch.label is None and isinstance(branches.get(name), dict):
                    branches[name]["label"] = None
        config_path.write_text(dump_mapping(mapping), encoding="utf-8")
        try:
            completed = subprocess.run(
                [_REAL_GITVERSION, "/nocache", "/output", "json"],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        finally:
            config_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            msg = f"reference gitversion failed:\n{completed.stdout}\n{completed.stderr}"
            raise AssertionError(msg)
        reference = json.loads(completed.stdout)
        # The reference sees an untracked GitVersion.yml while it runs, so the
        # dirty count differs by design. Its JSON writer emits null for empty
        # strings (handled by the JSON output writer in Phase 5), so compare
        # values with "" and None unified.
        mismatches = {
            key: (variables.get(key), value)
            for key, value in reference.items()
            if key != "UncommittedChanges" and _norm(variables.get(key)) != _norm(value)
        }
        if mismatches:
            msg = "differences from reference gitversion (ours, theirs):\n" + "\n".join(
                f"  {k}: {a!r} != {b!r}" for k, (a, b) in mismatches.items()
            )
            raise AssertionError(msg)


class RemoteScenario(Scenario):
    """Ports ``RemoteRepositoryFixture``: a remote with five commits plus a clone.

    ``self`` is the remote; :attr:`local` is the clone (``LocalRepositoryFixture``).
    """

    def __init__(self, branch_name: str = "main") -> None:
        """Create the remote with five commits and clone it."""
        super().__init__(branch_name)
        self.make_commits(5)
        self.local = self.clone()

    def close(self) -> None:
        """Remove both repositories."""
        self.local.close()
        super().close()


class GitFlowScenario(Scenario):
    """Ports ``BaseGitFlowRepositoryFixture``: a tagged ``main`` plus ``develop`` with one commit.

    Args:
        initial_version: Tag applied to the first commit on ``main``. Pass
            ``None`` and use ``setup`` for the ``Action<IRepository>`` overload.
        setup: Callable run on ``main`` before ``develop`` is created.
        default_branch: Name of the main branch.
    """

    def __init__(
        self,
        initial_version: str | None = "1.0.0",
        setup: Callable[[GitFlowScenario], None] | None = None,
        default_branch: str = "main",
    ) -> None:
        """Build the GitFlow starting state."""
        super().__init__(default_branch)
        # Upstream stages an empty random file before the initial action; the
        # first commit therefore contains it. Our make_a_commit adds its own
        # file, which is equivalent for versioning purposes.
        if setup is not None:
            setup(self)
        elif initial_version is not None:
            self.make_a_tagged_commit(initial_version)
        self.branch_to("develop")
        self.make_a_commit()
