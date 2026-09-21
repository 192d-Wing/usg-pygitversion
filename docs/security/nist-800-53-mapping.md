<!-- SPDX-License-Identifier: MIT -->
# NIST SP 800-53 Rev 5 control mapping

pygitversion is a command-line tool and library. SP 800-53 is an
organisational control catalogue, so most controls are inherited from the
environment that runs the tool. This document lists the controls the tool
itself implements or provides evidence for, with a pointer to the evidence.
It is updated as part of the definition of done for any change that affects
a listed control (PLAN.md 9.5).

Status legend: **Implemented** (evidence exists in this repo), **Planned**
(phase in which it lands), **Inherited** (organisation's responsibility).

| Control | Title | Status | Implementation | Evidence |
|---------|-------|--------|----------------|----------|
| AC-3 | Access Enforcement | Partially implemented | Repository is opened read-only; git-dir and work-tree resolved by git itself; output-path confinement lands with the writers (Ph5) | `pygitversion/git/repository.py`, `test_git_repository.py` |
| AC-6 | Least Privilege | Implemented | Read-only git calls; `--no-optional-locks`; `core.hooksPath` pointed at the null device; no pager/editor; `GIT_TERMINAL_PROMPT=0` | `pygitversion/git/command.py`, `test_command_environment_is_minimal_and_hooks_disabled` |
| AU-2 / AU-3 | Event Logging / Content of Audit Records | Implemented | Timestamped, levelled records via `logging`; verbosity mapped to upstream names | `pygitversion/_logging.py` |
| AU-9 | Protection of Audit Information | Implemented | `/l` log file created `0o600` | `pygitversion/_logging.py::configure` |
| CM-5 | Access Restrictions for Change | Implemented | Branch protection with required review; PR template checklist | `.github/pull_request_template.md`, repo settings |
| CM-6 | Configuration Settings | Planned (Ph2) | Secure, upstream-identical defaults; `/showconfig` renders effective config | `pygitversion/config/` |
| CM-7 | Least Functionality | Implemented | One runtime dependency; no plugins; no telemetry; features opt-in by flag | `pyproject.toml` |
| IA-5 | Authenticator Management | Implemented (policy) | Tool accepts no credentials; `/u` `/p` rejected | `docs/deviations.md`, CLI tests (Ph5) |
| SA-11 | Developer Testing and Evaluation | Implemented | ruff bandit rules, mypy strict, pip-audit, CodeQL, differential tests; hypothesis property tests on the semver parser; 1,203 upstream semver cases replayed | `.github/workflows/ci.yml`, `codeql.yml`, `tests/unit/test_semver.py` |
| SA-15 | Development Process, Standards, and Tools | Implemented | PLAN.md section 9, CONTRIBUTING.md, PR template | those files |
| SC-8 / SC-13 | Transmission Confidentiality / Cryptographic Protection | Implemented (by design) | No network I/O in v1; only SHA-256 from `hashlib` for cache keys | `pyproject.toml` (no HTTP deps), cache module (Ph5) |
| SC-28 | Protection of Information at Rest | Planned (Ph5) | Cache files `0o600`, atomic replace, contain only version variables | `pygitversion/cache/` |
| SI-2 | Flaw Remediation | Implemented | Dependabot weekly; pip-audit blocks merge; SECURITY.md process | `.github/dependabot.yml`, `SECURITY.md` |
| SI-7 | Software, Firmware, and Information Integrity | Implemented | Release job verifies SHA256SUMS before publish; PEP 740 attestations; SBOM attached | `.github/workflows/release.yml` |
| SI-10 | Information Input Validation | Partially implemented | argparse with typed options; .NET regex translated with length cap, bounded subjects and rejection of unsupported constructs; NUL-delimited strict git output parsing; date-format length cap; typed config schema (Ph2) | `pygitversion/dotnet/regex.py`, `pygitversion/git/repository.py::_parse_log`, `test_dotnet_regex.py` |
| SI-11 | Error Handling | Implemented | Typed exceptions, one-line messages, tracebacks only at Diagnostic | `pygitversion/errors.py`, `test_unported_path_fails_cleanly` |
| SI-16 | Memory Protection | Implemented | No eval/exec/pickle/yaml.load/shell=True, enforced by ruff `S` rules; single subprocess call site with argv lists, minimal environment and timeouts; bounded commit walks and caches | `pyproject.toml`, `pygitversion/git/command.py`, `test_walk_enforces_commit_cap` |
| SR-3 / SR-4 | Supply Chain Controls / Provenance | Implemented | Hashed `uv.lock`; actions pinned to SHAs; Dependabot; SBOM | `uv.lock`, `.github/workflows/*.yml` |
| SR-11 | Component Authenticity | Implemented | Trusted Publishing (OIDC), no stored tokens; attestations | `.github/workflows/release.yml` |

Inherited (not addressed by the tool): AC-2, AT-*, CP-*, IR-*, MP-*, PE-*,
PS-*, and all organisation-level PM controls.
