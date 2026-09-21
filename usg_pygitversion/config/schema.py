# SPDX-License-Identifier: MIT
"""Typed configuration model and its mapping (YAML) representation.

Ports ``BranchConfiguration``, ``PreventIncrementConfiguration``,
``IgnoreConfiguration`` and ``GitVersionConfiguration`` from GitVersion
6.8.2. Two facts drive the design:

* The root configuration *is* a branch configuration (upstream
  ``GitVersionConfiguration : BranchConfiguration``): the root-level
  ``mode``, ``label``, ``increment`` and so on are the fallback for every
  branch. :class:`GitVersionConfiguration` therefore embeds every branch
  field and exposes :meth:`GitVersionConfiguration.as_branch`.
* ``/showconfig`` output must match the reference binary byte for byte, so
  serialisation order is the upstream property declaration order, recorded
  once in :data:`BRANCH_FIELDS` and :data:`ROOT_FIELDS` and used by both the
  parser and the emitter.

Input validation (NIST SP 800-53 SI-10): every value is coerced to its
declared type or rejected with a message naming the key. Unknown keys are
ignored with a warning, matching upstream (verified against the binary).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Self

from usg_pygitversion.config.enums import (
    AssemblyFileVersioningScheme,
    AssemblyVersioningScheme,
    CommitMessageIncrementMode,
    DeploymentMode,
    IncrementStrategy,
    VersionStrategy,
)
from usg_pygitversion.errors import ConfigurationError
from usg_pygitversion.semver import SemanticVersionFormat

_log = logging.getLogger("usg_pygitversion.config")

BRANCH_NAME_PLACEHOLDER = "{BranchName}"
PULL_REQUEST_NUMBER_PLACEHOLDER = "{Number}"
UNKNOWN_BRANCH_KEY = "unknown"
PULL_REQUEST_BRANCH_KEY = "pull-request"

#: Upstream default strategies (``ConfigurationConstants.DefaultVersionStrategies``).
DEFAULT_VERSION_STRATEGIES: tuple[VersionStrategy, ...] = (
    VersionStrategy.FALLBACK,
    VersionStrategy.CONFIGURED_NEXT_VERSION,
    VersionStrategy.MERGE_MESSAGE,
    VersionStrategy.TAGGED_COMMIT,
    VersionStrategy.TRACK_RELEASE_BRANCHES,
    VersionStrategy.VERSION_IN_BRANCH_NAME,
)


# ---------------------------------------------------------------------------
# Field tables: (yaml key, attribute, kind). Order == upstream declaration
# order == /showconfig output order.
# ---------------------------------------------------------------------------

_PREVENT_FIELDS: tuple[tuple[str, str], ...] = (
    ("of-merged-branch", "of_merged_branch"),
    ("when-branch-merged", "when_branch_merged"),
    ("when-current-commit-tagged", "when_current_commit_tagged"),
)

BRANCH_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("mode", "mode", "enum:DeploymentMode"),
    ("label", "label", "str"),
    ("increment", "increment", "enum:IncrementStrategy"),
    ("prevent-increment", "prevent_increment", "prevent"),
    ("track-merge-target", "track_merge_target", "bool"),
    ("track-merge-message", "track_merge_message", "bool"),
    (
        "commit-message-incrementing",
        "commit_message_incrementing",
        "enum:CommitMessageIncrementMode",
    ),
    ("regex", "regex", "str"),
    ("source-branches", "source_branches", "strset"),
    ("is-source-branch-for", "is_source_branch_for", "strset"),
    ("tracks-release-branches", "tracks_release_branches", "bool"),
    ("is-release-branch", "is_release_branch", "bool"),
    ("is-main-branch", "is_main_branch", "bool"),
    ("pre-release-weight", "pre_release_weight", "int"),
)

ROOT_ONLY_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("workflow", "workflow", "str"),
    ("assembly-versioning-scheme", "assembly_versioning_scheme", "enum:AssemblyVersioningScheme"),
    (
        "assembly-file-versioning-scheme",
        "assembly_file_versioning_scheme",
        "enum:AssemblyFileVersioningScheme",
    ),
    ("assembly-informational-format", "assembly_informational_format", "str"),
    ("assembly-versioning-format", "assembly_versioning_format", "str"),
    ("assembly-file-versioning-format", "assembly_file_versioning_format", "str"),
    ("tag-prefix", "tag_prefix", "str"),
    ("version-in-branch-pattern", "version_in_branch_pattern", "str"),
    ("next-version", "next_version", "next-version"),
    ("major-version-bump-message", "major_version_bump_message", "str"),
    ("minor-version-bump-message", "minor_version_bump_message", "str"),
    ("patch-version-bump-message", "patch_version_bump_message", "str"),
    ("no-bump-message", "no_bump_message", "str"),
    ("tag-pre-release-weight", "tag_pre_release_weight", "int"),
    ("commit-date-format", "commit_date_format", "str"),
    ("merge-message-formats", "merge_message_formats", "strdict"),
    ("update-build-number", "update_build_number", "bool!"),
    ("semantic-version-format", "semantic_version_format", "enum:SemanticVersionFormat!"),
    ("strategies", "strategies", "strategies"),
    ("branches", "branches", "branches"),
    ("ignore", "ignore", "ignore"),
)

ROOT_FIELDS: tuple[tuple[str, str, str], ...] = BRANCH_FIELDS + ROOT_ONLY_FIELDS

_ENUMS: dict[str, type[Any]] = {
    "DeploymentMode": DeploymentMode,
    "IncrementStrategy": IncrementStrategy,
    "CommitMessageIncrementMode": CommitMessageIncrementMode,
    "AssemblyVersioningScheme": AssemblyVersioningScheme,
    "AssemblyFileVersioningScheme": AssemblyFileVersioningScheme,
    "SemanticVersionFormat": SemanticVersionFormat,
}


# ---------------------------------------------------------------------------
# Value coercion (SI-10)
# ---------------------------------------------------------------------------


def _bad(key: str, value: object, expected: str) -> ConfigurationError:
    return ConfigurationError(f"configuration key '{key}' expects {expected}, got {value!r}")


def _coerce_bool(key: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise _bad(key, value, "true or false")


def _coerce_int(key: str, value: object) -> int:
    if isinstance(value, bool):
        raise _bad(key, value, "an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+", value.strip()):
        return int(value.strip())
    raise _bad(key, value, "an integer")


def _coerce_str(key: str, value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    raise _bad(key, value, "a string")


def _coerce_next_version(key: str, value: object) -> str:
    """Ports the ``NextVersion`` setter: an integer ``N`` becomes ``N.0``.

    A YAML float such as ``2.10`` arrives as ``2.1``; the reference binary
    behaves the same (verified), so no attempt is made to preserve zeros.
    """
    if isinstance(value, bool):
        raise _bad(key, value, "a version string")
    if isinstance(value, int):
        return f"{value}.0"
    text = _coerce_str(key, value)
    try:
        return f"{int(text.strip())}.0"
    except ValueError:
        return text


def _coerce_strset(key: str, value: object) -> tuple[str, ...]:
    """Ordered, de-duplicated list of strings (upstream ``HashSet<string>``)."""
    if value is None:
        return ()
    if isinstance(value, str):
        items: list[object] = [value]
    elif isinstance(value, list | tuple):
        items = list(value)
    else:
        raise _bad(key, value, "a list of strings")
    out: list[str] = []
    for item in items:
        text = _coerce_str(key, item)
        if text not in out:
            out.append(text)
    return tuple(out)


def _coerce_enum(key: str, value: object, enum_name: str) -> Any:
    enum_type = _ENUMS[enum_name]
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise _bad(key, value, f"a {enum_name} name")
    try:
        return enum_type.parse(value)
    except (ConfigurationError, ValueError) as exc:
        raise ConfigurationError(f"configuration key '{key}': {exc}") from None


def _coerce_strategies(key: str, value: object) -> tuple[VersionStrategy, ...]:
    """Accept a YAML list or a comma-separated scalar (``VersionStrategiesConverter``)."""
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        items: list[object] = [part.strip() for part in text.split(",") if part.strip()]
    elif isinstance(value, list | tuple):
        items = list(value)
    else:
        raise _bad(key, value, "a list of strategy names")
    return tuple(VersionStrategy.parse(_coerce_str(key, item)) for item in items)


def _coerce_strdict(key: str, value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise _bad(key, value, "a mapping of strings")
    return {_coerce_str(key, k): _coerce_str(key, v) for k, v in value.items()}


def _coerce_datetime(key: str, value: object) -> datetime:
    """``commits-before``: ISO-8601; naive values are UTC (``DateTimeOffset.Parse``)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            raise _bad(key, value, "a date/time such as 2020-01-01T00:00:00") from None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise _bad(key, value, "a date/time such as 2020-01-01T00:00:00")


def _warn_unknown(context: str, mapping: Mapping[str, object], known: set[str]) -> None:
    for key in mapping:
        if key not in known:
            _log.warning("ignoring unknown configuration key '%s' in %s", key, context)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreventIncrementConfiguration:
    """Ports ``PreventIncrementConfiguration``; ``None`` means "inherit"."""

    of_merged_branch: bool | None = None
    when_branch_merged: bool | None = None
    when_current_commit_tagged: bool | None = None

    @classmethod
    def from_mapping(cls, value: object, context: str) -> Self:
        """Parse the ``prevent-increment`` mapping."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise _bad(f"{context}.prevent-increment", value, "a mapping")
        _warn_unknown(f"{context}.prevent-increment", value, {k for k, _ in _PREVENT_FIELDS})
        kwargs = {
            attr: _coerce_bool(f"{context}.prevent-increment.{key}", value[key])
            for key, attr in _PREVENT_FIELDS
            if value.get(key) is not None
        }
        return cls(**kwargs)

    def to_mapping(self) -> dict[str, object]:
        """Serialise, omitting ``None`` (``YamlIgnoreCondition.WhenWritingNull``)."""
        return {
            key: getattr(self, attr)
            for key, attr in _PREVENT_FIELDS
            if getattr(self, attr) is not None
        }

    def inherit(self, parent: PreventIncrementConfiguration) -> PreventIncrementConfiguration:
        """Fill ``None`` values from ``parent``."""
        return PreventIncrementConfiguration(
            of_merged_branch=_first(self.of_merged_branch, parent.of_merged_branch),
            when_branch_merged=_first(self.when_branch_merged, parent.when_branch_merged),
            when_current_commit_tagged=_first(
                self.when_current_commit_tagged, parent.when_current_commit_tagged
            ),
        )


def _first(*values: bool | None) -> bool | None:
    """``??`` chain."""
    for value in values:
        if value is not None:
            return value
    return None


@dataclass(frozen=True, slots=True)
class IgnoreConfiguration:
    """Ports ``IgnoreConfiguration`` (6.8.2: ``commits-before``, ``sha``, ``paths``)."""

    before: datetime | None = None
    shas: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: object) -> Self:
        """Parse the ``ignore`` mapping."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise _bad("ignore", value, "a mapping")
        _warn_unknown("ignore", value, {"commits-before", "sha", "paths"})
        before = value.get("commits-before")
        return cls(
            before=_coerce_datetime("ignore.commits-before", before)
            if before is not None
            else None,
            shas=_coerce_strset("ignore.sha", value.get("sha")),
            paths=_coerce_strset("ignore.paths", value.get("paths")),
        )

    def to_mapping(self) -> dict[str, object]:
        """Serialise in upstream property order."""
        out: dict[str, object] = {}
        if self.before is not None:
            # Upstream formats with the .NET pattern yyyy-MM-ddTHH:mm:ssZ.
            out["commits-before"] = self.before.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        out["sha"] = list(self.shas)
        out["paths"] = list(self.paths)
        return out

    @property
    def is_empty(self) -> bool:
        """True when nothing is configured."""
        return self.before is None and not self.shas and not self.paths


@dataclass(frozen=True, slots=True)
class BranchConfiguration:
    """Per-branch settings. ``None`` means "not set, inherit". Ports ``BranchConfiguration``."""

    mode: DeploymentMode | None = None
    label: str | None = None
    increment: IncrementStrategy = IncrementStrategy.NONE
    prevent_increment: PreventIncrementConfiguration = field(
        default_factory=PreventIncrementConfiguration
    )
    track_merge_target: bool | None = None
    track_merge_message: bool | None = None
    commit_message_incrementing: CommitMessageIncrementMode | None = None
    regex: str | None = None
    source_branches: tuple[str, ...] = ()
    is_source_branch_for: tuple[str, ...] = ()
    tracks_release_branches: bool | None = None
    is_release_branch: bool | None = None
    is_main_branch: bool | None = None
    pre_release_weight: int | None = None

    @classmethod
    def from_mapping(cls, value: object, context: str) -> Self:
        """Parse one ``branches.<name>`` mapping."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise _bad(context, value, "a mapping")
        _warn_unknown(context, value, {k for k, _, _ in BRANCH_FIELDS})
        return cls(**_parse_fields(value, BRANCH_FIELDS, context))

    def to_mapping(self) -> dict[str, object]:
        """Serialise in upstream order, omitting ``None``."""
        return _emit_fields(self, BRANCH_FIELDS)

    def is_match(self, branch_name: str) -> bool:
        """Ports ``IBranchConfiguration.IsMatch`` (search, case-insensitive)."""
        # Deferred import avoids an import cycle with the dotnet package.
        from usg_pygitversion.dotnet import regex as dotnet_regex  # noqa: PLC0415

        if not self.regex or not self.regex.strip():
            return False
        return (
            dotnet_regex.compile(self.regex).search(dotnet_regex.bounded(branch_name)) is not None
        )

    def inherit(self, parent: BranchConfiguration) -> BranchConfiguration:
        """Fill unset values from ``parent``. Ports ``Inherit(IBranchConfiguration)``.

        ``source_branches`` and ``is_source_branch_for`` are *not* inherited
        (upstream copies them from ``this`` via the record copy constructor).
        """
        return replace(
            self,
            increment=parent.increment
            if self.increment is IncrementStrategy.INHERIT
            else self.increment,
            mode=self.mode if self.mode is not None else parent.mode,
            label=self.label if self.label is not None else parent.label,
            prevent_increment=self.prevent_increment.inherit(parent.prevent_increment),
            track_merge_target=_first(self.track_merge_target, parent.track_merge_target),
            track_merge_message=_first(self.track_merge_message, parent.track_merge_message),
            commit_message_incrementing=(
                self.commit_message_incrementing
                if self.commit_message_incrementing is not None
                else parent.commit_message_incrementing
            ),
            regex=self.regex if self.regex is not None else parent.regex,
            tracks_release_branches=_first(
                self.tracks_release_branches, parent.tracks_release_branches
            ),
            is_release_branch=_first(self.is_release_branch, parent.is_release_branch),
            is_main_branch=_first(self.is_main_branch, parent.is_main_branch),
            pre_release_weight=(
                self.pre_release_weight
                if self.pre_release_weight is not None
                else parent.pre_release_weight
            ),
        )


@dataclass(frozen=True, slots=True)
class GitVersionConfiguration:
    """The whole configuration. Ports ``GitVersionConfiguration``.

    The first block of attributes mirrors :class:`BranchConfiguration` and
    acts as the fallback for every branch (see :meth:`as_branch`).
    """

    # -- branch-level fallbacks (upstream: inherited from BranchConfiguration)
    mode: DeploymentMode | None = None
    label: str | None = None
    increment: IncrementStrategy = IncrementStrategy.NONE
    prevent_increment: PreventIncrementConfiguration = field(
        default_factory=PreventIncrementConfiguration
    )
    track_merge_target: bool | None = None
    track_merge_message: bool | None = None
    commit_message_incrementing: CommitMessageIncrementMode | None = None
    regex: str | None = None
    source_branches: tuple[str, ...] = ()
    is_source_branch_for: tuple[str, ...] = ()
    tracks_release_branches: bool | None = None
    is_release_branch: bool | None = None
    is_main_branch: bool | None = None
    pre_release_weight: int | None = None
    # -- root-only
    workflow: str | None = None
    assembly_versioning_scheme: AssemblyVersioningScheme | None = None
    assembly_file_versioning_scheme: AssemblyFileVersioningScheme | None = None
    assembly_informational_format: str | None = None
    assembly_versioning_format: str | None = None
    assembly_file_versioning_format: str | None = None
    tag_prefix: str | None = None
    version_in_branch_pattern: str | None = None
    next_version: str | None = None
    major_version_bump_message: str | None = None
    minor_version_bump_message: str | None = None
    patch_version_bump_message: str | None = None
    no_bump_message: str | None = None
    tag_pre_release_weight: int | None = None
    commit_date_format: str | None = None
    merge_message_formats: dict[str, str] = field(default_factory=dict)
    update_build_number: bool = True
    semantic_version_format: SemanticVersionFormat = SemanticVersionFormat.STRICT
    strategies: tuple[VersionStrategy, ...] = ()
    branches: dict[str, BranchConfiguration] = field(default_factory=dict)
    ignore: IgnoreConfiguration = field(default_factory=IgnoreConfiguration)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Parse a flat (6.x) configuration document.

        Raises:
            ConfigurationError: On any type error; unknown keys only warn.
        """
        _warn_unknown("configuration", value, {k for k, _, _ in ROOT_FIELDS})
        return cls(**_parse_fields(value, ROOT_FIELDS, "configuration"))

    def to_mapping(self) -> dict[str, object]:
        """Serialise in the exact ``/showconfig`` order, omitting ``None``."""
        return _emit_fields(self, ROOT_FIELDS)

    def as_branch(self) -> BranchConfiguration:
        """The root settings viewed as the fallback branch configuration."""
        return BranchConfiguration(**{attr: getattr(self, attr) for _, attr, _ in BRANCH_FIELDS})

    @property
    def version_strategy(self) -> VersionStrategy:
        """All configured strategies OR-ed together. Ports ``VersionStrategy``."""
        result = VersionStrategy.NONE
        for item in self.strategies:
            result |= item
        return result

    @staticmethod
    def empty_branch_configuration() -> BranchConfiguration:
        """Config for a branch nothing matches. Ports ``GetEmptyBranchConfiguration``."""
        return BranchConfiguration(
            regex="", label=BRANCH_NAME_PLACEHOLDER, increment=IncrementStrategy.INHERIT
        )


# ---------------------------------------------------------------------------
# Table-driven parse / emit
# ---------------------------------------------------------------------------


def _parse_fields(  # noqa: PLR0912 -- one branch per field kind
    mapping: Mapping[str, object], fields: tuple[tuple[str, str, str], ...], context: str
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for key, attr, kind in fields:
        if key not in mapping:
            continue
        raw = mapping[key]
        path = f"{context}.{key}" if context != "configuration" else key
        required = kind.endswith("!")
        kind_ = kind.rstrip("!")
        if raw is None:
            if kind_ in ("strset", "strategies"):
                kwargs[attr] = ()
            elif kind_ in ("strdict", "branches"):
                kwargs[attr] = {}
            elif not required:
                kwargs[attr] = None
            continue
        if kind_ == "str":
            kwargs[attr] = _coerce_str(path, raw)
        elif kind_ == "int":
            kwargs[attr] = _coerce_int(path, raw)
        elif kind_ == "bool":
            kwargs[attr] = _coerce_bool(path, raw)
        elif kind_.startswith("enum:"):
            kwargs[attr] = _coerce_enum(path, raw, kind_[5:])
        elif kind_ == "prevent":
            kwargs[attr] = PreventIncrementConfiguration.from_mapping(raw, context)
        elif kind_ == "strset":
            kwargs[attr] = _coerce_strset(path, raw)
        elif kind_ == "next-version":
            kwargs[attr] = _coerce_next_version(path, raw)
        elif kind_ == "strdict":
            kwargs[attr] = _coerce_strdict(path, raw)
        elif kind_ == "strategies":
            kwargs[attr] = _coerce_strategies(path, raw)
        elif kind_ == "branches":
            if not isinstance(raw, Mapping):
                raise _bad(path, raw, "a mapping of branch configurations")
            kwargs[attr] = {
                str(name): BranchConfiguration.from_mapping(cfg, f"branches.{name}")
                for name, cfg in raw.items()
            }
        elif kind_ == "ignore":
            kwargs[attr] = IgnoreConfiguration.from_mapping(raw)
    return kwargs


def _emit_fields(obj: object, fields: tuple[tuple[str, str, str], ...]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, attr, kind in fields:
        value = getattr(obj, attr)
        kind_ = kind.rstrip("!")
        if value is None:
            continue
        if kind_ == "prevent":
            out[key] = value.to_mapping()
        elif kind_ == "strset":
            out[key] = list(value)
        elif kind_ == "strategies":
            out[key] = [item.upstream_name for item in value]
        elif kind_ == "branches":
            out[key] = {name: cfg.to_mapping() for name, cfg in value.items()}
        elif kind_ == "ignore":
            out[key] = value.to_mapping()
        elif kind_ == "strdict":
            out[key] = dict(value)
        elif kind_.startswith("enum:"):
            out[key] = value.value
        else:
            out[key] = value
    return out
