# SPDX-License-Identifier: MIT
"""Merge-commit message parsing and version-in-branch-name extraction.

Ports ``MergeMessage`` and ``ReferenceNameExtensions.TryGetSemanticVersion``
from 6.8.2. The eight built-in merge formats are the upstream patterns,
translated through the .NET regex shim; user ``merge-message-formats`` are
tried first, in configuration order.
"""

from __future__ import annotations

from dataclasses import dataclass

from usg_pygitversion.config.effective import is_release_branch
from usg_pygitversion.config.schema import GitVersionConfiguration
from usg_pygitversion.dotnet import regex as dotnet_regex
from usg_pygitversion.git.models import Commit
from usg_pygitversion.git.refname import REMOTE_TRACKING_BRANCH_PREFIX, ReferenceName
from usg_pygitversion.semver import SemanticVersion, SemanticVersionFormat

DEFAULT_VERSION_IN_BRANCH_PATTERN = r"(?<version>[vV]?\d+(\.\d+)?(\.\d+)?).*"

#: Upstream ``RegexPatterns.MergeMessage`` in ``DefaultFormats`` order.
DEFAULT_FORMATS: tuple[tuple[str, str], ...] = (
    ("Default", r"^Merge (branch|tag) '(?<SourceBranch>[^']*)'(?: into (?<TargetBranch>[^\s]*))*"),
    ("SmartGit", r"^Finish (?<SourceBranch>[^\s]*)(?: into (?<TargetBranch>[^\s]*))*"),
    (
        "BitBucketPull",
        (
            r"^Merge pull request #(?<PullRequestNumber>\d+) (from|in) (?<Source>.*) from "
            r"(?<SourceBranch>[^\s]*) to (?<TargetBranch>[^\s]*)"
        ),
    ),
    (
        "BitBucketPullv7",
        (
            r"^Pull request #(?<PullRequestNumber>\d+).*\r?\n\r?\nMerge in (?<Source>.*) from "
            r"(?<SourceBranch>[^\s]*) to (?<TargetBranch>[^\s]*)"
        ),
    ),
    (
        "BitBucketCloudPull",
        r"^Merged in (?<SourceBranch>[^\s]*) \(pull request #(?<PullRequestNumber>\d+)\)",
    ),
    (
        "GitHubPull",
        (
            r"^Merge pull request #(?<PullRequestNumber>\d+) (from|in) (?:[^\s\/]+\/)?"
            r"(?<SourceBranch>[^\s]*)(?: into (?<TargetBranch>[^\s]*))*"
        ),
    ),
    (
        "RemoteTracking",
        (
            r"^Merge remote-tracking branch '(?<SourceBranch>[^\s]*)'"
            r"(?: into (?<TargetBranch>[^\s]*))*"
        ),
    ),
    (
        "AzureDevOpsPull",
        (
            r"^Merge pull request (?<PullRequestNumber>\d+) from (?<SourceBranch>[^\s]*) "
            r"into (?<TargetBranch>[^\s]*)"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SemanticVersionResult:
    """Version found in a branch name plus the remaining name (``feature/1.0-foo`` -> ``foo``)."""

    value: SemanticVersion
    name: str | None


def try_get_semantic_version(
    branch_name: ReferenceName,
    version_in_branch_pattern: str | None,
    tag_prefix: str | None,
    fmt: SemanticVersionFormat,
) -> SemanticVersionResult | None:
    """Ports ``ReferenceName.TryGetSemanticVersion``.

    The branch name (without ``origin/``) is split on ``/`` when it contains
    one, otherwise on ``-``; the first part that matches the pattern and
    parses wins. The remainder of the name after the version, trimmed of
    ``-``, becomes ``name``.
    """
    pattern = version_in_branch_pattern or DEFAULT_VERSION_IN_BRANCH_PATTERN
    regex = dotnet_regex.compile("^" + pattern.lstrip("^"))
    text = branch_name.without_origin
    separator = "/" if ("/" in text or "-" not in text) else "-"
    length = 0
    for part in text.split(separator):
        if not part:
            return None
        match = regex.search(dotnet_regex.bounded(part))
        if match is not None:
            version_part = match.group("version")
            version = SemanticVersion.try_parse(version_part, tag_prefix, fmt)
            if version is not None:
                length += len(version_part)
                name = text[length:].strip("-")
                return SemanticVersionResult(version, name or None)
        length += len(part) + 1
    return None


@dataclass(frozen=True, slots=True)
class MergeMessage:
    """Parsed merge message. Ports ``MergeMessage``."""

    format_name: str | None = None
    target_branch: str | None = None
    merged_branch: ReferenceName | None = None
    pull_request_number: int | None = None
    version: SemanticVersion | None = None

    @property
    def is_merged_pull_request(self) -> bool:
        """True when a pull-request number was parsed."""
        return self.pull_request_number is not None

    @classmethod
    def parse(cls, message: str, configuration: GitVersionConfiguration) -> MergeMessage:
        """Try user formats then the defaults; the first match wins."""
        if not message:
            return cls()
        formats = [*configuration.merge_message_formats.items(), *DEFAULT_FORMATS]
        for name, pattern in formats:
            match = dotnet_regex.compile(pattern).search(dotnet_regex.bounded(message))
            if match is None:
                continue
            groups = match.groupdict()
            source = groups.get("SourceBranch") or ""
            if name == "RemoteTracking" and not source.startswith(REMOTE_TRACKING_BRANCH_PREFIX):
                source = REMOTE_TRACKING_BRANCH_PREFIX + source
            merged = ReferenceName.from_branch_name(source)
            target = groups.get("TargetBranch")
            pr_text = groups.get("PullRequestNumber")
            pr_number = int(pr_text) if pr_text and pr_text.isdigit() else None
            found = try_get_semantic_version(
                merged,
                configuration.version_in_branch_pattern,
                configuration.tag_prefix,
                configuration.semantic_version_format,
            )
            return cls(
                format_name=name,
                target_branch=target or None,
                merged_branch=merged,
                pull_request_number=pr_number,
                version=found.value if found else None,
            )
        return cls()

    @classmethod
    def try_parse(
        cls, commit: Commit, configuration: GitVersionConfiguration
    ) -> MergeMessage | None:
        """Ports ``MergeMessage.TryParse``: a merge commit, or a message naming a release branch."""
        merged = cls.parse(commit.message, configuration).merged_branch
        is_release = merged is not None and is_release_branch(configuration, merged)
        if commit.is_merge or is_release:
            return cls.parse(commit.message, configuration)
        return None
