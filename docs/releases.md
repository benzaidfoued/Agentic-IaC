# Launch and release criteria

## Repository setup (one time)

- Create your repository, confirm the working name, and add accurate description/topics.
  Suggested description: “Catalog-driven AI infrastructure agent for Terraform and Crossplane.
  Bring your model. Review your plan. Ship through GitOps.”
  Topics: `crossplane`, `terraform`, `gitops`, `platform-engineering`, `ai-agent`, `mcp`, `iac`.
- Set real CODEOWNERS (the supplied file contains commented placeholders, not fake ownership).
- Protect `main`: require PRs, approval, resolved conversations and CI test/audit checks. Require
  code-owner review for execution, catalog and workflow changes; disable force pushes/deletion.
- Restrict `v*` tag creation to maintainers. A workflow alone cannot enforce who may tag.
- Configure the `release` environment with a required reviewer and allowed protected tags.
  Availability of approval features depends on your GitHub plan/repository visibility.
- Enable private vulnerability reporting, secret scanning where available, Dependabot alerts
  and updates. Publish a private maintainer contact for conduct/security reports.
- Keep cloud secrets out of CI. Fork PRs run tests without deployment access. Do not change
  triggers to `pull_request_target` to run untrusted PR code with write credentials.
- Enable Discussions if you want design discussions and showcase posts. Add a demo recording
  only after exercising the demo yourself; do not imply a successful cloud run from fake output.

## Definition of a releasable version

1. Version agrees in `pyproject.toml`, `src/forgeiac/__init__.py`, changelog and `vX.Y.Z` tag.
2. CI passes on Python 3.11, 3.12 and 3.13; lint, package build and dependency audit pass.
3. Real no-cloud Terraform create/no-op/update lifecycle passes.
4. Security-negative cases pass: bad schema, injection, changed plan, wrong/expired/replayed
   approval, destructive plan, changed cluster identity and failed apply.
5. Any advertised new cloud capability has sandbox evidence with provider/control-plane versions;
   if not, label it explicitly as unverified and avoid a production-support claim.
6. Docs, compatibility notes, migration notes and limitations match delivered behavior.
7. Source archive and wheel install successfully; checksums are generated; no state/secrets ship.
8. A maintainer reviews artifacts and generated release notes before publishing the draft.

The workflow triggers on `v*`, reuses CI, checks version/changelog, builds wheel and source
archive, writes SHA256SUMS and creates a **draft GitHub Release** using `gh`. It never deploys
infrastructure and does not publish to PyPI. Actions are pinned to verified commit SHAs;
Dependabot proposes updates. The release job alone gets `contents: write` and uses the
configured environment. Publishing a draft is a separate maintainer decision.

If PyPI is added later, check package-name availability first, set up Trusted Publishing,
use a protected environment, produce provenance and verify installability before publication.
No registry token is included. Terraform binaries/providers are not bundled or relicensed.

## Dependency updates

`pyproject.toml` defines compatibility ranges; `requirements.lock` records the versions exercised
in the development environment and is used as a constraints file in CI. It is a version snapshot,
not a hash-locked, fully cross-platform resolver output. Validate the Python matrix on every
update. Re-resolve a clean environment, run the audit and tests, and regenerate the snapshot
with `pip freeze --exclude-editable > requirements.lock`.
Do not blindly freeze an environment containing unrelated packages or credentials in URLs.

## Versioning

Use patch releases for compatible fixes, minor releases for features (or documented breaks
while pre-1.0), and major releases for breaks after 1.0. Never silently reinterpret existing
catalog/run schemas. Mark unsupported run versions and provide migration instructions.
There is no automatic run-store migration in v0.1.
