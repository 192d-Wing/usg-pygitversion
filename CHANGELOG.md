# Changelog

All notable changes to pygitversion are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/). Versions are computed by
the tool itself from git history (PLAN.md 8.3).

## [Unreleased]

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
- Public Python API: `pygitversion.calculate` and `pygitversion.export_env`.
- Security posture documented against NIST SP 800-53 Rev 5
  (`docs/security/nist-800-53-mapping.md`); behavioural differences from the
  .NET tool documented in `docs/deviations.md`.

### Not included
- AssemblyInfo, project-file and WiX updaters, the MSBuild task, dynamic
  repository cloning (`/url`) and build agents other than GitHub Actions and
  GitLab CI (see PLAN.md section 1).
