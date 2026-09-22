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
  nothing and removes the polynomial-backtracking input class.
* Patterns whose structure is exponential in the subject length, an
  unbounded quantifier applied to a group that itself starts with an
  unbounded quantifier such as ``(a+)+`` or ``(?:x*)*``, are rejected at
  compile time by :func:`_reject_nested_quantifiers`. The stdlib ``re``
  engine cannot be interrupted by a signal or a thread while it matches, so
  a timeout is not implementable without a second dependency; a structural
  check is the stdlib-only defence. Bounded subjects and the structural check
  together are what make a hostile ``GitVersion.yml`` unable to hang a build
  (PLAN.md 9.3; SECURITY.md lists ReDoS in scope).

Ports: ``GitVersion.Core/Core/RegexPatterns.cs`` (``Cache.GetOrAdd``) with
the dialect translation that the .NET runtime did not need.
"""

from __future__ import annotations

import re
from functools import lru_cache

# The stdlib pattern parser. Private, but it is what ``re.compile`` itself
# uses and the deprecated public alias ``sre_parse`` is a thin re-export of
# it that warns on import. Only ``parse`` and ``MAXREPEAT`` are used.
from re import _parser as _sre_parser  # type: ignore[attr-defined]
from typing import Any

from usg_pygitversion.errors import ConfigurationError

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
            msg = f"regex uses {what}, which is not supported by usg-pygitversion: {pattern!r}"
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


_UNBOUNDED_REPEAT_OPS = frozenset({_sre_parser.MAX_REPEAT, _sre_parser.MIN_REPEAT})
_REPEAT_OPS = _UNBOUNDED_REPEAT_OPS
_P = _sre_parser  # short alias for the opcode constants below

#: Representative characters per ``\d``/``\s``/``\w`` category, used to probe
#: whether a following element overlaps with a repeated class. Conservative
#: on the side of reporting overlap (a false positive only rejects a config
#: pattern with a clear message; a false negative would allow a hang).
_CATEGORY_SAMPLES: dict[Any, str] = {
    _P.CATEGORY_DIGIT: "5",
    _P.CATEGORY_NOT_DIGIT: "a .",
    _P.CATEGORY_SPACE: " ",
    _P.CATEGORY_NOT_SPACE: "a5.",
    _P.CATEGORY_WORD: "a",
    _P.CATEGORY_NOT_WORD: " .-",
}


def _is_unbounded_repeat(item: tuple[Any, Any]) -> bool:
    """True for ``x*``, ``x+``, ``x{n,}`` and their lazy forms."""
    op, av = item
    return op in _UNBOUNDED_REPEAT_OPS and av[1] == _P.MAXREPEAT


def _is_optional(item: tuple[Any, Any]) -> bool:
    """True for ``x?``, ``x*``, ``x{0,n}`` and zero-width anchors."""
    op, av = item
    return op == _P.AT or (op in _REPEAT_OPS and av[0] == 0)


_CATEGORY_TESTS: dict[Any, Any] = {
    _P.CATEGORY_DIGIT: str.isdigit,
    _P.CATEGORY_NOT_DIGIT: lambda ch: not ch.isdigit(),
    _P.CATEGORY_SPACE: str.isspace,
    _P.CATEGORY_NOT_SPACE: lambda ch: not ch.isspace(),
    _P.CATEGORY_WORD: lambda ch: ch.isalnum() or ch == "_",
    _P.CATEGORY_NOT_WORD: lambda ch: not (ch.isalnum() or ch == "_"),
}


def _category_matches(category: Any, ch: str) -> bool:
    r"""Whether a ``\d``/``\s``/``\w`` category matches ``ch`` (unknown: assume yes)."""
    test = _CATEGORY_TESTS.get(category)
    return True if test is None else bool(test(ch))


def _single_char_matches(item: tuple[Any, Any], ch: str) -> bool | None:
    """Whether a one-character element matches ``ch``; ``None`` if not a simple class.

    Case-insensitive throughout, since every GitVersion pattern is compiled
    with ``IgnoreCase``.
    """
    op, av = item
    variants = {ch, ch.lower(), ch.upper()}
    if op == _P.ANY:
        return ch != "\n"
    if op == _P.LITERAL:
        return chr(av) in variants
    if op == _P.NOT_LITERAL:
        return chr(av) not in variants
    if op == _P.IN:
        negate = bool(av) and av[0][0] == _P.NEGATE
        hit = False
        for sub_op, sub_av in av[1:] if negate else av:
            if sub_op == _P.LITERAL:
                hit = chr(sub_av) in variants
            elif sub_op == _P.RANGE:
                hit = any(sub_av[0] <= ord(v) <= sub_av[1] for v in variants)
            elif sub_op == _P.CATEGORY:
                hit = _category_matches(sub_av, ch)
            else:
                return None  # unusual class member: cannot reason about it
            if hit:
                break
        return not hit if negate else hit
    return None


def _sample_chars(item: tuple[Any, Any]) -> str | None:
    """Characters a mandatory element can start with; ``None`` if not derivable."""
    op, av = item
    if op == _P.LITERAL:
        return chr(av)
    if op == _P.IN:
        chars: list[str] = []
        for sub_op, sub_av in av:
            if sub_op == _P.LITERAL:
                chars.append(chr(sub_av))
            elif sub_op == _P.RANGE:
                chars.extend((chr(sub_av[0]), chr(sub_av[1])))
            elif sub_op == _P.CATEGORY:
                chars.extend(_CATEGORY_SAMPLES.get(sub_av, ""))
            else:
                return None
        return "".join(chars) or None
    return None


def _follow_separates(inner_body: Any, follow: list[Any]) -> bool:  # noqa: PLR0911 -- one branch per node kind
    r"""Whether the element after an inner repeat cannot be consumed by that repeat.

    ``(.+\n)+`` is safe because ``.`` never matches the ``\n`` that must end
    every iteration; ``(a+a)+`` and ``(a+)+`` are not, because the boundary
    between iterations is ambiguous and the engine tries every split.
    """
    if len(inner_body) != 1:
        return False  # multi-element repeat body: too complex, assume overlap
    repeated = inner_body[0]
    if _single_char_matches(repeated, "x") is None:
        return False
    for index, item in enumerate(follow):
        if _is_optional(item):
            continue
        op, av = item
        if op == _P.SUBPATTERN:
            return _follow_separates(inner_body, list(av[3]) + follow[index + 1 :])
        if op in _REPEAT_OPS:  # mandatory repeat: its body comes first
            return _follow_separates(inner_body, list(av[2]) + follow[index + 1 :])
        if op == _P.BRANCH:
            return all(
                _follow_separates(inner_body, list(alt) + follow[index + 1 :]) for alt in av[1]
            )
        samples = _sample_chars(item)
        if samples is None:
            return False
        return not any(_single_char_matches(repeated, ch) for ch in samples)
    return False  # nothing mandatory follows: `(a+)+` shape


def _body_is_ambiguous(items: list[Any]) -> bool:
    """Whether a repeated body can *begin* with an unbounded repeat that is not fenced off.

    Walks the body left to right. Optional elements may be skipped (both
    paths are checked); the first mandatory non-repeat element pins the
    iteration start and ends the search.
    """
    for index, item in enumerate(items):
        op, av = item
        rest = items[index + 1 :]
        if _is_unbounded_repeat(item):
            return not _follow_separates(av[2], rest)
        if op == _P.SUBPATTERN:
            return _body_is_ambiguous(list(av[3]) + rest)
        if op == _P.BRANCH:
            return any(_body_is_ambiguous(list(alt) + rest) for alt in av[1])
        if op in _REPEAT_OPS and av[0] == 0:
            # Bounded optional: taken or skipped.
            if _body_is_ambiguous(list(av[2]) + rest):
                return True
            continue
        if op == _P.AT:
            continue
        return False
    return False


def _find_nested_quantifier(items: Any) -> bool:
    """Depth-first search for an unbounded repeat whose body is ambiguous."""
    for item in items:
        op, av = item
        if op in _REPEAT_OPS:
            body = list(av[2])
            if _is_unbounded_repeat(item) and _body_is_ambiguous(body):
                return True
            if _find_nested_quantifier(body):
                return True
        elif op == _P.SUBPATTERN:
            if _find_nested_quantifier(av[3]):
                return True
        elif op == _P.BRANCH:
            if any(_find_nested_quantifier(alt) for alt in av[1]):
                return True
        elif op in (_P.ASSERT, _P.ASSERT_NOT) and _find_nested_quantifier(av[1]):
            return True
    return False


def _reject_nested_quantifiers(pattern: str, translated: str) -> None:
    r"""Refuse patterns with catastrophic-backtracking structure (SI-10).

    Raises:
        ConfigurationError: Naming the pattern, if an unbounded quantifier is
            applied to a group that itself starts with an unbounded repeat
            whose boundary is ambiguous (``(a+)+``, ``(a+a)+``, ``(\d+\.?)+``).
            Iterations that begin with a fixed element, such as upstream's
            ``(?: into (?<TargetBranch>[^\s]*))*``, or whose inner repeat is
            fenced by a character it cannot match, such as the documented
            conventional-commit pattern's ``(.+\n)+``, are unaffected.
    """
    try:
        parsed = _sre_parser.parse(translated)
    except re.error:
        return  # re.compile reports the syntax error with a better message
    if _find_nested_quantifier(parsed):
        msg = (
            f"regex {pattern!r} nests an unbounded quantifier inside another "
            "(for example '(a+)+'), which can take exponential time; rewrite it so "
            "each repetition starts with, or is ended by, a character the inner "
            "repeat cannot match"
        )
        raise ConfigurationError(msg)


@lru_cache(maxsize=256)
def compile(pattern: str, flags: int = DEFAULT_FLAGS) -> re.Pattern[str]:  # noqa: A001 -- mirrors re.compile
    """Translate and compile a .NET pattern, with a bounded cache.

    Args:
        pattern: Pattern in .NET syntax.
        flags: :mod:`re` flags. Defaults to case-insensitive, matching
            ``RegexOptions.IgnoreCase`` used throughout GitVersion.

    Raises:
        ConfigurationError: On unsupported constructs, a pattern that
            Python's engine rejects, or a pattern with nested unbounded
            quantifiers (catastrophic backtracking). The original .NET
            pattern is quoted so the user can find it in their config; the
            translated form is included so the failure is diagnosable.
    """
    translated = translate(pattern)
    try:
        compiled = re.compile(translated, flags)
    except re.error as exc:
        msg = f"invalid regex {pattern!r} (translated to {translated!r}): {exc}"
        raise ConfigurationError(msg) from exc
    _reject_nested_quantifiers(pattern, translated)
    return compiled


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
