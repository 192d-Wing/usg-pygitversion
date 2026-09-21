# SPDX-License-Identifier: MIT
"""Compiled regular expressions for semantic-version parsing.

These are the upstream patterns from ``RegexPatterns.SemanticVersion``
rewritten into Python syntax by hand (named groups ``(?P<...>)``). They are
internal and fixed, so they do not go through the .NET translation shim;
user-supplied patterns do. All are compiled case-insensitively to match
``RegexOptions.IgnoreCase``.
"""

from __future__ import annotations

import re

#: SemVer 2.0 grammar. Ports ``ParseStrictRegexPattern``.
STRICT = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$",
    re.IGNORECASE,
)

#: Lenient grammar: 1..4 numeric parts, leading zeros, any tag text.
#: Ports ``ParseLooseRegexPattern``.
LOOSE = re.compile(
    r"^(?P<SemVer>(?P<Major>\d+)(\.(?P<Minor>\d+))?(\.(?P<Patch>\d+))?)"
    r"(\.(?P<FourthPart>\d+))?(-(?P<Tag>[^\+]*))?(\+(?P<BuildMetaData>.*))?$",
    re.IGNORECASE,
)

#: ``4.Branch.main.Sha.abc.other``. Ports ``ParseBuildMetaDataRegexPattern``.
BUILD_METADATA = re.compile(
    r"(?P<BuildNumber>\d+)?(\.?Branch(Name)?\.(?P<BranchName>[^\.]+))?"
    r"(\.?Sha?\.(?P<Sha>[^\.]+))?(?P<Other>.*)",
    re.IGNORECASE,
)

#: Characters not allowed in build metadata parts; replaced with ``-``.
#: Ports ``FormatBuildMetaDataRegexPattern``.
FORMAT_BUILD_METADATA = re.compile(r"[^0-9A-Za-z-.]")

#: ``beta.3`` / ``beta3`` / ``3`` -> name + optional number.
#: Ports ``ParsePreReleaseTagRegexPattern``.
PRERELEASE_TAG = re.compile(r"(?P<name>.*?)\.?(?P<number>\d+)?$", re.IGNORECASE)
