# pygitversion

Semantic versioning from git history, without .NET. A pure-Python port of
[GitVersion](https://gitversion.net) 6.8.2.

> **Status:** Phase 0 (project bootstrap). The calculation engine is not yet
> ported; see `PLAN.md` for the roadmap and every design decision.

## Why

GitVersion is the standard tool for deriving SemVer from branches, tags and
merge history, but it needs the .NET runtime. This port runs anywhere Python
3.11+ and a `git` binary exist, and produces byte-compatible JSON so existing
scripts keep working.

## Install

```sh
uv tool install pygitversion       # or: pipx install pygitversion
```

## Use

```sh
gitversion                          # JSON, same as upstream
gitversion /showvariable SemVer     # upstream /flag syntax works
gitversion --showvariable SemVer    # so does --flag syntax
python -m pygitversion --output env # shell exports for any CI system
```

From Python, in a build script:

```python
import os, pygitversion

v = pygitversion.calculate(".")
pygitversion.export_env(v, os.environ)   # GitVersion_* now visible to subprocesses
print(v.full_sem_ver)
```

## What is and is not ported

Ported: the full calculation pipeline, all three built-in workflows
(GitFlow/v1, GitHubFlow/v1, TrunkBased/preview1), `GitVersion.yml`
configuration, JSON / dotenv / file output, GitHub Actions and GitLab CI
build-agent integration, and a generic environment export for every other
CI system.

Not ported: AssemblyInfo / `.csproj` / WiX updaters, the MSBuild task, and
dynamic remote clone (`/url`). See `PLAN.md` section 1.

## Security

See `SECURITY.md` for reporting and `docs/security/nist-800-53-mapping.md`
for how the tool maps to NIST SP 800-53 Rev 5 controls.

## License

MIT. GitVersion itself is MIT licensed; this project is an independent
reimplementation and is not affiliated with the GitTools organisation.
