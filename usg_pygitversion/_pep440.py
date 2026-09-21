# SPDX-License-Identifier: MIT
"""Map GitVersion output onto a PEP 440 version for the package itself (PLAN.md 8.3).

GitVersion produces SemVer 2.0 strings; Python packaging needs PEP 440.
The mapping is deliberately simple and total: every GitVersion ``SemVer``
becomes a legal, correctly ordered PEP 440 version, and stable releases
map to themselves.

=============================  ==================
GitVersion ``SemVer``          PEP 440
=============================  ==================
``1.2.0``                      ``1.2.0``
``1.2.0-alpha.5``              ``1.2.0a5``
``1.2.0-beta.3``               ``1.2.0b3``
``1.2.0-rc.1``                 ``1.2.0rc1``
``1.2.1-5`` (untagged main)    ``1.2.1.dev5``
``1.2.0-feature-x.4``          ``1.2.0.dev4``
``1.2.0-PullRequest12.1``      ``1.2.0.dev1``
=============================  ==================
"""

from __future__ import annotations

import re

_STABLE = re.compile(r"^(?P<core>\d+\.\d+\.\d+)$")
_PRERELEASE = re.compile(
    r"^(?P<core>\d+\.\d+\.\d+)-(?P<label>[0-9A-Za-z-]*?)(?:\.?(?P<number>\d+))?$"
)
_KNOWN_LABELS = {
    "alpha": "a",
    "a": "a",
    "beta": "b",
    "b": "b",
    "rc": "rc",
    "c": "rc",
    "preview": "rc",
}


def to_pep440(semver: str) -> str:
    """Translate a GitVersion ``SemVer`` string to PEP 440.

    Raises:
        ValueError: If ``semver`` is not ``MAJOR.MINOR.PATCH[-label[.N]]``.
    """
    text = semver.strip()
    if (stable := _STABLE.match(text)) is not None:
        return stable.group("core")
    match = _PRERELEASE.match(text)
    if match is None:
        raise ValueError(f"cannot map {semver!r} to a PEP 440 version")
    core = match.group("core")
    label = (match.group("label") or "").lower()
    number = match.group("number") or "0"
    if label in _KNOWN_LABELS:
        return f"{core}{_KNOWN_LABELS[label]}{int(number)}"
    return f"{core}.dev{int(number)}"
