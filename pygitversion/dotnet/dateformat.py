# SPDX-License-Identifier: MIT
r"""Format datetimes with .NET custom format strings.

GitVersion's ``commit-date-format`` (default ``yyyy-MM-dd``) is a .NET
*custom* date and time format string, formatted with ``DateTimeOffset``
under the invariant culture. This module implements the token set that
grammar defines so users keep their existing configuration.

Supported specifiers (invariant culture):

``d dd ddd dddd  M MM MMM MMMM  y yy yyy yyyy yyyyy  H HH h hh  m mm  s ss
f..fffffff F..FFFFFFF  t tt  z zz zzz  K  : /  'literal' "literal" \\x``

Ports: the behaviour of ``DateTimeOffset.ToString(string, CultureInfo.InvariantCulture)``
as used by ``SemanticVersionFormatValues.CommitDate``.
"""

from __future__ import annotations

from datetime import datetime

from pygitversion.errors import ConfigurationError

_DAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DAY_FULL = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)  # fmt: skip
_MONTH_FULL = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)  # fmt: skip

#: Characters that can start a repeated specifier run.
_SPECIFIERS = frozenset("dMyHhmsfFtzK")

#: Maximum accepted format-string length (SI-10 input bound).
MAX_FORMAT_LENGTH = 256


def _offset_parts(value: datetime) -> tuple[str, int, int]:
    """Return (sign, hours, minutes) of the UTC offset; naive means UTC."""
    offset = value.utcoffset()
    total = int(offset.total_seconds()) if offset is not None else 0
    sign = "-" if total < 0 else "+"
    total = abs(total)
    return sign, total // 3600, (total % 3600) // 60


def _render(spec: str, count: int, value: datetime) -> str:  # noqa: PLR0911, PLR0912 -- one branch per specifier
    """Render one specifier run such as ``yyyy`` or ``ff``."""
    if spec == "d":
        if count == 1:
            return str(value.day)
        if count == 2:  # noqa: PLR2004
            return f"{value.day:02d}"
        if count == 3:  # noqa: PLR2004
            return _DAY_ABBR[value.weekday()]
        return _DAY_FULL[value.weekday()]
    if spec == "M":
        if count == 1:
            return str(value.month)
        if count == 2:  # noqa: PLR2004
            return f"{value.month:02d}"
        if count == 3:  # noqa: PLR2004
            return _MONTH_ABBR[value.month - 1]
        return _MONTH_FULL[value.month - 1]
    if spec == "y":
        if count == 1:
            return str(value.year % 100)
        if count == 2:  # noqa: PLR2004
            return f"{value.year % 100:02d}"
        return f"{value.year:0{count}d}"
    if spec == "H":
        return str(value.hour) if count == 1 else f"{value.hour:02d}"
    if spec == "h":
        hour12 = value.hour % 12 or 12
        return str(hour12) if count == 1 else f"{hour12:02d}"
    if spec == "m":
        return str(value.minute) if count == 1 else f"{value.minute:02d}"
    if spec == "s":
        return str(value.second) if count == 1 else f"{value.second:02d}"
    if spec in "fF":
        digits = f"{value.microsecond:06d}0"[: min(count, 7)]
        return digits.rstrip("0") if spec == "F" else digits
    if spec == "t":
        meridiem = "AM" if value.hour < 12 else "PM"  # noqa: PLR2004
        return meridiem[:1] if count == 1 else meridiem
    if spec == "z":
        sign, hours, minutes = _offset_parts(value)
        if count == 1:
            return f"{sign}{hours}"
        if count == 2:  # noqa: PLR2004
            return f"{sign}{hours:02d}"
        return f"{sign}{hours:02d}:{minutes:02d}"
    # spec == "K": kind. For an offset-aware value .NET emits the offset;
    # for UTC it emits "Z"; naive emits nothing.
    if value.tzinfo is None:
        return ""
    sign, hours, minutes = _offset_parts(value)
    if hours == 0 and minutes == 0:
        return "Z"
    return f"{sign}{hours:02d}:{minutes:02d}"


def format_datetime(value: datetime, fmt: str) -> str:
    """Format ``value`` using a .NET custom format string.

    Args:
        value: The datetime. Timezone-aware values render offsets from their
            ``tzinfo``; naive values are treated as UTC.
        fmt: .NET custom date/time format, e.g. ``yyyy-MM-dd``.

    Returns:
        The formatted string.

    Raises:
        ConfigurationError: If ``fmt`` is empty, too long, or has an
            unterminated quoted literal.
    """
    if not fmt:
        raise ConfigurationError("commit-date-format must not be empty")
    if len(fmt) > MAX_FORMAT_LENGTH:
        msg = f"commit-date-format is {len(fmt)} characters; the limit is {MAX_FORMAT_LENGTH}"
        raise ConfigurationError(msg)

    out: list[str] = []
    i = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch in _SPECIFIERS:
            j = i
            while j < n and fmt[j] == ch:
                j += 1
            out.append(_render(ch, j - i, value))
            i = j
        elif ch in "'\"":
            end = fmt.find(ch, i + 1)
            if end < 0:
                msg = f"unterminated quoted literal in commit-date-format {fmt!r}"
                raise ConfigurationError(msg)
            out.append(fmt[i + 1 : end])
            i = end + 1
        elif ch == "\\":
            if i + 1 >= n:
                msg = f"trailing backslash in commit-date-format {fmt!r}"
                raise ConfigurationError(msg)
            out.append(fmt[i + 1])
            i += 2
        elif ch == ":":
            out.append(":")  # invariant culture time separator
            i += 1
        elif ch == "/":
            out.append("/")  # invariant culture date separator
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)
