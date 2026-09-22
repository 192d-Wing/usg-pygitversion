# SPDX-License-Identifier: MIT
"""On-disk result cache under ``.git/gitversion_cache``.

Ports ``GitVersionCacheKeyFactory`` and ``GitVersionCacheProvider``. The key
is the SHA-1 of four inputs: the ``refs`` directory contents, the
configuration file, the HEAD snapshot and the override document. SHA-1 is
used only as a cache fingerprint for compatibility with the reference tool's
key format, never for integrity or authentication.

Deviation (``docs/deviations.md``): the snapshot also covers the requested
target branch (``/b`` or the build agent's branch) and commit (``/c``).
Upstream can omit them because it checks the target branch out before
calculating; this port is read-only, so without them a cached HEAD result
would be served for a different branch or commit (SI-7 integrity).

Cache files are written with owner-only permissions (SC-28) and a corrupt
file is deleted rather than trusted (SI-10).
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from usg_pygitversion.calculation.variables import GitVersionVariables
from usg_pygitversion.config.locator import find_configuration_file
from usg_pygitversion.config.yaml_io import dump_mapping
from usg_pygitversion.errors import GitVersionError
from usg_pygitversion.git.repository import GitRepository
from usg_pygitversion.output.serializer import from_json, to_json

_log = logging.getLogger("usg_pygitversion.cache")

CACHE_DIRECTORY_NAME = "gitversion_cache"
#: Bound on the ``refs`` walk so a pathological repository cannot exhaust memory.
MAX_REF_ENTRIES = 100_000


def _sha1(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest().upper()


def _directory_contents(root: Path) -> list[str]:
    """Ports ``CalculateDirectoryContents``: names and file contents, depth first.

    Entries are visited in sorted order so the key is stable across
    filesystems (upstream relies on the OS enumeration order).
    """
    if not root.is_dir():
        raise GitVersionError(f"Root directory does not exist: {root}")
    result: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        result.append(current.name)
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            _log.error("%s", exc)
            continue
        subdirs = [e for e in entries if e.is_dir()]
        for entry in entries:
            if not entry.is_file():
                continue
            try:
                result.append(entry.name)
                result.append(entry.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                _log.error("%s", exc)
            if len(result) > MAX_REF_ENTRIES:
                raise GitVersionError("too many entries under .git/refs to fingerprint")
        stack.extend(reversed(subdirs))
    return result


def cache_key(
    repository: GitRepository,
    working_directory: Path,
    override_document: Mapping[str, Any] | None,
    explicit_config_file: str | None = None,
    *,
    target_branch: str | None = None,
    commit_id: str | None = None,
) -> str:
    """Ports ``GitVersionCacheKeyFactory.Create``.

    Args:
        repository: The open repository.
        working_directory: Where the configuration file is looked for first.
        override_document: ``/overrideconfig`` values, if any.
        explicit_config_file: ``/config`` path, if any.
        target_branch: The branch the calculation is for when it is not
            ``HEAD`` (``/b``, ``GITVERSION_BRANCH`` or a build agent).
        commit_id: The commit the calculation is for when it is not the
            branch tip (``/c``).
    """
    git_system = _sha1(":".join(_directory_contents(repository.git_dir / "refs")))
    config_path = find_configuration_file(working_directory, explicit_config_file)
    if config_path is None:
        config_path = find_configuration_file(repository.working_tree, explicit_config_file)
    config_hash = _sha1(config_path.read_text(encoding="utf-8")) if config_path else ""
    head = repository.head()
    snapshot = _sha1(f"{head.name.canonical}:{head.tip}") if head.tip else head.name.canonical
    # Upstream's key stops at HEAD. Fold in the requested branch and commit
    # so that "/b other" or "/c <sha>" never reuse a result computed for HEAD.
    if target_branch or commit_id:
        snapshot = _sha1(f"{snapshot}:{target_branch or ''}:{commit_id or ''}")
    override_hash = _sha1(dump_mapping(dict(override_document))) if override_document else ""
    return _sha1(":".join([git_system, config_hash, snapshot, override_hash]))


class CacheProvider:
    """Reads and writes cached variables for one repository."""

    def __init__(self, repository: GitRepository) -> None:
        """Bind to a repository; the cache lives inside its ``.git`` directory."""
        self.repository = repository

    @property
    def directory(self) -> Path:
        """``<git-dir>/gitversion_cache``."""
        return self.repository.git_dir / CACHE_DIRECTORY_NAME

    def path_for(self, key: str) -> Path:
        """Cache file for ``key`` (directory created on demand)."""
        self.directory.mkdir(mode=0o700, exist_ok=True)
        return self.directory / key

    def load(self, key: str) -> GitVersionVariables | None:
        """Ports ``LoadVersionVariablesFromDiskCache``; corrupt files are removed."""
        path = self.path_for(key)
        _log.info("Loading version variables from disk cache file %s", path)
        if not path.is_file():
            _log.info("Cache file %s not found.", path)
            return None
        try:
            return from_json(path.read_text(encoding="utf-8"))
        except (OSError, GitVersionError) as exc:
            _log.warning("Unable to read cache file %s, deleting it.", path)
            _log.info("%s", exc)
            try:
                path.unlink()
            except OSError as delete_exc:
                _log.warning(
                    "Unable to delete corrupted version cache file %s: %s", path, delete_exc
                )
            return None

    def save(self, key: str, variables: GitVersionVariables) -> None:
        """Ports ``WriteVariablesToDiskCache``; failures are logged, never fatal."""
        path = self.path_for(key)
        _log.info("Write version variables to cache file %s", path)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(to_json(variables))
        except OSError as exc:
            _log.error("Unable to write cache file %s. Got %s.", path, type(exc).__name__)
