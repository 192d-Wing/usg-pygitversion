# Deviations from GitVersion 6.8.2

Every intentional behavioural difference between pygitversion and the
reference implementation is recorded here. If it is not listed, it is a bug.

| Area | Upstream behaviour | pygitversion behaviour | Reason |
|------|--------------------|------------------------|--------|
| `/url`, `/u`, `/p` | Clones a remote into a temp dir and versions it | Rejected with a message pointing to `git clone` | Out of scope for v1 (PLAN.md section 6); avoids credential handling |
| `/updateassemblyinfo`, `/updateprojectfiles`, `/ensureassemblyinfo`, `/updatewixversionfile` | Rewrites .NET project files | Rejected with a clear error | .NET-specific; out of scope |
| Build agents | 15 agents auto-detected | GitHub Actions and GitLab CI auto-detected; generic `--output env` / `--env-file` for the rest | PLAN.md section 7 |
