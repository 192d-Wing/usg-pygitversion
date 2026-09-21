# SPDX-License-Identifier: MIT
"""Build the configuration for a directory.

Ports ``ConfigurationProvider`` and ``ConfigurationBuilderBase.Build``
(finalise + validate) from 6.8.2.

Layering, in order:

1. Base: the selected workflow preset. Without a ``workflow`` key this is
   ``GitFlow/v1``, which equals upstream's ``GitFlowConfigurationBuilder``
   defaults; with a key it is that preset applied to an empty builder.
2. The configuration file (``GitVersion.yml`` in the working directory,
   else the project root).
3. Runtime overrides (``/overrideconfig``).

Then: ``is-source-branch-for`` entries are folded into the targets'
``source-branches`` (finalise) and the result is validated (every branch
needs ``regex``; every ``source-branches`` entry must exist).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from usg_pygitversion.config import workflows
from usg_pygitversion.config.locator import find_configuration_file
from usg_pygitversion.config.merge import clone, merge
from usg_pygitversion.config.schema import GitVersionConfiguration
from usg_pygitversion.config.yaml_io import load_mapping
from usg_pygitversion.errors import ConfigurationError

_log = logging.getLogger("usg_pygitversion.config")

_HELP_URL = "\nSee https://gitversion.net/docs/reference/configuration for more info"


def read_configuration_file(path: Path) -> dict[str, Any]:
    """Read and parse a configuration file into a document mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read configuration file {path}: {exc.strerror}"
        raise ConfigurationError(msg) from exc
    return load_mapping(text, f"configuration file {path}")


def _select_workflow(*documents: Mapping[str, Any] | None) -> str | None:
    """Last non-null ``workflow`` wins (file, then override). Ports ``GetWorkflow``."""
    workflow: str | None = None
    for document in documents:
        if document and document.get("workflow") is not None:
            workflow = str(document["workflow"])
    return workflow


def build(
    file_document: Mapping[str, Any] | None = None,
    override_document: Mapping[str, Any] | None = None,
) -> GitVersionConfiguration:
    """Compose preset, file and override documents into a validated configuration.

    Raises:
        ConfigurationError: On invalid values or an inconsistent branch graph.
    """
    workflow = _select_workflow(file_document, override_document)
    document = clone(workflows.load_preset(workflow or workflows.DEFAULT_WORKFLOW))
    for layer in (file_document, override_document):
        if layer:
            document = merge(document, layer)
    configuration = GitVersionConfiguration.from_mapping(document)
    configuration = _finalize(configuration)
    _validate(configuration)
    return configuration


def _finalize(configuration: GitVersionConfiguration) -> GitVersionConfiguration:
    """Fold ``is-source-branch-for`` into targets' ``source-branches``.

    Ports ``FinalizeConfiguration``.
    """
    branches = dict(configuration.branches)
    for name, branch in configuration.branches.items():
        for target_name in branch.is_source_branch_for:
            target = branches.get(target_name)
            if target is None:
                msg = (
                    f"Branch configuration '{name}' declares 'is-source-branch-for' "
                    f"'{target_name}', which is not configured{_HELP_URL}"
                )
                raise ConfigurationError(msg)
            if name not in target.source_branches:
                branches[target_name] = replace(
                    target, source_branches=(*target.source_branches, name)
                )
    return replace(configuration, branches=branches)


def _validate(configuration: GitVersionConfiguration) -> None:
    """Ports ``ValidateConfiguration``; messages match upstream."""
    for name, branch in configuration.branches.items():
        if branch.regex is None:
            msg = (
                f"Branch configuration '{name}' is missing required configuration "
                f"'regex'{_HELP_URL}"
            )
            raise ConfigurationError(msg)
        missing = [sb for sb in branch.source_branches if sb not in configuration.branches]
        if missing:
            msg = (
                f"Branch configuration '{name}' defines these 'source-branches' that are not "
                f"configured: '[{','.join(missing)}]'{_HELP_URL}"
            )
            raise ConfigurationError(msg)


def provide(
    working_directory: Path,
    project_root: Path | None = None,
    *,
    explicit_file: str | None = None,
    override_document: Mapping[str, Any] | None = None,
) -> GitVersionConfiguration:
    """Locate, load and build the configuration. Ports ``ConfigurationProvider.Provide``.

    Args:
        working_directory: Where the tool was invoked.
        project_root: The git working tree root, searched second.
        explicit_file: Optional ``/config`` path.
        override_document: Parsed ``/overrideconfig`` values.
    """
    path = find_configuration_file(working_directory, explicit_file)
    if path is None and project_root is not None:
        path = find_configuration_file(project_root, explicit_file)
    if path is None:
        _log.info("No configuration file found, using default configuration")
        file_document = None
    else:
        _log.info("Using configuration file '%s'", path)
        file_document = read_configuration_file(path)
    return build(file_document, override_document)
