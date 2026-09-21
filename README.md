<!-- SPDX-License-Identifier: MIT -->
# pygitversion

Semantic versioning from git history, without .NET. A pure-Python port of
[GitVersion](https://gitversion.net) 6.8.2.

> **Status:** Phases 0-5 complete: the calculation engine for the GitFlow,
> GitHubFlow and TrunkBased (Mainline) workflows, the CLI, all outputs,
> the cache, the GitHub Actions and GitLab CI agents and the generic
> environment export are ported and verified against the reference 6.8.2
> binary on 500+ upstream scenarios. Phase 6 (hardening and the first
> release) is next; see `PLAN.md` for the roadmap and every design decision.

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
gitversion                              # JSON, same as upstream
gitversion /showvariable SemVer         # upstream /flag syntax works
gitversion --showvariable SemVer        # so does --flag syntax
gitversion /format "{Major}.{Minor}"    # custom formatting
gitversion /output dotenv               # GitVersion_<Name>='value' lines
gitversion /output file /outputfile v.json
gitversion /showconfig                  # effective configuration as YAML
gitversion /overrideconfig tag-prefix=v /nocache
gitversion /output buildserver          # GitHub Actions / GitLab CI integration
```

For build servers without a dedicated agent, export the variables into
the environment of a shell or a file:

```sh
eval "$(python -m pygitversion --output env)"                       # sh/bash/zsh
python -m pygitversion --output env --shell powershell | Invoke-Expression
python -m pygitversion --output env --shell cmd > gv.bat && call gv.bat
python -m pygitversion --env-file "$SOME_CI_ENV_FILE"               # append KEY=value
```

Values are quoted for the chosen shell, so branch names cannot inject
commands. `--prefix` changes the `GitVersion_` prefix. Run
`gitversion /?` for the full argument list.

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
