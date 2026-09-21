<!-- SPDX-License-Identifier: MIT -->
# Deviations from GitVersion 6.8.2

Every intentional behavioural difference between pygitversion and the
reference implementation is recorded here. If it is not listed, it is a bug.

| Area | Upstream behaviour | pygitversion behaviour | Reason |
|------|--------------------|------------------------|--------|
| `/url`, `/u`, `/p` | Clones a remote into a temp dir and versions it | Rejected with a message pointing to `git clone` | Out of scope for v1 (PLAN.md section 6); avoids credential handling |
| `/updateassemblyinfo`, `/updateprojectfiles`, `/ensureassemblyinfo`, `/updatewixversionfile` | Rewrites .NET project files | Rejected with a clear error | .NET-specific; out of scope |
| Build agents | 15 agents auto-detected | GitHub Actions and GitLab CI auto-detected; generic `--output env` / `--env-file` for the rest | PLAN.md section 7 |
| Pre-release label ordering | `StringComparer.InvariantCultureIgnoreCase` (linguistic) | Case-folded code-point comparison | Python has no invariant-culture collation. Identical for the ASCII letters, digits, `-` and `.` that SemVer 2.0 permits in labels. |
| Regex dialect | .NET `Regex` | Translated to Python `re` (`pygitversion/dotnet/regex.py`) | Balancing groups, `(?n)`, and `\p{...}` classes are rejected with a message naming the construct. Patterns are capped at 1024 chars; matched subjects at 4 KiB (ReDoS bound). |
| `commit-date-format` | .NET `DateTimeOffset.ToString(fmt, InvariantCulture)` | Re-implemented custom-format engine (`pygitversion/dotnet/dateformat.py`) | Standard single-letter formats (`o`, `s`, `d`...) are not supported, only custom formats; GitVersion's default `yyyy-MM-dd` and all documented custom specifiers are. |
| Pre-release regex failure | Writes to the console | Logged at WARNING | Never reachable in practice; the pattern matches any string. |
