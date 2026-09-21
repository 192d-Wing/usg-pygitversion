# SPDX-License-Identifier: MIT
"""Built-in workflow presets, vendored verbatim from GitVersion 6.8.2.

Ports ``WorkflowManager``. Upstream embeds the YAML files as assembly
resources named ``<Workflow>/<version>.yml``; here they live in the
``presets`` resource package as ``<Workflow>-<version>.yml``.

Upstream has two paths: no ``workflow`` key means "start from the GitFlow
builder's defaults"; a ``workflow`` key means "start empty and apply that
preset". Because each preset file is the *complete* serialised output of its
builder (the approved test files), starting from the ``GitFlow/v1`` file is
equivalent to the builder defaults. That is verified in the tests against a
``/showconfig`` capture from the reference binary.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from pygitversion.config.yaml_io import load_mapping
from pygitversion.errors import ConfigurationError

DEFAULT_WORKFLOW = "GitFlow/v1"
KNOWN_WORKFLOWS: tuple[str, ...] = ("GitFlow/v1", "GitHubFlow/v1", "TrunkBased/preview1")


def _resource_name(workflow: str) -> str:
    return workflow.replace("/", "-") + ".yml"


@lru_cache(maxsize=8)
def load_preset(workflow: str) -> dict[str, Any]:
    """Return the preset document for ``workflow``.

    The cached result is treated as read-only by callers; the merge step
    clones before modifying.

    Raises:
        ConfigurationError: If the workflow is not one of :data:`KNOWN_WORKFLOWS`.
    """
    # Exact-name lookup only: the value comes from user configuration and
    # must never be used to form an arbitrary path (AC-3).
    if workflow not in KNOWN_WORKFLOWS:
        names = ", ".join(KNOWN_WORKFLOWS)
        msg = f"unknown workflow {workflow!r}; expected one of: {names}"
        raise ConfigurationError(msg)
    resource = resources.files("pygitversion.config.presets").joinpath(_resource_name(workflow))
    text = resource.read_text(encoding="utf-8")
    return load_mapping(text, f"workflow preset {workflow}")
