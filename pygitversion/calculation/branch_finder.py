# SPDX-License-Identifier: MIT
"""Resolve ``Inherit`` by walking source branches. Ports ``EffectiveBranchConfigurationFinder``."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from pygitversion.calculation.base_version import EffectiveBranchConfiguration
from pygitversion.calculation.store import RepositoryStore
from pygitversion.config.effective import EffectiveConfiguration, get_branch_configuration
from pygitversion.config.enums import IncrementStrategy
from pygitversion.config.schema import BranchConfiguration, GitVersionConfiguration
from pygitversion.git.models import Branch

_log = logging.getLogger("pygitversion.calculation")


class EffectiveBranchConfigurationFinder:
    """Yields one effective configuration per resolved source-branch path."""

    def __init__(self, store: RepositoryStore) -> None:
        """Bind to the store."""
        self.store = store

    def get_configurations(
        self, branch: Branch, configuration: GitVersionConfiguration
    ) -> list[EffectiveBranchConfiguration]:
        """Ports ``GetConfigurations``."""
        return list(self._recursive(branch, configuration, None, set()))

    def _recursive(
        self,
        branch: Branch,
        configuration: GitVersionConfiguration,
        child: BranchConfiguration | None,
        traversed: set[Branch],
    ) -> Iterator[EffectiveBranchConfiguration]:
        if branch in traversed:
            return  # circuit breaker, as upstream
        traversed.add(branch)
        branch_configuration = get_branch_configuration(configuration, branch.name)
        if child is not None:
            branch_configuration = child.inherit(branch_configuration)
        if branch_configuration.increment is not IncrementStrategy.INHERIT:
            yield EffectiveBranchConfiguration(
                EffectiveConfiguration.create(configuration, branch_configuration), branch
            )
            return
        sources = self.store.get_source_branches(branch, configuration, traversed)
        if not sources:
            skip = configuration.increment is IncrementStrategy.INHERIT
            _log.info(
                "An orphaned branch '%s' has been detected and will be skipped=%s.", branch, skip
            )
            if not skip:
                yield EffectiveBranchConfiguration(
                    EffectiveConfiguration.create(configuration, branch_configuration), branch
                )
            return
        for source in sources:
            yield from self._recursive(source, configuration, branch_configuration, traversed)
