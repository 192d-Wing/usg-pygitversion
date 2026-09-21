## Summary

<!-- What changed and why. Name the upstream GitVersion type/method ported, if any. -->

## Definition of done (PLAN.md 9.5)

- [ ] Docstrings and comments present; upstream C# reference cited where ported
- [ ] `ruff check`, `ruff format --check`, `mypy --strict`, tests green on all OSes
- [ ] New input surface has validation tests and at least one negative test (SI-10)
- [ ] Any new subprocess, file or regex use goes through the shared wrappers (`git/command.py`, `config/dotnet_regex.py`)
- [ ] `docs/security/nist-800-53-mapping.md` updated if a control's evidence changed
- [ ] `docs/deviations.md` updated if behaviour differs from GitVersion 6.8.2

## Security checklist

- [ ] No `shell=True`, `eval`, `exec`, `pickle`, or `yaml.load`
- [ ] No environment variables, file contents or credentials in log or error messages
- [ ] Repository content (branch names, tags, commit messages) treated as untrusted
