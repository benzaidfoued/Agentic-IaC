# Contributing

Thank you for improving ForgeIaC. Small, independently reviewable pull requests are welcome.
Open an issue before changing execution semantics, adding cloud dependencies, or changing the
catalog/run format. Documentation and focused bug fixes can go straight to a PR.

## Local workflow

1. Fork and create a topic branch from `main`.
2. Use Python 3.11+ and install `pip install -e '.[dev,ai,mcp]'` in a virtual environment.
3. Run `ruff check .`, `ruff format --check .` and `pytest -q`.
4. Install Terraform 1.9+ to run the real no-cloud integration test.
5. Add tests for meaningful behavior and safety regressions, update docs and CHANGELOG.
6. Describe the problem, resulting behavior, validation and limitations in the PR.

Use Conventional Commit titles (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Do not check in
secrets, state, saved plans or raw cloud logs. Do not give untrusted PR code cloud credentials.
Contributions are licensed under Apache-2.0. Include a `Signed-off-by` line (`git commit -s`)
to certify the Developer Certificate of Origin: https://developercertificate.org/ .

## Review criteria

- Clear purpose and documented user-facing behavior.
- All required checks pass on supported Python versions.
- New execution behavior has positive, failure and no-unapproved-mutation tests.
- New blueprints meet [catalog criteria](docs/catalog.md), including sandbox validation.
- No model-controlled executable commands or automatic approval bypass.
- Dependency additions are justified, licensed compatibly and reviewed for vulnerabilities.
- Breaking behavior includes migration notes and the appropriate version change.
- At least one maintainer approves; execution/security changes require two reviewers when the
  project has enough maintainers. Do not claim this is automatically enforced: configure
  repository rules/CODEOWNERS and review requirements as documented in the release guide.

Good starting tasks are in [the roadmap](docs/roadmap.md). Report reproducible bugs using the
issue template, with versions and redacted command output.
