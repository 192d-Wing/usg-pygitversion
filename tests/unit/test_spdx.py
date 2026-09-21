# SPDX-License-Identifier: MIT
"""Every tracked source, config and documentation file carries an SPDX tag.

Standing project rule (see CONTRIBUTING.md). The check runs over ``git
ls-files`` so new files cannot be added without a header.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TAG = "SPDX-License-Identifier: MIT"
ROOT = Path(__file__).resolve().parents[2]
CHECKED_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".md"}
EXEMPT = {"LICENSE", "uv.lock"}


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30
    ).stdout
    return [ROOT / name for name in out.split("\0") if name]


def test_all_tracked_files_have_spdx_header() -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in _tracked_files()
        if path.suffix in CHECKED_SUFFIXES
        and path.name not in EXEMPT
        and TAG not in path.read_text(encoding="utf-8").splitlines()[0]
    ]
    assert not missing, "files without an SPDX header on line 1:\n" + "\n".join(missing)
