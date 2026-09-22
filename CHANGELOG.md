<!-- SPDX-License-Identifier: MIT -->
# Changelog

All notable changes to usg-pygitversion are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/). Versions are computed by
the tool itself from git history (PLAN.md 8.3).

## [Unreleased]

### Security
- `/output dotenv` now single-quotes values POSIX-style, so a branch name
  containing `'` and `$(...)` can no longer execute commands when the file
  is sourced. Output is unchanged for values without a single quote.
- `--output env --shell powershell` doubles the Unicode single-quote
  characters U+2018 to U+201B as well as `'`, which PowerShell also treats
  as string delimiters.
- Every revision passed to git is preceded by `--end-of-options`, and `/c`
  rejects values starting with `-`, so a commit id such as
  `--output=<file>` cannot be parsed as a `git log` option and overwrite a
  file. git 2.24 or newer is now required.
- The disk cache key includes the requested target branch and commit, so a
  cached result for `HEAD` is no longer returned for `/c <sha>` or `/b`.
- Configuration regexes that nest an unbounded quantifier inside another
  (`(a+)+`) are rejected at load time; such a pattern in `GitVersion.yml`
  could previously hang the tool indefinitely.
- `{env:NAME}` placeholders in configuration templates (`label`,
  `assembly-*-format`) no longer see environment variables whose names
  look like credentials. The `/format` switch is unaffected.
- The streaming git reader sends the child's stderr to a temporary file and
  kills the child on timeout, removing a deadlock on large stderr output.
- Git children inherit only `GIT_SSL_*`, `GIT_TRACE*` and
  `GIT_CONFIG_NOSYSTEM` from the caller; `GIT_CONFIG_GLOBAL`,
  `GIT_CONFIG_SYSTEM` and `GIT_CONFIG_COUNT`/`KEY`/`VALUE` are no longer
  passed through.
- Release workflow: publishes the exact artefacts CI tested (no rebuild),
  verifies their hashes before and after SBOM generation, pins the SBOM
  generator version, writes the SBOM outside `dist/`, and only publishes
  from a `v*` tag push (manual dispatch stops after the build step).

## [1.0.0] - 2026-09-21

### Changed
- Renamed from `pygitversion` to `usg-pygitversion`: the PyPI distribution
  and console script are `usg-pygitversion`, the import package is
  `usg_pygitversion` (`python -m usg_pygitversion`), and the test
  environment variables are `USG_PYGITVERSION_*`. The `gitversion` console
  script is unchanged.

### Added
- Pure-Python port of GitVersion 6.8.2: semantic-version model, configuration
  (GitFlow/v1, GitHubFlow/v1, TrunkBased/preview1 presets, `GitVersion.yml`,
  `/overrideconfig`), and the complete calculation engine including the
  Mainline strategy. Verified against the reference binary on 897 ported
  upstream scenarios.
- CLI compatible with the upstream argument surface in `/flag`, `-flag` and
  `--flag` forms; `json`, `file`, `dotenv` and `buildserver` outputs;
  `/showvariable`, `/format`, `/showconfig`; on-disk cache.
- Build-server integration for GitHub Actions and GitLab CI, and a generic
  environment export (`--output env` for sh/bash/PowerShell/cmd, `--env-file`,
  `--prefix`) for every other CI system.
- Public Python API: `usg_pygitversion.calculate` and `usg_pygitversion.export_env`.
- Security posture documented against NIST SP 800-53 Rev 5
  (`docs/security/nist-800-53-mapping.md`); behavioural differences from the
  .NET tool documented in `docs/deviations.md`.

### Not included
- AssemblyInfo, project-file and WiX updaters, the MSBuild task, dynamic
  repository cloning (`/url`) and build agents other than GitHub Actions and
  GitLab CI (see PLAN.md section 1).

[Unreleased]: https://github.com/192d-Wing/usg-pygitversion/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/192d-Wing/usg-pygitversion/releases/tag/v1.0.0
