# SPDX-License-Identifier: MIT
"""Resolve the settings that apply to one branch.

Ports ``EffectiveConfiguration``, ``ConfigurationExtensions.GetBranchConfiguration``
/ ``GetEffectiveConfiguration`` and ``GetBranchSpecificLabel`` from 6.8.2.
The recursive ``Inherit`` walk over source branches
(``EffectiveBranchConfigurationFinder``) needs the repository and lands in
Phase 3; this module provides the pieces it composes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from pygitversion.config.enums import (
    AssemblyFileVersioningScheme,
    AssemblyVersioningScheme,
    CommitMessageIncrementMode,
    DeploymentMode,
    IncrementStrategy,
    VersionStrategy,
)
from pygitversion.config.schema import (
    UNKNOWN_BRANCH_KEY,
    BranchConfiguration,
    GitVersionConfiguration,
    IgnoreConfiguration,
)
from pygitversion.dotnet import regex as dotnet_regex
from pygitversion.errors import ConfigurationError
from pygitversion.formatting import TemplateError, format_with
from pygitversion.git.refname import ReferenceName
from pygitversion.semver import SemanticVersionFormat

#: ``RegexPatterns.SanitizeNameRegexPattern``: anything not alphanumeric or ``-``.
_SANITIZE_NAME = re.compile(r"[^a-zA-Z0-9-]")
#: ``RegexPatterns.SanitizeLabelRegexPattern``: also allows ``.``.
_SANITIZE_LABEL = re.compile(r"[^a-zA-Z0-9-.]")


@dataclass(frozen=True, slots=True)
class EffectiveConfiguration:
    """Fully resolved settings for a branch: no ``None`` left. Ports ``EffectiveConfiguration``."""

    tracks_release_branches: bool
    is_release_branch: bool
    is_main_branch: bool
    mode: DeploymentMode
    assembly_versioning_scheme: AssemblyVersioningScheme
    assembly_file_versioning_scheme: AssemblyFileVersioningScheme
    assembly_informational_format: str | None
    assembly_versioning_format: str | None
    assembly_file_versioning_format: str | None
    tag_prefix: str | None
    version_in_branch_pattern: str | None
    label: str | None
    next_version: str | None
    increment: IncrementStrategy
    regex: str | None
    prevent_increment_of_merged_branch: bool
    prevent_increment_when_branch_merged: bool
    prevent_increment_when_current_commit_tagged: bool
    track_merge_target: bool
    track_merge_message: bool
    major_version_bump_message: str | None
    minor_version_bump_message: str | None
    patch_version_bump_message: str | None
    no_bump_message: str | None
    commit_message_incrementing: CommitMessageIncrementMode
    ignore: IgnoreConfiguration
    commit_date_format: str
    update_build_number: bool
    semantic_version_format: SemanticVersionFormat
    version_strategy: VersionStrategy
    pre_release_weight: int
    tag_pre_release_weight: int

    @classmethod
    def create(
        cls,
        configuration: GitVersionConfiguration,
        branch: BranchConfiguration,
        fallback: EffectiveConfiguration | None = None,
    ) -> EffectiveConfiguration:
        """Ports the ``EffectiveConfiguration`` constructor.

        Without ``fallback`` the branch inherits from the root configuration;
        with it, from that already-effective parent (used for ``Inherit``).

        Raises:
            ConfigurationError: If a required root value is missing. Upstream
                raises ``InvalidOperationException`` with "this should not
                happen"; with the vendored presets it cannot.
        """
        resolved = branch.inherit(
            configuration.as_branch() if fallback is None else fallback.as_branch()
        )
        for name, value in (
            ("mode", resolved.mode),
            ("assembly-versioning-scheme", configuration.assembly_versioning_scheme),
            ("assembly-file-versioning-scheme", configuration.assembly_file_versioning_scheme),
            ("commit-message-incrementing", resolved.commit_message_incrementing),
            ("tag-pre-release-weight", configuration.tag_pre_release_weight),
            ("commit-date-format", configuration.commit_date_format or None),
        ):
            if value is None:
                msg = (
                    f"Configuration value for '{name}' has no value. "
                    "(this should not happen, please report an issue)"
                )
                raise ConfigurationError(msg)
        # The loop above guarantees these are not None.
        assert resolved.mode is not None  # noqa: S101 -- checked above
        assert configuration.assembly_versioning_scheme is not None  # noqa: S101
        assert configuration.assembly_file_versioning_scheme is not None  # noqa: S101
        assert resolved.commit_message_incrementing is not None  # noqa: S101
        assert configuration.tag_pre_release_weight is not None  # noqa: S101
        assert configuration.commit_date_format  # noqa: S101
        return cls(
            tracks_release_branches=resolved.tracks_release_branches or False,
            is_release_branch=resolved.is_release_branch or False,
            is_main_branch=resolved.is_main_branch or False,
            mode=resolved.mode,
            assembly_versioning_scheme=configuration.assembly_versioning_scheme,
            assembly_file_versioning_scheme=configuration.assembly_file_versioning_scheme,
            assembly_informational_format=configuration.assembly_informational_format,
            assembly_versioning_format=configuration.assembly_versioning_format,
            assembly_file_versioning_format=configuration.assembly_file_versioning_format,
            tag_prefix=configuration.tag_prefix,
            version_in_branch_pattern=configuration.version_in_branch_pattern,
            label=resolved.label,
            next_version=configuration.next_version,
            increment=resolved.increment,
            regex=resolved.regex,
            prevent_increment_of_merged_branch=resolved.prevent_increment.of_merged_branch or False,
            prevent_increment_when_branch_merged=resolved.prevent_increment.when_branch_merged
            or False,
            prevent_increment_when_current_commit_tagged=(
                True
                if resolved.prevent_increment.when_current_commit_tagged is None
                else resolved.prevent_increment.when_current_commit_tagged
            ),
            track_merge_target=resolved.track_merge_target or False,
            track_merge_message=True
            if resolved.track_merge_message is None
            else resolved.track_merge_message,
            major_version_bump_message=configuration.major_version_bump_message,
            minor_version_bump_message=configuration.minor_version_bump_message,
            patch_version_bump_message=configuration.patch_version_bump_message,
            no_bump_message=configuration.no_bump_message,
            commit_message_incrementing=resolved.commit_message_incrementing,
            ignore=configuration.ignore,
            commit_date_format=configuration.commit_date_format,
            update_build_number=configuration.update_build_number,
            semantic_version_format=configuration.semantic_version_format,
            version_strategy=configuration.version_strategy,
            pre_release_weight=resolved.pre_release_weight or 0,
            tag_pre_release_weight=configuration.tag_pre_release_weight,
        )

    def as_branch(self) -> BranchConfiguration:
        """View as a fully populated branch config, for ``Inherit(EffectiveConfiguration)``."""
        from pygitversion.config.schema import PreventIncrementConfiguration  # noqa: PLC0415

        return BranchConfiguration(
            mode=self.mode,
            label=self.label,
            increment=self.increment,
            prevent_increment=PreventIncrementConfiguration(
                of_merged_branch=self.prevent_increment_of_merged_branch,
                when_branch_merged=self.prevent_increment_when_branch_merged,
                when_current_commit_tagged=self.prevent_increment_when_current_commit_tagged,
            ),
            track_merge_target=self.track_merge_target,
            track_merge_message=self.track_merge_message,
            commit_message_incrementing=self.commit_message_incrementing,
            regex=self.regex,
            tracks_release_branches=self.tracks_release_branches,
            is_release_branch=self.is_release_branch,
            is_main_branch=self.is_main_branch,
            pre_release_weight=self.pre_release_weight,
        )

    # -- label -----------------------------------------------------------------

    def branch_specific_label(
        self,
        branch_name: ReferenceName | str | None,
        branch_name_override: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> str | None:
        """Expand ``{BranchName}`` placeholders in ``label``. Ports ``GetBranchSpecificLabel``.

        Named groups of the branch ``regex`` become placeholders (values
        sanitised to ``[a-zA-Z0-9-]``) and the template engine handles
        ``{env:NAME}`` and ``??`` fallbacks. The result is sanitised to
        ``[a-zA-Z0-9-.]``. As upstream, a template that cannot be evaluated
        yields the *raw* label unchanged.
        """
        if self.label is None:
            return None
        name = branch_name.without_origin if isinstance(branch_name, ReferenceName) else branch_name
        effective_name = branch_name_override if branch_name_override is not None else name
        placeholders = _label_placeholders(self.regex, effective_name)

        def resolve(member: str) -> str | None:
            if member not in placeholders:
                msg = f"'{member}' is not a valid placeholder"
                raise TemplateError(msg)
            return placeholders[member]

        try:
            expanded = format_with(self.label, resolve, environment or {})
        except TemplateError:
            return self.label
        return _SANITIZE_LABEL.sub("-", expanded)


def _label_placeholders(regex: str | None, branch_name: str | None) -> dict[str, str]:
    """Ports ``BuildLabelPlaceholders``: named groups of the branch regex."""
    if not regex or not regex.strip() or not branch_name:
        return {}
    pattern = dotnet_regex.compile(regex)
    match = pattern.search(dotnet_regex.bounded(branch_name))
    if match is None:
        return {}
    return {
        group: _SANITIZE_NAME.sub("-", match.group(group) or "") for group in pattern.groupindex
    }


# ---------------------------------------------------------------------------
# Branch lookup
# ---------------------------------------------------------------------------


def get_branch_configuration(
    configuration: GitVersionConfiguration, branch_name: ReferenceName | str
) -> BranchConfiguration:
    """First configured branch whose regex matches, with ``unknown`` tried last.

    Ports ``ConfigurationExtensions.GetBranchConfiguration``. Matching uses
    the name without an ``origin/`` prefix. Falls back to
    :meth:`GitVersionConfiguration.empty_branch_configuration`.
    """
    name = branch_name.without_origin if isinstance(branch_name, ReferenceName) else branch_name
    unknown: BranchConfiguration | None = None
    for key, branch in configuration.branches.items():
        if not branch.is_match(name):
            continue
        if key == UNKNOWN_BRANCH_KEY:
            unknown = branch
        else:
            return branch
    return unknown if unknown is not None else GitVersionConfiguration.empty_branch_configuration()


def get_effective_configuration(
    configuration: GitVersionConfiguration,
    branch_name: ReferenceName | str,
    parent: EffectiveConfiguration | None = None,
) -> EffectiveConfiguration:
    """Ports ``ConfigurationExtensions.GetEffectiveConfiguration``.

    ``parent`` is only consulted when the matched branch's increment is
    ``Inherit``; otherwise the root configuration is the fallback.
    """
    branch = get_branch_configuration(configuration, branch_name)
    fallback = parent if branch.increment is IncrementStrategy.INHERIT else None
    return EffectiveConfiguration.create(configuration, branch, fallback)


def is_release_branch(
    configuration: GitVersionConfiguration, branch_name: ReferenceName | str
) -> bool:
    """Ports ``ConfigurationExtensions.IsReleaseBranch``."""
    return get_branch_configuration(configuration, branch_name).is_release_branch or False
