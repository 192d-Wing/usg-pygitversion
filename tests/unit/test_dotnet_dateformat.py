# SPDX-License-Identifier: MIT
"""Tests for the .NET custom date-format engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pygitversion.dotnet.dateformat import format_datetime
from pygitversion.errors import ConfigurationError

_DT = datetime(2024, 3, 7, 14, 5, 9, 123456, tzinfo=timezone(timedelta(hours=-5, minutes=-30)))


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("yyyy-MM-dd", "2024-03-07"),  # GitVersion default
        ("yy-M-d", "24-3-7"),
        ("yyyy-MM-ddTHH:mm:ss", "2024-03-07T14:05:09"),
        ("h:mm tt", "2:05 PM"),
        ("H t", "14 P"),
        ("ddd dddd", "Thu Thursday"),
        ("MMM MMMM", "Mar March"),
        ("s.fff", "9.123"),
        ("s.FFFFFF", "9.123456"),
        ("s.FFFFFFF", "9.123456"),  # trailing zero trimmed
        ("s.fffffff", "9.1234560"),
        ("z zz zzz", "-5 -05 -05:30"),
        ("K", "-05:30"),
        ("yyyy-MM-dd'T'HH:mm:ssK", "2024-03-07T14:05:09-05:30"),
        ('"Year:" yyyy', "Year: 2024"),
        (r"yyyy\-MM", "2024-03"),
        ("MM/dd/yyyy", "03/07/2024"),
    ],
)
def test_format(fmt: str, expected: str) -> None:
    assert format_datetime(_DT, fmt) == expected


def test_utc_kind_and_naive() -> None:
    assert format_datetime(datetime(2024, 1, 1, tzinfo=UTC), "K") == "Z"
    assert format_datetime(datetime(2024, 1, 1), "K") == ""
    assert format_datetime(datetime(2024, 1, 1), "zzz") == "+00:00"


def test_midnight_and_noon_12_hour_clock() -> None:
    assert format_datetime(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), "h tt") == "12 AM"
    assert format_datetime(datetime(2024, 1, 1, 12, 0, tzinfo=UTC), "h tt") == "12 PM"


@pytest.mark.parametrize("bad", ["", "'unterminated", "yyyy\\", "y" * 300])
def test_invalid_formats(bad: str) -> None:
    with pytest.raises(ConfigurationError):
        format_datetime(_DT, bad)
