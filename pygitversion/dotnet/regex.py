# SPDX-License-Identifier: MIT
r"""Translate .NET regular expressions to Python :mod:`re` patterns.

GitVersion configuration (``tag-prefix``, branch ``regex``, bump-message
patterns, ``version-in-branch-pattern``, ``ignore.paths``) is written in the
.NET dialect. This module rewrites the constructs that differ and refuses,
with a precise message, the few that Python cannot express. The goal is that
a ``GitVersion.yml`` that works with the .NET tool works here too, and one
that cannot work fails loudly rather than silently matching differently.

Translation table:

==========================  =============================  ==================
.NET                        Python                         Notes
==========================  =============================  ==================
``(?<name>...)``            ``(?P<name>...)``              lookbehind ``(?<=`` / ``(?<!`` untouched
``(?'name'...)``            ``(?P<name>...)``
``\\k<name>`` / ``\\k'name'``  ``(?P=name)``
``\\z``                      ``\\Z``                         end of string
``\\Z``                      ``(?=\\n?\\Z)``                  end or before final newline
``(?n)`` explicit capture   rejected
``(?<a-b>...)`` balancing   rejected
``\\p{..}`` unicode classes  rejected                       stdlib ``re`` has none
==========================  =============================  ==================

Security (NIST SP 800-53 SI-10, and the ReDoS guidance in PLAN.md 9.3):

* Patterns are capped at :data:`MAX_PATTERN_LENGTH` characters.
* Compiled patterns are cached with a bounded LRU so hostile configs cannot
  grow memory without limit.
* Subject strings should be bounded by callers with :func:`bounded`; branch
  names, tag names and commit subjects are short, so a small cap costs
  nothing and removes the catastrophic-backtracking input class.

Ports: ``GitVersion.Core/Core/RegexPatterns.cs`` (``Cache.GetOrAdd``) with
the dialect translation that the .NET runtime did not need.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pygitversion.errors import ConfigurationError

#: Upper bound on a user-supplied pattern. Real GitVersion configs are well
#: under 200 characters; the cap is generous but finite.
MAX_PATTERN_LENGTH = 1024

#: Default subject cap used by :func:`bounded`. Git ref names are limited by
#: the filesystem (typically 255 bytes per component); commit subjects are
#: conventionally under 100 characters. 4 KiB is generous.
MAX_SUBJECT_LENGTH = 4096

#: GitVersion compiles every pattern with ``RegexOptions.IgnoreCase``.
DEFAULT_FLAGS = re.IGNORECASE

# Ordered rewrite rules. Each is (compiled matcher, replacement). Order
# matters: reject rules run before rewrite rules so an unsupported construct
# is reported rather than mangled.
_REJECT: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\(\?<[A-Za-z_]\w*-[A-Za-z_]\w*>"), "balancing groups ((?<a-b>...))"),
    (re.compile(r"\(\?<-[A-Za-z_]\w*>"), "balancing groups ((?<-name>...))"),
    (re.compile(r"\(\?[imsx]*n[imsx]*[:)]"), "the (?n) explicit-capture option"),
    (re.compile(r"\\[pP]\{"), r"unicode categories (\p{...})"),
)
_REWRITE: tuple[tuple[re.Pattern[str], str], ...] = (
    # (?<name>  -> (?P<name>   but not (?<= or (?<!
    (re.compile(r"\(\?<(?![=!])([A-Za-z_]\w*)>"), r"(?P<\1>"),
    # (?'name'  -> (?P<name>
    (re.compile(r"\(\?'([A-Za-z_]\w*)'"), r"(?P<\1>"),
    # \k<name> and \k'name' -> (?P=name)
    (re.compile(r"\\k<([A-Za-z_]\w*)>"), r"(?P=\1)"),
    (re.compile(r"\\k'([A-Za-z_]\w*)'"), r"(?P=\1)"),
)
# Anchors differ: .NET \z is absolute end (Python \Z); .NET \Z is end or
# before a final newline (Python has no single escape for that).
_DOTNET_SMALL_Z = re.compile(r"(?<!\\)\\z")
_DOTNET_BIG_Z = re.compile(r"(?<!\\)\\Z")


def translate(pattern: str) -> str:
    """Rewrite a .NET pattern into Python syntax without compiling it.

    Args:
        pattern: Pattern in .NET syntax.

    Returns:
        Equivalent pattern in Python :mod:`re` syntax.

    Raises:
        ConfigurationError: If the pattern is too long or uses a construct
            Python cannot express. The message names the construct.
    """
    if len(pattern) > MAX_PATTERN_LENGTH:
        msg = f"regex pattern is {len(pattern)} characters; the limit is {MAX_PATTERN_LENGTH}"
        raise ConfigurationError(msg)
    for matcher, what in _REJECT:
        if matcher.search(pattern):
            msg = f"regex uses {what}, which is not supported by pygitversion: {pattern!r}"
            raise ConfigurationError(msg)

    # Protect \z from being seen as \Z by the .NET-\Z rule: translate \z first
    # into a placeholder, apply the \Z rule, then restore.
    placeholder = "\x00ABSEND\x00"
    out = _DOTNET_SMALL_Z.sub(placeholder, pattern)
    out = _DOTNET_BIG_Z.sub(r"(?=\\n?\\Z)", out)
    out = out.replace(placeholder, r"\Z")
    for matcher, replacement in _REWRITE:
        out = matcher.sub(replacement, out)
    return out


@lru_cache(maxsize=256)
def compile(pattern: str, flags: int = DEFAULT_FLAGS) -> re.Pattern[str]:  # noqa: A001 -- mirrors re.compile
    """Translate and compile a .NET pattern, with a bounded cache.

    Args:
        pattern: Pattern in .NET syntax.
        flags: :mod:`re` flags. Defaults to case-insensitive, matching
            ``RegexOptions.IgnoreCase`` used throughout GitVersion.

    Raises:
        ConfigurationError: On unsupported constructs or a pattern that
            Python's engine rejects. The original .NET pattern is quoted so
            the user can find it in their config; the translated form is
            included so the failure is diagnosable.
    """
    translated = translate(pattern)
    try:
        return re.compile(translated, flags)
    except re.error as exc:
        msg = f"invalid regex {pattern!r} (translated to {translated!r}): {exc}"
        raise ConfigurationError(msg) from exc


def bounded(subject: str, limit: int = MAX_SUBJECT_LENGTH) -> str:
    """Truncate ``subject`` to ``limit`` characters before matching.

    Callers apply this to untrusted repository content (branch names, commit
    messages) so that a pathological user pattern cannot be driven into
    catastrophic backtracking by a long input. Truncation is deliberate and
    documented: no legitimate GitVersion pattern needs to see more than the
    first few kilobytes of a commit message.
    """
    return subject if len(subject) <= limit else subject[:limit]


def cache_clear() -> None:
    """Drop all cached compiled patterns (used by tests)."""
    compile.cache_clear()
