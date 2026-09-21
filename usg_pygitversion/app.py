# SPDX-License-Identifier: MIT
"""The executable flow behind the CLI. Ports ``GitVersionExecutor``/``GitVersionCalculateTool``.

Sequence: initialise logging, honour ``/showconfig``, otherwise discover the
repository, resolve the build agent and the branch it reports, consult the
cache, calculate, write outputs. Everything the reference tool does to the
repository during "normalisation" (creating local branches, fetching) is
deliberately not ported; the agent's branch is resolved read-only
(``docs/deviations.md``).
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from usg_pygitversion import _logging
from usg_pygitversion.__about__ import __version__
from usg_pygitversion.buildagents.base import BuildAgent, LocalBuild, Writer, resolve
from usg_pygitversion.cache import CacheProvider, cache_key
from usg_pygitversion.calculation.api import calculate_variables
from usg_pygitversion.calculation.variables import GitVersionVariables
from usg_pygitversion.cli.arguments import Arguments, OutputType, environment_overrides
from usg_pygitversion.config.locator import verify_unambiguous
from usg_pygitversion.config.provider import provide
from usg_pygitversion.config.yaml_io import dump_mapping
from usg_pygitversion.errors import GitVersionError, RepositoryError
from usg_pygitversion.git.repository import GitRepository
from usg_pygitversion.output.generator import write_outputs

_log = logging.getLogger("usg_pygitversion")


def _stdout_writer(line: str) -> None:
    sys.stdout.write(line + "\n")


def run(
    arguments: Arguments,
    environment: Mapping[str, str] | None = None,
    writer: Writer = _stdout_writer,
) -> int:
    """Execute one invocation and return the process exit code."""
    env: Mapping[str, str] = dict(os.environ) if environment is None else environment
    arguments = environment_overrides(arguments, env)
    if arguments.is_help or arguments.is_version:
        return 0
    if arguments.diag:
        arguments.no_cache = True
    console_log = OutputType.BUILDSERVER in arguments.output or arguments.log_file_path == "console"
    log_file = (
        Path(arguments.log_file_path)
        if arguments.log_file_path and arguments.log_file_path != "console"
        else None
    )
    _logging.configure(arguments.verbosity, log_file, console=console_log)
    try:
        return _run_configured(arguments, env, writer)
    finally:
        # Release the log file and the stdout handler bound to this invocation.
        _logging.shutdown()


def _run_configured(arguments: Arguments, env: Mapping[str, str], writer: Writer) -> int:
    """The body of :func:`run` once logging is configured."""
    working_directory = arguments.working_directory
    if not working_directory.is_dir():
        _log.warning("The working directory '%s' does not exist.", working_directory)
    else:
        _log.info("Working directory: %s", working_directory)

    try:
        if arguments.show_configuration:
            _show_configuration(arguments, working_directory, writer)
            return 0
        _run_tool(arguments, working_directory, env, writer)
    except GitVersionError as exc:
        # The message goes to stderr exactly once; the log (file/console
        # appenders) records it at info level so it is not duplicated there.
        _log.info("An error occurred:\n%s", exc)
        sys.stderr.write(f"An error occurred:\n{exc}\n")
        return 1
    return 0


def _show_configuration(arguments: Arguments, working_directory: Path, writer: Writer) -> None:
    """Ports ``VerifyAndDisplayConfiguration``: prints the effective YAML plus a blank line."""
    project_root = _project_root(working_directory)
    if project_root is not None:
        verify_unambiguous(working_directory, project_root, arguments.configuration_file)
    configuration = provide(
        working_directory, project_root, explicit_file=arguments.configuration_file
    )
    writer(dump_mapping(configuration.to_mapping()))


def _project_root(working_directory: Path) -> Path | None:
    try:
        return GitRepository(working_directory).working_tree
    except RepositoryError:
        return None


def _run_tool(
    arguments: Arguments, working_directory: Path, env: Mapping[str, str], writer: Writer
) -> None:
    repository = GitRepository(working_directory)
    _log.info("Project root is: %s", repository.working_tree)
    _log.info("DotGit directory is: %s", repository.git_dir)
    agent = resolve(env, working_directory)
    target_branch = _prepare(repository, agent, arguments)
    verify_unambiguous(working_directory, repository.working_tree, arguments.configuration_file)
    configuration = provide(
        working_directory,
        repository.working_tree,
        explicit_file=arguments.configuration_file,
        override_document=arguments.override_configuration,
    )
    variables = _calculate(repository, arguments, target_branch, env)
    write_outputs(
        variables,
        arguments,
        agent,
        writer,
        update_build_number=configuration.update_build_number,
        environment=env,
    )


def _prepare(repository: GitRepository, agent: BuildAgent, arguments: Arguments) -> str | None:
    """The read-only part of ``GitPreparer.Prepare``."""
    current_branch = agent.current_branch() or arguments.target_branch
    _log.info("Branch from build environment: %s", current_branch or "")
    if arguments.no_normalize or isinstance(agent, LocalBuild):
        return current_branch
    remotes = repository.remotes()
    if len(remotes) != 1:
        raise GitVersionError(
            f"{len(remotes)} remote(s) have been detected. When being run on a build server, "
            "the Git repository is expected to bear one (and no more than one) remote."
        )
    return current_branch


def _calculate(
    repository: GitRepository,
    arguments: Arguments,
    target_branch: str | None,
    env: Mapping[str, str],
) -> GitVersionVariables:
    """Ports ``CalculateVersionVariables`` with the disk cache."""
    cache: CacheProvider | None = None
    key = ""
    if not arguments.no_cache:
        cache = CacheProvider(repository)
        key = cache_key(
            repository,
            arguments.working_directory,
            arguments.override_configuration,
            arguments.configuration_file,
        )
        cached = cache.load(key)
        if cached is not None:
            return cached
    variables = calculate_variables(
        arguments.working_directory,
        override_document=arguments.override_configuration,
        explicit_config_file=arguments.configuration_file,
        target_branch=target_branch,
        commit_id=arguments.commit_id,
        environment=env,
    )
    if cache is not None:
        cache.save(key, variables)
    return variables


def version_text() -> str:
    """``/version`` output."""
    return __version__
