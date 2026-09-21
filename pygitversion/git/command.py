"""The single sanctioned subprocess call site for running ``git``.

Hardening, mapped to PLAN.md 9.3 and NIST SP 800-53:

* **Argument lists only, never a shell** (SI-16). Repository content such
  as branch names is passed as discrete argv entries and cannot be
  interpreted by a shell.
* **Minimal, explicit environment** (CM-7). Only ``PATH``, ``HOME`` (so the
  user's ``safe.directory`` and credential-free settings still apply), the
  platform variables a process needs, and a fixed ``LC_ALL=C`` so output is
  stable. ``GIT_TERMINAL_PROMPT=0`` guarantees git never blocks on input.
* **Hooks disabled and no optional locks** (AC-6). ``-c core.hooksPath``
  points at the null device so a hostile repository cannot run code through
  us; ``GIT_OPTIONAL_LOCKS=0`` stops git from writing index locks during
  read-only queries.
* **Timeouts and cleanup** (9.4). Every invocation has a timeout; children
  are killed and reaped on timeout or error, so no zombies remain.
* **Streaming** (9.4). :meth:`GitCommand.stream` yields lines as they are
  produced and terminates the child early when the consumer stops.

Ports the role of ``GitVersion.LibGit2Sharp`` / ``GitVersion.Git.Managed``
as a subprocess-backed equivalent.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path

from pygitversion.errors import GitCommandError, RepositoryError

_log = logging.getLogger("pygitversion.git")

#: Default timeout for one git invocation. Version calculation on a very
#: large repository can legitimately take a while; 120 s is generous.
DEFAULT_TIMEOUT_SECONDS = 120.0

#: stderr is captured for error messages but capped so a runaway child
#: cannot fill memory (9.4).
_STDERR_CAP = 16 * 1024


def _find_git() -> str:
    """Locate the git executable once.

    Raises:
        RepositoryError: If no ``git`` is on ``PATH``.
    """
    found = shutil.which("git")
    if found is None:
        msg = "git executable not found on PATH; pygitversion requires git >= 2.20"
        raise RepositoryError(msg)
    return found


def _base_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build the minimal environment passed to every git child process."""
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        # Pager/editor must never be spawned by a non-interactive tool.
        "GIT_PAGER": "cat",
        "GIT_EDITOR": ":",
    }
    # HOME is needed for the user's global config (safe.directory etc.).
    for name in ("HOME", "USERPROFILE", "SYSTEMROOT", "TMP", "TEMP", "TMPDIR"):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    # Allow git's own tracing/ssl variables through when the user set them;
    # nothing else from the caller's environment is inherited.
    env.update(
        {
            name: value
            for name, value in os.environ.items()
            if name.startswith(("GIT_SSL_", "GIT_TRACE", "GIT_CONFIG_"))
        }
    )
    if extra:
        env.update(extra)
    return env


class GitCommand:
    """Runs ``git`` in a fixed working directory with hardened defaults.

    Args:
        cwd: Directory to run in. Must exist.
        timeout: Per-invocation timeout in seconds.
        git_executable: Override the discovered binary (tests).
    """

    #: Global options prepended to every invocation.
    _GLOBAL_OPTIONS: tuple[str, ...] = (
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "log.showSignature=false",
        "--no-optional-locks",
    )

    def __init__(
        self,
        cwd: Path,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        git_executable: str | None = None,
    ) -> None:
        """Bind the wrapper to ``cwd``."""
        self.cwd = Path(cwd)
        self.timeout = timeout
        self.executable = git_executable or _find_git()

    def _argv(self, args: tuple[str, ...]) -> list[str]:
        return [self.executable, *self._GLOBAL_OPTIONS, *args]

    def run(self, *args: str, check: bool = True) -> str:
        """Run git and return its standard output.

        Suitable for commands with bounded output (``rev-parse``,
        ``for-each-ref``, ``merge-base``). For unbounded output use
        :meth:`stream`.

        Args:
            *args: Arguments after ``git``.
            check: Raise :class:`GitCommandError` on non-zero exit.

        Returns:
            Standard output, decoded as UTF-8 with replacement, trailing
            newline stripped.

        Raises:
            GitCommandError: On non-zero exit (when ``check``) or timeout.
        """
        argv = self._argv(args)
        _log.debug("git %s", " ".join(args))
        try:
            completed = subprocess.run(  # noqa: S603 -- sole sanctioned call site; argv list, no shell
                argv,
                cwd=self.cwd,
                env=_base_environment(),
                capture_output=True,
                timeout=self.timeout,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = (exc.stderr or b"")[:_STDERR_CAP].decode("utf-8", "replace")
            raise GitCommandError(list(args), None, stderr) from exc
        except OSError as exc:
            raise GitCommandError(list(args), None, str(exc)) from exc

        if check and completed.returncode != 0:
            stderr = completed.stderr[:_STDERR_CAP].decode("utf-8", "replace")
            raise GitCommandError(list(args), completed.returncode, stderr)
        return completed.stdout.decode("utf-8", "replace").rstrip("\n")

    def stream(self, *args: str) -> Iterator[str]:
        """Run git and yield stdout lines as they arrive.

        The child is terminated when the generator is closed or garbage
        collected before exhaustion, so callers may ``break`` early without
        leaking a process. A non-zero exit after full consumption raises.

        Args:
            *args: Arguments after ``git``.

        Yields:
            Lines without their trailing newline.

        Raises:
            GitCommandError: If git exits non-zero or the timeout elapses.
        """
        argv = self._argv(args)
        _log.debug("git %s (streaming)", " ".join(args))
        with subprocess.Popen(  # noqa: S603 -- sole sanctioned call site; argv list, no shell
            argv,
            cwd=self.cwd,
            env=_base_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        ) as proc:
            assert proc.stdout is not None  # noqa: S101 -- Popen contract with PIPE
            try:
                for raw in proc.stdout:
                    yield raw.decode("utf-8", "replace").rstrip("\r\n")
            finally:
                # Consumer stopped early or we are done: close the pipe first
                # so git sees EPIPE and exits promptly, then reap it.
                with contextlib.suppress(OSError):
                    proc.stdout.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            # Full consumption path: report failures.
            returncode = proc.wait(timeout=self.timeout)
            if returncode != 0:
                stderr_bytes = proc.stderr.read(_STDERR_CAP) if proc.stderr else b""
                raise GitCommandError(
                    list(args), returncode, stderr_bytes.decode("utf-8", "replace")
                )
