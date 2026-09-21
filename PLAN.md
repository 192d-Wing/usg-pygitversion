<!-- SPDX-License-Identifier: MIT -->
# pygitversion: Plan for a Python port of GitVersion

Status: APPROVED (rev 7: engineering standards section added (docs, NIST 800-53 Rev5, security, memory); all questions resolved; PyPI-only distribution confirmed; PyPI wheel publishing in CI/CD; GitHub+GitLab agents, generic env export + Python API; Python 3.11 floor, git binary backend, local gitversion 6.8.2 available for differential tests)
Target of the port: GitVersion 6.8.2 (latest release, 2026-07-10), https://gitversion.net/docs/
Goal: run GitVersion's version calculation on Python dev machines with no .NET runtime.

---

## 1. What we are porting (and what we are not)

GitVersion is a CLI that reads a git repository plus an optional `GitVersion.yml`
and emits ~30 version variables (`SemVer`, `FullSemVer`, `Major`, `PreReleaseTag`,
`CommitsSinceVersionSource`, ...). Its .NET source is roughly:

| Component (C#)              | Size    | Port decision |
|-----------------------------|---------|---------------|
| GitVersion.Core             | ~500 KB | Port (the actual algorithm)                |
| GitVersion.Configuration    | ~125 KB | Port (YAML config, 3 workflow presets)     |
| GitVersion.App + Output     | ~120 KB | Port CLI, json/dotenv/file output          |
| GitVersion.BuildAgents      | ~55 KB  | Port GitHub Actions + GitLab CI, plus a generic env export / Python API (section 7) |
| GitVersion.MsBuild          |         | Out of scope (.NET-only by definition)     |
| AssemblyInfo / .csproj / WiX updaters |  | Out of scope in v1 (no .NET on target machines) |
| Core.Tests IntegrationTests | ~1.27 MB, ~40 scenario files | Port as the conformance oracle |

**In scope for v1**
- Full calculation pipeline: branch-config resolution, version strategies
  (`Fallback`, `ConfiguredNextVersion`, `MergeMessage`, `TaggedCommit`,
  `TrackReleaseBranches`, `VersionInBranchName`, `Mainline`), increment
  finding (commit-message bumps, `Inherit`, `prevent-increment.*`), deployment
  modes (`ManualDeployment`, `ContinuousDelivery`, `ContinuousDeployment`),
  pre-release weights, `ignore` (sha, paths, commits-before, branches, tags).
- All three built-in workflows: `GitFlow/v1` (default), `GitHubFlow/v1`, `TrunkBased/preview1`.
- `GitVersion.yml` loading, `/overrideconfig`, `/showconfig`, `/config`.
- Output: `json` (default), `/showvariable`, `/format`, `dotenv`, `file` /
  `/outputfile`, `buildserver` (section 7).
- Repo options: `path`, `/c <sha>`, `/b <branch>` (local only), `/nofetch`,
  `/nocache`, `/allowshallow`, `/verbosity`, `/diag`, `/version`, `/help`.
- Result cache (same key semantics: config hash + HEAD + branch + dirty state).

**Explicitly out of scope for v1** (documented in README as such)
- `/updateassemblyinfo`, `/updateprojectfiles`, `/ensureassemblyinfo`,
  `/updatewixversionfile`, MSBuild task.
- `/url` + `/u` `/p` remote clone (dynamic repositories).
  Users clone first; we may add later.
- Build-agent "normalize" of detached-HEAD CI checkouts is a stretch goal
  (see risk R4).

---

## 2. Key design decisions (please review these first)

### D1. Git access: shell out to `git`, no libgit2 (DECIDED)
Decision: plain `subprocess` calls to the `git` binary, behind a small
`GitRepository` abstraction. Zero native deps, git is already on every dev
machine, and GitVersion only needs a handful of read operations: `rev-list`, `for-each-ref`, `log --format`,
`merge-base`, `cat-file`, `status --porcelain`, `diff-tree`. We batch these
(one `rev-list --parents --format` walk per run, cached in memory) so
performance is fine. The abstraction lets us add a `pygit2` backend later
if anyone needs it.

### D2. Regex dialect: translate .NET regex to Python `re`
Config files and presets use .NET syntax, notably named groups
`(?<BranchName>.+)`. Python needs `(?P<BranchName>.+)`. We ship a
`dotnet_regex.compile()` shim that rewrites named groups and `\k<name>`
backrefs, and raises a clear error on unsupported constructs
(balancing groups, `(?#...)` comments are fine, conditionals are not).
Existing user `GitVersion.yml` files keep working unchanged.

### D3. Config model is a faithful copy, including the two-layer preset merge
GitVersion 6 splits config into `calculation:` and `output:` sections in the
presets and applies: built-in defaults -> workflow preset -> `GitVersion.yml`
-> `/overrideconfig`. We port `EffectiveConfiguration` and
`EffectiveBranchConfiguration` (including `Inherit` resolution via
`source-branches`) rather than re-deriving them, because most subtle bugs in
GitVersion history live there. The three preset YAML files are vendored verbatim.

### D4. Conformance testing against the upstream integration suite
GitVersion's ~40 `IntegrationTests/*Scenarios.cs` files each build a
repository via a fixture DSL (`MakeACommit`, `BranchTo`, `ApplyTag`,
`MergeTo`, ...) and assert a `FullSemVer`. We port that DSL to a Python
fixture (`RepositoryFixture`) and translate the scenarios. This is the only
credible way to claim parity; unit tests alone won't catch it. Target: 100%
of scenarios that fall in v1 scope pass, with any deliberate deviation
recorded in `docs/deviations.md`.

### D5. Python 3.11 floor; packaging with `uv` (DECIDED)
We target `>=3.11`: `tomllib`, `StrEnum`, `Self`, exception groups, and
modern typing without `typing_extensions`. `uv` manages the interpreter
(`uv python install 3.11`) so the system 3.9 on dev machines is irrelevant.
`pyproject.toml`, `hatchling` build, `uv tool install` for distribution.
Runtime deps: `PyYAML` only. Dev deps: `pytest`, `ruff`, `mypy`.

### D6. Output compatibility is a hard requirement, verified against the real tool
`gitversion` JSON output (key order, casing, `null` vs `""`, integer vs
string fields such as `BuildMetaData`) must be byte-compatible so existing
scripts that parse it keep working. GitVersion 6.8.2 and .NET 10 are
installed locally, so the test suite gains a **differential mode**: every
scenario fixture repo is also run through the real `gitversion` and the two
JSON outputs are diffed. This runs locally on demand (`pytest --differential`)
and in CI via the `gittools/gitversion:6.8.2` Docker image. CommitDate uses .NET format strings
(`yyyy-MM-dd`); we ship a small .NET-to-strftime formatter.

### D7. CLI surface
Accept GitVersion's `/flag` style **and** POSIX `--flag` style. Console
script is installed as both `gitversion` and `pygitversion`. Exit codes
match upstream (0 ok, 1 error).

---

## 3. Proposed package layout

```
pygitversion/
  __init__.py, __main__.py, _version.py
  cli/            argparse front-end, /flag translation, verbosity, exit codes
  git/            GitRepository abstraction; subprocess backend; models
                  (Commit, Branch, Tag, ReferenceName); commit graph cache
  dotnet/         .NET compatibility shims: regex dialect translation
                  (regex.py) and custom date-format engine (dateformat.py)
  config/         schema dataclasses, YAML loader, presets/*.yml (vendored),
                  merge/override logic, EffectiveConfiguration, validation,
                  /showconfig serializer
  semver/         SemanticVersion, PreReleaseTag, BuildMetaData, parsing
                  (Strict/Loose), comparison, formatting
  calculation/    context factory, EffectiveBranchConfigurationFinder,
                  IncrementStrategyFinder, strategies/ (one file per strategy),
                  mainline/ (the trunk-based state machine),
                  NextVersionCalculator, DeploymentMode calculators
  output/         VariableProvider (the ~30 variables), json/dotenv/file
                  writers, /format templating
  buildagents/    base ABC, resolver, LocalBuild, github.py, gitlab.py,
                  envexport.py (generic env/shell/file export, section 7.5)
  cache/          cache key + on-disk JSON cache under .git/gitversion_cache
  logging.py, errors.py
tests/
  fixtures/       RepositoryFixture DSL (creates real temp git repos)
  unit/           semver, config merge, regex shim, date format, variables
  scenarios/      ported upstream IntegrationTests (one module per C# file)
  golden/         JSON output snapshots
docs/             README, deviations.md, migration notes
```

---

## 4. Phased delivery

Each phase ends in a green test run and a tagged pre-release.

**Phase 0: Bootstrap (0.5 wk)**
- `pyproject.toml`, `uv` lock, ruff (incl. bandit `S` and pydocstyle `D`
  rules), `mypy --strict`, pytest config, CI (GitHub Actions matrix:
  macOS/Linux/Windows x Python 3.11/3.12/3.13, actions pinned to SHAs),
  CodeQL, `pip-audit`, Dependabot, pre-commit.
- `SECURITY.md`, `CONTRIBUTING.md`, PR template with the section 9.5
  checklist, and the initial `docs/security/nist-800-53-mapping.md`.
- `release.yml` with PyPI Trusted Publishing wired end to end (section 8);
  reserve the `pygitversion` name on PyPI and TestPyPI; publish `0.0.1` to
  prove the pipeline before any real code exists.
- `RepositoryFixture` test DSL. This lands first because every later phase
  is verified with it.

**Phase 1: Foundations (1 wk)**
- `semver/` with full parse/compare/format and `Strict`/`Loose` modes.
- `git/` subprocess backend and in-memory commit graph.
- `dotnet_regex` shim and .NET date formatter.
- Unit tests ported from `SemanticVersionTests`, `ReferenceNameTests`, etc.

**Phase 2: Configuration (1 wk)**
- Dataclass schema, YAML loader, preset vendoring, layered merge,
  `/overrideconfig` parsing, validation errors matching upstream wording.
- `/showconfig` producing YAML equal to upstream's approved
  `Workflows/approved/*.yml` (exact-match tests).

**Phase 3: Core calculation, GitFlow + GitHubFlow (2-3 wks)**
- Branch config finder with `Inherit`, version strategies except Mainline,
  increment finder, deployment modes, pre-release weighting, `ignore`.
- VariableProvider and JSON output.
- Port scenario suites: `MainScenarios`, `DevelopScenarios`,
  `FeatureBranchScenarios`, `ReleaseBranchScenarios`, `HotfixBranchScenarios`,
  `SupportBranchScenarios`, `PullRequestScenarios`, `VersionInTagScenarios`,
  `VersionInMergedBranchNameScenarios`, `VersionBumpingScenarios`,
  `IgnoreCommitScenarios`, `ComparingTheBehaviorOfDifferentVersioningModes`,
  `DocumentationSamplesForGitFlow`, `DocumentationSamplesForGitHubFlow`.

**Phase 4: Mainline / TrunkBased (1-2 wks)**
- Port `Mainline/` iteration state machine (Trunk / NonTrunk commit
  classifiers, enrichers, incrementers). This is the most intricate code in
  upstream and is isolated for that reason.
- Scenario suites: `MainlineDevelopmentScenarios`,
  `DocumentationSamplesForTrunkBased`, `AlignGitFlowWithMainline*`,
  `CompareTheDifferent*Mainline*`.

**Phase 5: CLI, outputs, cache, build agents (1 wk)**
- Full argument surface, `dotenv`/`file` output, `/showvariable`, `/format`,
  cache, GitHub Actions + GitLab CI agents, generic `--output env` /
  `--env-file` export, public Python API (`calculate`, `export_env`),
  `/diag` logging.
- Golden JSON tests generated by running the local `gitversion` 6.8.2 over
  the fixture repos; snapshots committed, regenerable with one command.

**Phase 6: Hardening and release (1 wk)**
- Run against 5-10 real internal repositories and diff against the local
  `gitversion` 6.8.2 output; the same check runs in CI via Docker.
- Performance check on a large repo (goal: < 2 s for 50k commits).
- README, deviations doc, `uv tool install` instructions.
- Tag `v1.0.0`; release.yml publishes the wheel to PyPI and creates the
  GitHub release.

Total: roughly 7-9 engineer-weeks for one engineer. Phases 3 and 4 can run
in parallel with two engineers.

---

## 5. Risks and mitigations

- **R1. Hidden semantics in the C# code, not the docs.** Increment
  inheritance, `track-merge-target`, and Mainline have behavior only the code
  and tests define. Mitigation: port from source + tests, not from docs (D4).
- **R2. Regex dialect gaps.** Some user configs may use .NET-only regex
  features. Mitigation: shim with explicit error listing the unsupported
  construct; document alternatives.
- **R3. Performance of subprocess git on huge repos.** Mitigation: one bulk
  `rev-list` walk cached in memory, lazy tag/branch loading, benchmark in
  Phase 6, `pygit2` backend as an escape hatch behind the abstraction.
- **R4. CI checkouts (detached HEAD, missing local branches).** Upstream
  "normalizes" the repo (creates local branches from remotes, may fetch).
  Mitigation: implement read-only normalization (resolve branch from CI env
  vars and `refs/remotes/origin/*`) first; mutating normalization only if
  needed.
- **R5. Upstream drift.** GitVersion moves; we will lag. Mitigation: pin the
  ported version in the README, keep scenario files named after upstream so
  diffs are easy to re-port, and schedule a quarterly re-sync.
- **R6. Windows.** Dev machines are macOS/Linux today, but path handling and
  `git` invocation quoting differ. Mitigation: Windows in the CI matrix from
  Phase 0.

---

## 6. Decisions log

All reviewer questions are resolved. Recorded here for reference:

| Decision | Outcome |
|----------|---------|
| Git backend | Shell out to the `git` binary (D1) |
| Python floor | 3.11 (D5) |
| Reference implementation for parity | Local GitVersion 6.8.2 on .NET 10, used for differential tests (D6) |
| Build agents in v1 | GitHub Actions and GitLab CI only; all others via generic env export (7.5). No Tier 2 in v1. |
| AssemblyInfo / csproj / WiX updaters, MSBuild task | Out of scope |
| `/url` dynamic clone (clone a remote into a temp dir and version it) | Out of scope for v1; users clone first. Can be added later as a thin wrapper. |
| Distribution | PyPI only, via Trusted Publishing from the release pipeline (section 8). No internal index. |

Plan status: **approved for Phase 0**.

---

## 7. Build server (`/output buildserver`) in detail

### 7.1 What upstream does
Build-agent support is one abstract class (`BuildAgentBase`) plus 15 small
subclasses, one per CI system. The interface is small and all of it ports
cleanly to Python. Each agent answers five questions:

| Hook | Purpose | Default |
|------|---------|---------|
| `can_apply()` | Detect this CI from an environment variable (e.g. `GITHUB_ACTIONS`, `TF_BUILD`, `GITLAB_CI`, `JENKINS_URL`, `TEAMCITY_VERSION`, `BUILDKITE=true`) | env var non-empty |
| `current_branch()` | Read the branch being built from CI env vars, because CI checkouts are usually detached HEAD | `None` (fall back to git) |
| `current_tag()` | Read the tag being built (GitHub `GITHUB_REF_TYPE=tag`, GitLab `CI_COMMIT_TAG`) | `None` |
| `prevent_fetch()` | Whether GitVersion should skip `git fetch` on this agent | `True` |
| `write_integration(writer, variables, update_build_number)` | Emit the agent-specific lines to stdout and/or files | see below |

**Resolution.** All agents are probed; the *last* one whose `can_apply()` is
true wins; if none match, `LocalBuild` is used. `LocalBuild` prints nothing
extra, so `/output buildserver` on a dev machine is a silent no-op. Detection
failures are logged and skipped, never fatal.

**Write integration** does two things, in order:
1. If `update-build-number: true` (config, default true) and the agent has a
   build-number concept, emit `set_build_number(variables)`, normally a
   service message carrying `FullSemVer`.
2. For every one of the ~30 variables in output order, emit
   `set_output_variables(name, value)`, which returns zero or more lines.
   Names are always prefixed `GitVersion_` (TeamCity uses `GitVersion.`).

**Interaction with the other outputs.** `/output` accepts several values at
once (`/output json /output buildserver`). `buildserver` is additive: the
JSON still prints. The `/updatebuildnumber` semantics come from the config
key `update-build-number`, not a CLI flag.

### 7.2 Per-agent behaviour to reproduce

| Agent | Detect | Branch source | Build number | Variable export |
|-------|--------|---------------|--------------|-----------------|
| GitHub Actions | `GITHUB_ACTIONS` | `GITHUB_REF` unless `GITHUB_REF_TYPE=tag` | none | appends `GitVersion_<Name>=<value>` lines to the file named by `$GITHUB_ENV`, skipping empty values; logs a warning if `GITHUB_ENV` unset |
| Azure Pipelines | `TF_BUILD` | `GIT_BRANCH`, else `BUILD_SOURCEBRANCH` unless it is `refs/tags/*` | `##vso[build.updatebuildnumber]…`; if `BUILD_BUILDNUMBER` contains `$(GITVERSION_<Name>)` / `$(GITVERSION.<Name>)` tokens they are substituted, otherwise `FullSemVer` with a trailing `+0` stripped | two lines per variable: `##vso[task.setvariable variable=GitVersion_<Name>]<v>` and the same with `;isOutput=true` |
| GitLab CI | `GITLAB_CI` | `None` if `CI_COMMIT_TAG`; else `CI_MERGE_REQUEST_REF_PATH`; else `CI_COMMIT_REF_NAME` | `FullSemVer` printed | writes `gitversion.properties` (`GitVersion_<Name>=<v>` per line) in cwd and prints the same lines |
| Jenkins | `JENKINS_URL` | `BRANCH_NAME` (pipeline-as-code), else `GIT_LOCAL_BRANCH`, else `GIT_BRANCH` | `FullSemVer` printed | writes `gitversion.properties`, same format as GitLab |
| TeamCity | `TEAMCITY_VERSION` | `Git_Branch` env var; warns if absent | `##teamcity[buildNumber '<FullSemVer>']` | two lines per variable: `##teamcity[setParameter name='GitVersion.<Name>' value='…']` and `system.GitVersion.<Name>`; values escaped per TeamCity service-message rules (`|`, `'`, `\n`, `\r`, `[`, `]`) |
| Buildkite | `BUILDKITE=true` | `BUILDKITE_BRANCH`, or `refs/pull/<n>/head` when `BUILDKITE_PULL_REQUEST` set | none | none |
| AppVeyor, Bitbucket Pipelines, CodeBuild, Drone, Travis, MyGet, ContinuaCI, Space, EnvRun | each ~30 lines | per agent | per agent | per agent |

### 7.3 Port plan
- `pygitversion/buildagents/base.py`: `BuildAgent` ABC mirroring the five
  hooks, `LocalBuild`, and `resolve(env) -> BuildAgent` with the
  last-match-wins rule and non-fatal detection.
- One module per agent. **Tier 1 (v1, fully tested):** GitHub Actions and
  GitLab CI, plus the generic environment export in 7.5 which covers every
  other build server. **Tier 2 (post-v1, on request):** Azure Pipelines,
  Jenkins, TeamCity, Buildkite and the remaining nine, which are mechanical
  and each about 30 lines. Tier 2 users are not blocked: they use 7.5.
- The agent's `current_branch()` / `current_tag()` feed the context factory
  in `calculation/`, so a detached-HEAD CI checkout still resolves to the
  right branch config. This is the read-only part of the "normalize" step
  in risk R4 and is required for correct CI results, not just output.
- `prevent_fetch()` is honored but mostly moot: v1 never fetches unless
  `/nofetch` is absent *and* the agent allows it; on dev machines nothing
  fetches.
- Environment is injected (a `Mapping[str, str]`), never read from
  `os.environ` directly, so every agent is unit-testable without a CI box.

### 7.4 Testing
- Unit tests per agent, ported from upstream `GitVersion.BuildAgents.Tests`:
  detection, branch/tag resolution, exact output lines, file writes to a tmp
  dir.
- Differential test: run the real `gitversion /output buildserver` with the
  same faked env vars and diff stdout and any written files. This is cheap
  since the local 6.8.2 install is available.
- One smoke job per Tier 1 agent in real CI where we have access (GitHub
  Actions at minimum) that asserts the exported `GitVersion_SemVer` variable
  is visible in a later step.
- For 7.5: tests that `export_env` populates a mapping, that the `env`
  output is `eval`-safe for shell metacharacters in branch names, that the
  `--env-file` output round-trips through `python-dotenv`-style parsing, and
  a `python -m pygitversion` invocation test.

### 7.5 Generic environment export for unlisted build servers

Goal: any build server, or any plain script, can consume GitVersion
variables as environment variables without a dedicated agent. A child
process cannot mutate its parent's environment, so we provide the three
mechanisms that actually work, all producing the same `GitVersion_<Name>`
variable set as the built-in agents:

1. **Python API** (for build scripts written in Python: `nox`, `invoke`,
   custom `build.py`, pytest conftest, Django/Flask settings, etc.):

   ```python
   import os
   import pygitversion

   version = pygitversion.calculate(".")          # -> GitVersionVariables
   pygitversion.export_env(version, os.environ)   # sets GitVersion_* in-process
   pygitversion.export_env(version, env, prefix="MYAPP_")   # any MutableMapping
   version.as_dict()                              # same keys/values as JSON output
   version.full_sem_ver                           # typed attribute access
   ```

   Because this runs inside the build script's own process, the variables
   are visible to that script and to every subprocess it launches. This is
   the primary answer for "non-listed build servers".

2. **Module entry point with shell-evaluable output**, for shell-based
   pipelines (`python -m pygitversion` works even when the `gitversion`
   console script is not on `PATH`, e.g. inside a `uv run` or a venv):

   ```sh
   eval "$(python -m pygitversion --output env)"          # POSIX sh/bash/zsh
   python -m pygitversion --output env --shell powershell | Invoke-Expression
   python -m pygitversion --output env --shell cmd > gv.bat && call gv.bat
   ```

   `--output env` prints one `export GitVersion_<Name>='<value>'` line per
   variable (or `$env:`/`set` for the other shells), with values quoted
   safely for the chosen shell. `--prefix` overrides `GitVersion_`.

3. **File-based export**, for servers that source a file between steps:

   ```sh
   python -m pygitversion --output dotenv --outputfile gitversion.env
   python -m pygitversion --env-file "$SOME_CI_ENV_FILE"   # append, GitHub-style
   ```

   `dotenv` is upstream's existing format (`GitVersion_<Name>=<value>` per
   line). `--env-file` is new: it appends to an existing file, which is the
   contract used by GitHub Actions (`GITHUB_ENV`) and by several other CI
   systems that expose a "write vars here" file.

Implementation notes:
- All three share one `EnvExporter` in `buildagents/envexport.py`: it owns
  naming, prefix handling, empty-value skipping (matching GitHub Actions
  behaviour), and per-shell quoting. Built-in agents that write env lines
  (GitHub Actions, GitLab, Jenkins) reuse it, so formats can't drift.
- The public API is `pygitversion.calculate`, `pygitversion.export_env`,
  and the `GitVersionVariables` dataclass. It is the supported programmatic
  surface and is covered by the compatibility promise; everything else in
  the package is private.
- `--output env` composes with the other outputs like `buildserver` does,
  but when it is the only output the JSON is suppressed so the result is
  safe to `eval`.
- Where a build server exposes a "current branch" env var but has no agent,
  `--branch` (upstream `/b`) already lets the pipeline pass it explicitly.
  We also add `GITVERSION_BRANCH` / `GITVERSION_TAG` env overrides so a
  pipeline can set them once instead of passing flags.

---

## 8. CI/CD and PyPI publishing

### 8.1 Pipeline shape (GitHub Actions)
```
ci.yml        on push / pull_request
  lint        ruff check + ruff format --check + mypy --strict
  test        matrix: ubuntu / macos / windows  x  Python 3.11 / 3.12 / 3.13
              pytest with coverage; unit + scenario suites
  diff        ubuntu only; runs the differential suite against the real
              gitversion 6.8.2 (installed via `dotnet tool install`)
  build       uv build  ->  dist/*.whl + dist/*.tar.gz, uploaded as artifact
  smoke       installs the built wheel into a clean venv on each OS and runs
              `gitversion /version`, `python -m pygitversion --output env`
              on the checked-out repo, and the GitHub Actions env-export
              smoke (asserts GitVersion_SemVer visible in a later step)

release.yml   on push of tag v*  (also workflow_dispatch for reruns)
  needs: ci   reuses ci.yml via workflow_call; nothing publishes unless CI
              is green on the tagged commit
  build       uv build; version comes from the tag (see 8.3)
  publish-testpypi   if tag is a pre-release (v1.0.0-beta.1, v1.0.0rc1)
  publish-pypi       if tag is a final release; `environment: pypi`
  github-release     gh release create with dist/* attached and generated
                     notes
```

### 8.2 Publishing mechanics
- **Trusted Publishing (OIDC), no API tokens.** The `pypi` and `testpypi`
  environments on GitHub are registered as trusted publishers on pypi.org
  and test.pypi.org for the `pygitversion` project. The job has
  `permissions: id-token: write` and uses `pypa/gh-action-pypi-publish`.
  No secrets are stored in the repo.
- **Environment protection.** The `pypi` environment requires a reviewer
  approval and is restricted to `v*` tags, so a mistyped tag cannot publish.
- **Artifacts.** Both a universal `py3-none-any` wheel and an sdist are
  published. The package is pure Python, so one wheel covers every OS.
- **Attestations.** `pypa/gh-action-pypi-publish` generates PEP 740
  attestations by default; we keep that on.
- **Name reservation.** Claim `pygitversion` on PyPI and TestPyPI in Phase
  0 with a `0.0.1` placeholder so the trusted-publisher config can be
  created against a real project. PyPI is the only distribution target;
  no internal index.

### 8.3 Versioning the package itself
The tool dogfoods itself. `hatch-vcs` is *not* used because it would give
us setuptools-scm semantics rather than GitVersion semantics. Instead:
- A tiny hatch build hook runs `python -m pygitversion --showvariable
  SemVer` (from the source tree, no install needed) and writes
  `pygitversion/_version.py`. PEP 440 normalisation maps GitVersion output
  to a legal Python version: `1.2.0-beta.3` -> `1.2.0b3`,
  `1.2.0-alpha.5` -> `1.2.0a5`, `1.2.0-feature-x.4` -> `1.2.0.dev4`,
  `1.2.0-PullRequest12.1` -> `1.2.0.dev1`. The mapping is a documented
  function with tests, and the raw GitVersion string is kept in
  `_version.py` as `__gitversion__`.
- Release tags are created by hand (`git tag v1.2.0 && git push --tags`) and
  the tagged commit then computes exactly `1.2.0`.
- Repo config `GitVersion.yml` uses `GitHubFlow/v1`: `main` is
  ContinuousDelivery, so untagged pushes to main produce e.g. `1.2.1-5` ->
  `1.2.1.dev5`, which TestPyPI accepts for a nightly if we want one.

### 8.4 Install story for the dev machines
```sh
uv tool install pygitversion          # or: pipx install pygitversion
gitversion                            # console script
python -m pygitversion                # module form, inside any venv
uv add --dev pygitversion             # as a project dev dependency
```
Requires Python >= 3.11 and a `git` binary on `PATH`; nothing else.

---

## 9. Engineering standards: documentation, security, memory

These are mandatory for every commit. Reviewers reject PRs that do not meet
them. They are enforced by tooling where a tool exists and by review
checklist otherwise.

### 9.1 Code documentation
- Every module, class and public function has a docstring (Google style).
  Docstrings state *what* and *why*; they name the upstream C# type or
  method being ported (e.g. `Ports: IncrementStrategyFinder.DetermineIncrementedField`)
  so the port stays traceable to GitVersion 6.8.2.
- Inline comments explain non-obvious logic, especially anywhere behaviour
  is dictated by an upstream quirk or a scenario test. Cite the scenario.
- `ruff` rule set `D` (pydocstyle) is enabled, so a missing docstring fails
  lint. `mypy --strict` is on; every function is fully typed.
- Any deliberate deviation from upstream is commented in place *and* listed
  in `docs/deviations.md`.

### 9.2 NIST SP 800-53 Rev 5 alignment
800-53 is an organisational control catalogue; most controls are satisfied
by the environment the tool runs in, not by the tool. The table lists the
controls a CLI/library can implement or provide evidence for, and how
pygitversion does so. `docs/security/nist-800-53-mapping.md` will carry this
table with per-control evidence links (file, test, CI job) and is kept
current as part of the definition of done for each phase.

| Control | Requirement | How pygitversion satisfies it |
|---------|-------------|-------------------------------|
| **SI-10** Information Input Validation | Validate all inputs | CLI args parsed by argparse with typed choices; `GitVersion.yml` validated against a typed schema with allow-listed keys and enum values, unknown keys rejected with a precise error; regex from config compiled through the .NET shim with a length cap and a per-match timeout; git output parsed with strict formats (`%x00` delimiters), never split on whitespace heuristically; branch/tag names validated with `git check-ref-format` rules before use. |
| **SI-11** Error Handling | Fail securely, no sensitive data in errors | All exceptions are typed (`errors.py`), messages never include environment contents or file contents; tracebacks only with `/verbosity diagnostic`; exit codes are deterministic. |
| **SI-16** Memory Protection | Protect from unauthorised code execution | No `eval`/`exec`, no `pickle`, no `yaml.load` (only `yaml.safe_load`), no dynamic imports from config, `subprocess` always with an argument list and `shell=False`. Enforced by `ruff` rules `S102`, `S301`, `S506`, `S602`, `S604` (bandit set). |
| **SC-28** Protection of Information at Rest | Protect stored data | Cache files under `.git/gitversion_cache/` are written `0o600` via `os.open` with explicit mode, atomically (write temp + `os.replace`), contain only version variables (no env, no credentials), and are keyed by a SHA-256 of inputs. |
| **SC-8 / SC-13** Transmission and cryptography | Protect data in transit; use approved crypto | The tool makes no network calls in v1 (no `/url`, fetch disabled unless the user opts in and then it is `git fetch`, delegated to git's own TLS/SSH). Only hashing used is SHA-256 from `hashlib` for cache keys; no home-grown crypto. |
| **IA-5** Authenticator Management | Protect credentials | The tool never accepts, stores or logs credentials (`/u` `/p` are rejected with a message pointing to git credential helpers). `GitVersion_*` export skips nothing sensitive because no variable is sensitive; tests assert no env var other than the allow-list is ever echoed. |
| **AU-2 / AU-3 / AU-9** Audit events, content, protection | Log what matters, protect logs | Structured logging via `logging` with levels mapped to `/verbosity`; log lines include timestamp, component, and the git SHA under evaluation; the log file from `/l` is opened `0o600`; environment dumps are never logged, even at diagnostic level. |
| **CM-5 / CM-7** Access restrictions for change; least functionality | Minimal footprint | Runtime dependency is `PyYAML` only; every optional feature (build agents, env export) is opt-in by flag; no plugin loading; no telemetry. |
| **CM-6** Configuration Settings | Secure defaults | Defaults mirror upstream GitFlow/v1; `/showconfig` renders the fully effective configuration so users can audit exactly what was applied. |
| **AC-3 / AC-6** Access enforcement; least privilege | Operate with minimal rights | The tool only reads the repo except for the cache dir and explicitly requested output files; it never modifies refs, working tree, or git config; temp files use `tempfile.mkstemp` in a mode-restricted dir and are removed in `finally`. |
| **SA-11** Developer Testing and Evaluation | Security testing during development | `ruff` with the `S` (bandit) rule family, `mypy --strict`, `pip-audit` on the lock file, CodeQL on every PR, differential tests against upstream, fuzz tests (`hypothesis`) for the semver parser, regex shim and .NET date formatter. |
| **SA-15** Development Process, Standards, Tools | Documented process | This section, `CONTRIBUTING.md`, PR template with a security checklist, branch protection with required reviews. |
| **SR-3 / SR-4 / SR-11** Supply chain controls, provenance, authenticity | Trustworthy dependencies and artefacts | `uv.lock` with hashes committed; Dependabot; GitHub Actions pinned to commit SHAs, not tags; PyPI Trusted Publishing (OIDC) with PEP 740 attestations; SBOM (CycloneDX) generated and attached to each GitHub release. |
| **SI-2** Flaw Remediation | Patch promptly | `SECURITY.md` with a reporting channel; Dependabot and `pip-audit` failures block merge; security fixes ship as patch releases. |
| **SI-7** Software, Firmware, Information Integrity | Verify integrity | Wheels are attested (SR-11) and users can verify with `pip download` + `pypi-attestations`; the release job checks the built wheel's hash matches what was tested in CI before publishing. |

Controls that are out of the tool's hands (AC-2 accounts, PE physical,
IR incident response, etc.) are the operating organisation's responsibility
and are listed as "inherited" in the mapping document.

### 9.3 Security best practice (beyond the control mapping)
- **Subprocess hygiene.** One `GitCommand` wrapper is the only call site of
  `subprocess`. It passes an argument list, `shell=False`, an explicit
  `cwd`, a minimal environment (`PATH`, `HOME`, `GIT_*` allow-list, and
  `LC_ALL=C` so output is stable), a timeout, and `-c core.hooksPath=/dev/null`
  plus `--no-optional-locks` so a malicious repo cannot run hooks or take
  locks through us. Git paths are resolved once with `shutil.which`.
- **Path handling.** All user paths pass through `Path.resolve(strict=True)`
  and must be inside the repository root for reads or an explicit output
  path for writes; symlink escapes are rejected.
- **Regex denial of service.** Config regexes are run through the shim with
  a size limit and a compiled-pattern cache; matching is wrapped with a
  timeout (`regex` module `timeout=` is *not* used, to keep pure stdlib; we
  bound input length instead, since branch names and commit subjects are
  short). Tests include known pathological patterns.
- **YAML.** `yaml.safe_load` only, with a 1 MiB size cap on config files.
- **Untrusted repository content.** Commit messages, branch names and tags
  are treated as hostile: never interpolated into shell, never used as
  format strings, escaped for each shell in env export, and never used to
  build file paths.
- **No secrets, ever.** Nothing in the tool has a reason to hold a secret.
  A test asserts that `os.environ` is never serialised in any output path.

### 9.4 Memory management
Python manages allocation, but a version calculator over a large repository
can still blow up memory or hold resources open. Rules:
- **Stream, do not slurp.** Git output is consumed line by line from the
  subprocess pipe with a generator; `communicate()` is used only for
  commands with bounded output (`rev-parse`, `for-each-ref`). `rev-list`
  walks are bounded by the version-source commit; we stop reading and
  terminate the child once the answer is known.
- **Bounded commit graph.** The in-memory graph holds only the commits
  reachable between HEAD and the nearest version source(s), stored as
  `__slots__` dataclasses keyed by 20-byte binary SHA, not 40-char strings.
  A hard cap (configurable, default 200k commits) raises a clear error
  rather than exhausting memory.
- **Explicit lifetimes.** Every subprocess, file and temp dir is opened in a
  `with` block or an `ExitStack`; nothing relies on `__del__`. Child
  processes are always `wait()`ed to avoid zombies, and killed on timeout.
- **No unbounded caches.** `functools.lru_cache` always has a `maxsize`;
  compiled regex cache is bounded; the on-disk cache is per-commit and
  pruned to the newest N entries.
- **Sensitive buffers.** Not applicable in v1 (no credentials), recorded
  here so the rule exists if `/url` support is ever added: credentials
  would be held in `bytearray` and zeroed after use, never in `str`.
- **Verification.** A memory test in CI runs the calculator on a synthetic
  100k-commit repo under `tracemalloc` and asserts peak RSS below a fixed
  budget; `pytest` runs with `-W error::ResourceWarning` so an unclosed
  file or process fails the suite.

### 9.5 Definition of done (per PR)
- [ ] Docstrings and comments per 9.1, upstream reference cited
- [ ] `ruff` (incl. `S` and `D` rules), `mypy --strict`, tests green on all OSes
- [ ] New input surface has validation tests (SI-10) and a negative test
- [ ] New subprocess/file/regex use goes through the shared wrappers
- [ ] NIST mapping document updated if a control's evidence changed
- [ ] `docs/deviations.md` updated if behaviour differs from upstream
