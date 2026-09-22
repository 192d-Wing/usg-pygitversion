# SPDX-License-Identifier: MIT
"""The inputs of one calculation. Ports ``GitVersionContext`` and ``GitVersionContextFactory``."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from usg_pygitversion.calculation.store import RepositoryStore
from usg_pygitversion.calculation.tagged_versions import TaggedSemanticVersionRepository
from usg_pygitversion.config.schema import GitVersionConfiguration
from usg_pygitversion.errors import RepositoryError
from usg_pygitversion.formatting import redact_secrets
from usg_pygitversion.git.models import Branch, Commit

_log = logging.getLogger("usg_pygitversion.calculation")


@dataclass(frozen=True, slots=True)
class GitVersionContext:
    """Everything the calculator reads. Ports ``GitVersionContext``."""

    current_branch: Branch
    current_commit: Commit
    configuration: GitVersionConfiguration
    is_current_commit_tagged: bool
    uncommitted_changes: int
    environment: Mapping[str, str]

    def current_branch_commits(self, store: RepositoryStore) -> list[Commit]:
        """Branch commits at or before the current commit. Ports ``CurrentBranchCommits``."""
        return store.commits_prior_to(
            store.branch_commits(self.current_branch), self.current_commit.when
        )


def create_context(
    store: RepositoryStore,
    tags: TaggedSemanticVersionRepository,
    configuration: GitVersionConfiguration,
    *,
    target_branch: str | None = None,
    commit_id: str | None = None,
    only_tracked_branches: bool = False,
    environment: Mapping[str, str] | None = None,
) -> GitVersionContext:
    """Ports ``GitVersionContextFactory.Create``.

    Raises:
        RepositoryError: If the branch has no commits.
    """
    current_branch = store.get_target_branch(target_branch)
    current_commit = store.get_current_commit(current_branch, commit_id, configuration.ignore)
    if current_commit is None:
        raise RepositoryError("No commits found on the current branch.")
    if current_branch.is_detached_head:
        containing = store.get_branches_containing_commit(
            current_commit, only_tracked=only_tracked_branches
        )
        if len(containing) == 1:
            current_branch = containing[0]
    tagged = tags.all(
        configuration.tag_prefix, configuration.semantic_version_format, configuration.ignore
    )
    return GitVersionContext(
        current_branch=current_branch,
        current_commit=current_commit,
        configuration=configuration,
        is_current_commit_tagged=current_commit in tagged,
        uncommitted_changes=store.uncommitted_changes,
        # Configuration-driven templates only ever see a redacted environment
        # (SC-28): a GitVersion.yml label must not be able to lift a CI secret.
        environment=redact_secrets(environment) if environment is not None else {},
    )
