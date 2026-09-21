# Contributing

This project ports [GitVersion](https://gitversion.net) 6.8.2 to Python.
Read `PLAN.md` first; it records every design decision and the engineering
standards (section 9) that pull requests are reviewed against.

## Setup

```sh
uv sync --group dev
uv run pre-commit install
uv run pytest
```

Optional, for differential tests against the reference implementation:

```sh
dotnet tool install --global GitVersion.Tool --version 6.8.2
uv run pytest -m differential
```

## Rules of the road

- **Port, don't reinvent.** Every calculation behaviour comes from the C#
  source or its scenario tests. Cite the upstream type or method in the
  docstring. If you must deviate, comment why in place and add an entry to
  `docs/deviations.md`.
- **Docstrings everywhere.** `ruff` enforces pydocstyle (Google style).
- **Strict typing.** `mypy --strict` must pass with no new ignores.
- **One subprocess call site.** All git invocations go through
  `pygitversion/git/command.py`. Tests use `tests/fixtures/repository.py`.
  All user-supplied regexes go through `pygitversion/dotnet/regex.py`.
- **Treat the repository as hostile.** Branch names, tags and commit
  messages are untrusted input: never shell-interpolate, never use as format
  strings, never build file paths from them.
- **No secrets, no environment dumps** in logs, errors, cache or output.
- **Bounded memory.** Stream git output; never load whole history; all
  caches have a maximum size. `pytest` runs with `ResourceWarning` as an
  error, so close what you open.

## Commit and PR conventions

- Branch from `main`; open a PR; CI must be green on all three OSes.
- Fill in the PR template checklist honestly. Reviewers use it.
- Commit messages may carry `+semver: major|minor|patch|none` to steer the
  tool's own version, exactly as GitVersion documents.
