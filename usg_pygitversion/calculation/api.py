# SPDX-License-Identifier: MIT
"""Run a full calculation.

Ports ``GitVersionCalculateTool.CalculateVersionVariables`` minus repository
preparation and caching, which land in Phase 5.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from usg_pygitversion.calculation.calculator import NextVersionCalculator
from usg_pygitversion.calculation.context import create_context
from usg_pygitversion.calculation.increment import IncrementStrategyFinder
from usg_pygitversion.calculation.store import RepositoryStore
from usg_pygitversion.calculation.strategies import Services
from usg_pygitversion.calculation.tagged_versions import (
    TaggedSemanticVersionRepository,
    TaggedSemanticVersionService,
)
from usg_pygitversion.calculation.variables import GitVersionVariables, get_variables_for
from usg_pygitversion.config.effective import EffectiveConfiguration, get_branch_configuration
from usg_pygitversion.config.provider import provide
from usg_pygitversion.config.schema import GitVersionConfiguration
from usg_pygitversion.git.repository import GitRepository


def calculate_variables(
    path: Path | str = ".",
    *,
    configuration: GitVersionConfiguration | None = None,
    override_document: Mapping[str, object] | None = None,
    explicit_config_file: str | None = None,
    target_branch: str | None = None,
    commit_id: str | None = None,
    only_tracked_branches: bool = False,
    environment: Mapping[str, str] | None = None,
) -> GitVersionVariables:
    """Calculate the output variables for the repository at ``path``.

    Args:
        path: Directory inside the working tree.
        configuration: A pre-built configuration (tests); otherwise it is
            loaded from ``GitVersion.yml`` plus ``override_document``.
        override_document: ``/overrideconfig`` values.
        explicit_config_file: ``/config`` path.
        target_branch: ``/b``: branch to calculate for instead of HEAD.
        commit_id: ``/c``: commit to calculate for.
        only_tracked_branches: Restrict detached-HEAD branch resolution to
            branches with an upstream.
        environment: Environment for ``{env:...}`` placeholders.
    """
    repository = GitRepository(path)
    if configuration is None:
        configuration = provide(
            Path(path).resolve(),
            repository.working_tree,
            explicit_file=explicit_config_file,
            override_document=override_document,
        )
    store = RepositoryStore(repository)
    tag_repository = TaggedSemanticVersionRepository(store)
    tag_service = TaggedSemanticVersionService(tag_repository)
    context = create_context(
        store,
        tag_repository,
        configuration,
        target_branch=target_branch,
        commit_id=commit_id,
        only_tracked_branches=only_tracked_branches,
        environment=environment,
    )
    services = Services(context, store, tag_service, IncrementStrategyFinder(store, tag_repository))
    version = NextVersionCalculator(context, store, tag_service, services).find_version()
    effective = EffectiveConfiguration.create(
        configuration, get_branch_configuration(configuration, context.current_branch.name)
    )
    return get_variables_for(
        version, configuration, effective.pre_release_weight, context.environment
    )
