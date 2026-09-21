# SPDX-License-Identifier: MIT
"""The output variables.

Ports ``SemanticVersionFormatValues``, ``VariableProvider`` and
``GitVersionVariables`` from 6.8.2.

``GitVersionVariables`` is an ordered mapping whose key order is upstream's
``AvailableVariables`` list; JSON and other writers rely on it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC

from pygitversion.calculation.formatting import TemplateError, format_with
from pygitversion.config.enums import AssemblyFileVersioningScheme, AssemblyVersioningScheme
from pygitversion.config.schema import GitVersionConfiguration
from pygitversion.dotnet.dateformat import format_datetime
from pygitversion.errors import ConfigurationError
from pygitversion.semver import SemanticVersion

_SANITIZE_NAME = re.compile(r"[^a-zA-Z0-9-]")
_SANITIZE_ASSEMBLY_INFO = re.compile(r"[^0-9A-Za-z-.+]")

#: Upstream ``GitVersionVariables.AvailableVariables`` order.
AVAILABLE_VARIABLES: tuple[str, ...] = (
    "AssemblySemFileVer",
    "AssemblySemVer",
    "BranchName",
    "BuildMetaData",
    "CommitDate",
    "CommitsSinceVersionSource",
    "EscapedBranchName",
    "FullBuildMetaData",
    "FullSemVer",
    "InformationalVersion",
    "Major",
    "MajorMinorPatch",
    "Minor",
    "Patch",
    "PreReleaseLabel",
    "PreReleaseLabelWithDash",
    "PreReleaseNumber",
    "PreReleaseTag",
    "PreReleaseTagWithDash",
    "SemVer",
    "Sha",
    "ShortSha",
    "UncommittedChanges",
    "VersionSourceDistance",
    "VersionSourceIncrement",
    "VersionSourceSemVer",
    "VersionSourceSha",
    "WeightedPreReleaseNumber",
)


def _scheme_format(v: SemanticVersion, scheme: str) -> str | None:
    """Shared body of the two scheme formatters (the enums have identical members)."""
    number = v.prerelease.number or 0
    return {
        "Major": f"{v.major}.0.0.0",
        "MajorMinor": f"{v.major}.{v.minor}.0.0",
        "MajorMinorPatch": f"{v.major}.{v.minor}.{v.patch}.0",
        "MajorMinorPatchTag": f"{v.major}.{v.minor}.{v.patch}.{number}",
        "None": None,
    }[scheme]


def assembly_version(version: SemanticVersion, scheme: AssemblyVersioningScheme) -> str | None:
    """Ports ``GetAssemblyVersion``."""
    return _scheme_format(version, scheme.value)


def assembly_file_version(
    version: SemanticVersion, scheme: AssemblyFileVersioningScheme
) -> str | None:
    """Ports ``GetAssemblyFileVersion``."""
    return _scheme_format(version, scheme.value)


def _with_prefix(value: str, prefix: str) -> str:
    return prefix + value if value else value


class SemanticVersionFormatValues:
    """Ports ``SemanticVersionFormatValues``: every derived string for a version."""

    def __init__(
        self,
        version: SemanticVersion,
        configuration: GitVersionConfiguration,
        pre_release_weight: int,
    ) -> None:
        """Bind the inputs."""
        self.v = version
        self.c = configuration
        self.weight = pre_release_weight

    @property
    def major(self) -> str:
        """Major."""
        return str(self.v.major)

    @property
    def minor(self) -> str:
        """Minor."""
        return str(self.v.minor)

    @property
    def patch(self) -> str:
        """Patch."""
        return str(self.v.patch)

    @property
    def pre_release_tag(self) -> str:
        """``beta.1``."""
        return str(self.v.prerelease)

    @property
    def pre_release_tag_with_dash(self) -> str:
        """``-beta.1``."""
        return _with_prefix(self.pre_release_tag, "-")

    @property
    def pre_release_label(self) -> str:
        """``beta``."""
        return self.v.prerelease.name

    @property
    def pre_release_label_with_dash(self) -> str:
        """``-beta``."""
        return _with_prefix(self.pre_release_label, "-")

    @property
    def pre_release_number(self) -> str:
        """``1`` or empty."""
        return "" if self.v.prerelease.number is None else str(self.v.prerelease.number)

    @property
    def weighted_pre_release_number(self) -> str:
        """Number plus branch weight, or the tag weight for a release."""
        if self.v.prerelease.number is not None:
            return str(self.v.prerelease.number + self.weight)
        return str(self.c.tag_pre_release_weight)

    @property
    def build_metadata(self) -> str:
        """Format ``b``."""
        return self.v.build_metadata.to_string("b")

    @property
    def full_build_metadata(self) -> str:
        """Format ``f``."""
        return self.v.build_metadata.to_string("f")

    @property
    def major_minor_patch(self) -> str:
        """``1.2.3``."""
        return f"{self.v.major}.{self.v.minor}.{self.v.patch}"

    @property
    def sem_ver(self) -> str:
        """Format ``s``."""
        return self.v.to_string("s")

    @property
    def assembly_sem_ver(self) -> str | None:
        """Per ``assembly-versioning-scheme``."""
        scheme = self.c.assembly_versioning_scheme
        if scheme is None:
            raise ConfigurationError("assembly-versioning-scheme has no value")
        return assembly_version(self.v, scheme)

    @property
    def assembly_file_sem_ver(self) -> str | None:
        """Per ``assembly-file-versioning-scheme``."""
        scheme = self.c.assembly_file_versioning_scheme
        if scheme is None:
            raise ConfigurationError("assembly-file-versioning-scheme has no value")
        return assembly_file_version(self.v, scheme)

    @property
    def full_sem_ver(self) -> str:
        """Format ``f``."""
        return self.v.to_string("f")

    @property
    def branch_name(self) -> str | None:
        """Branch from metadata."""
        return self.v.build_metadata.branch

    @property
    def escaped_branch_name(self) -> str | None:
        """Branch with non ``[a-zA-Z0-9-]`` replaced by ``-``."""
        b = self.v.build_metadata.branch
        return None if b is None else _SANITIZE_NAME.sub("-", b)

    @property
    def sha(self) -> str | None:
        """Full SHA."""
        return self.v.build_metadata.sha

    @property
    def short_sha(self) -> str | None:
        """Short SHA."""
        return self.v.build_metadata.short_sha

    @property
    def commit_date(self) -> str | None:
        """Commit date in UTC using ``commit-date-format``."""
        when = self.v.build_metadata.commit_date
        if when is None:
            return None
        return format_datetime(
            when.astimezone(UTC).replace(tzinfo=None), self.c.commit_date_format or "yyyy-MM-dd"
        )

    @property
    def informational_version(self) -> str:
        """Format ``i``."""
        return self.v.to_string("i")

    @property
    def version_source_sem_ver(self) -> str | None:
        """Baseline version."""
        source = self.v.build_metadata.version_source_semver
        return None if source is None else str(source)

    @property
    def version_source_sha(self) -> str | None:
        """Baseline SHA."""
        return self.v.build_metadata.version_source_sha

    @property
    def version_source_distance(self) -> str:
        """Commits since the baseline."""
        return str(self.v.build_metadata.version_source_distance)

    @property
    def commits_since_version_source(self) -> str:
        """Deprecated alias of :attr:`version_source_distance`."""
        return self.version_source_distance

    @property
    def uncommitted_changes(self) -> str:
        """Dirty count."""
        return str(self.v.build_metadata.uncommitted_changes)

    @property
    def version_source_increment(self) -> str:
        """``None``/``Patch``/``Minor``/``Major``."""
        return self.v.build_metadata.version_source_increment.upstream_name

    #: Template member names (upstream property names) -> attribute names.
    MEMBERS: Mapping[str, str] = {
        "Major": "major",
        "Minor": "minor",
        "Patch": "patch",
        "PreReleaseTag": "pre_release_tag",
        "PreReleaseTagWithDash": "pre_release_tag_with_dash",
        "PreReleaseLabel": "pre_release_label",
        "PreReleaseLabelWithDash": "pre_release_label_with_dash",
        "PreReleaseNumber": "pre_release_number",
        "WeightedPreReleaseNumber": "weighted_pre_release_number",
        "BuildMetaData": "build_metadata",
        "FullBuildMetaData": "full_build_metadata",
        "MajorMinorPatch": "major_minor_patch",
        "SemVer": "sem_ver",
        "AssemblySemVer": "assembly_sem_ver",
        "AssemblyFileSemVer": "assembly_file_sem_ver",
        "FullSemVer": "full_sem_ver",
        "BranchName": "branch_name",
        "EscapedBranchName": "escaped_branch_name",
        "Sha": "sha",
        "ShortSha": "short_sha",
        "CommitDate": "commit_date",
        "InformationalVersion": "informational_version",
        "VersionSourceSemVer": "version_source_sem_ver",
        "VersionSourceSha": "version_source_sha",
        "CommitsSinceVersionSource": "commits_since_version_source",
        "VersionSourceDistance": "version_source_distance",
        "UncommittedChanges": "uncommitted_changes",
        "VersionSourceIncrement": "version_source_increment",
    }

    def resolve(self, member: str) -> str | None:
        """Member lookup for :func:`format_with`; unknown members raise."""
        attr = self.MEMBERS.get(member)
        if attr is None:
            msg = f"'{member}' is not a property or field on type 'SemanticVersionFormatValues'"
            raise TemplateError(msg)
        value: str | None = getattr(self, attr)
        return value


@dataclass(frozen=True, slots=True)
class GitVersionVariables:
    """The 28 output variables in upstream order. Ports ``GitVersionVariables``."""

    values: Mapping[str, str | None]

    def __getitem__(self, name: str) -> str | None:
        """Variable by name (case-sensitive, as upstream)."""
        return self.values[name]

    def get(self, name: str) -> str | None:
        """Case-insensitive lookup used by ``/showvariable``; ``None`` if unknown."""
        for key, value in self.values.items():
            if key.lower() == name.lower():
                return value
        return None

    def __iter__(self) -> Iterator[tuple[str, str | None]]:
        """Iterate ``(name, value)`` in upstream order."""
        return iter(self.values.items())

    def __contains__(self, name: object) -> bool:
        """Membership by exact name."""
        return name in self.values

    @property
    def full_sem_ver(self) -> str:
        """``FullSemVer`` (never ``None``)."""
        return self.values["FullSemVer"] or ""

    @property
    def sem_ver(self) -> str:
        """``SemVer``."""
        return self.values["SemVer"] or ""

    @property
    def major_minor_patch(self) -> str:
        """``MajorMinorPatch``."""
        return self.values["MajorMinorPatch"] or ""

    def as_dict(self) -> dict[str, str | None]:
        """A plain ordered dict copy."""
        return dict(self.values)


def get_variables_for(
    version: SemanticVersion,
    configuration: GitVersionConfiguration,
    pre_release_weight: int,
    environment: Mapping[str, str] | None = None,
) -> GitVersionVariables:
    """Ports ``VariableProvider.GetVariablesFor``."""
    env = environment or {}
    f = SemanticVersionFormatValues(version, configuration, pre_release_weight)

    def check_and_format(template: str | None, default: str | None, name: str) -> str | None:
        if not template:
            return default
        try:
            return _SANITIZE_ASSEMBLY_INFO.sub("-", format_with(template, f.resolve, env))
        except TemplateError as exc:
            msg = f"Unable to format {name}.  Check your format string: {exc}"
            raise ConfigurationError(msg) from exc

    informational = check_and_format(
        configuration.assembly_informational_format,
        f.informational_version,
        "AssemblyInformationalVersion",
    )
    assembly_file = check_and_format(
        configuration.assembly_file_versioning_format,
        f.assembly_file_sem_ver,
        "AssemblyFileVersioningFormat",
    )
    assembly = check_and_format(
        configuration.assembly_versioning_format, f.assembly_sem_ver, "AssemblyVersioningFormat"
    )
    values: dict[str, str | None] = {
        "AssemblySemFileVer": assembly_file,
        "AssemblySemVer": assembly,
        "BranchName": f.branch_name,
        "BuildMetaData": f.build_metadata,
        "CommitDate": f.commit_date,
        "CommitsSinceVersionSource": f.version_source_distance,
        "EscapedBranchName": f.escaped_branch_name,
        "FullBuildMetaData": f.full_build_metadata,
        "FullSemVer": f.full_sem_ver,
        "InformationalVersion": informational,
        "Major": f.major,
        "MajorMinorPatch": f.major_minor_patch,
        "Minor": f.minor,
        "Patch": f.patch,
        "PreReleaseLabel": f.pre_release_label,
        "PreReleaseLabelWithDash": f.pre_release_label_with_dash,
        "PreReleaseNumber": f.pre_release_number,
        "PreReleaseTag": f.pre_release_tag,
        "PreReleaseTagWithDash": f.pre_release_tag_with_dash,
        "SemVer": f.sem_ver,
        "Sha": f.sha,
        "ShortSha": f.short_sha,
        "UncommittedChanges": f.uncommitted_changes,
        "VersionSourceDistance": f.version_source_distance,
        "VersionSourceIncrement": f.version_source_increment,
        "VersionSourceSemVer": f.version_source_sem_ver,
        "VersionSourceSha": f.version_source_sha,
        "WeightedPreReleaseNumber": f.weighted_pre_release_number,
    }
    assert tuple(values) == AVAILABLE_VARIABLES  # noqa: S101 -- order contract
    return GitVersionVariables(values)
