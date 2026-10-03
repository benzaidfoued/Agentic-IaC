# Validation record for the delivered v0.1.0 alpha

This record describes the build environment, not a promise of universal compatibility.

| Check | Result |
|---|---|
| Python | 3.12.14 on Linux |
| Automated suite | 47 tests passed |
| Statement coverage | 86% overall |
| Real Terraform | 1.9.8, official binary with SHA256 checked |
| Real Terraform lifecycle | Built-in terraform_data create → apply → no-op → revise → update → apply |
| Azure Terraform configuration | Real provider installation and terraform validate passed; no Azure plan/apply |
| LangChain | Real provider initialization; actual HTTP serialization against mocked transport; no paid model call |
| MCP | Real v1 SDK tool registration and proposal invocation |
| Crossplane | Catalog rendering, simulated command contract, target checks, status and GitOps export tested |
| RAG | Real SQLite FTS5 indexing, retrieval, citations and reindexing tested |
| Safety tests | Invalid parameters, expression injection, destructive/unknown plans, changed files, wrong/expired/replayed approval, partial failure, concurrency and stale readiness |
| Dependency audit | No known vulnerabilities after updating pip and pytest; editable project excluded by audit |
| Packaging | Wheel and source distribution built; starter catalog bundled in wheel |
| Static checks | Ruff lint/format and YAML parsing |

The dependency snapshot is `requirements.lock`. Terraform is deliberately an external tool,
not included in the repository. Cloud accounts, Kubernetes credentials and model API keys were
not available for live acceptance tests. No Azure resources were created, no Crossplane control
plane was contacted, and no GitHub workflow was executed on GitHub during this build.

Before claiming production support, validate your exact provider/control-plane versions and
Compositions, run a sandbox request through GitOps to Ready/Synced, verify cloud state, check
least privilege and remote state recovery, then exercise your chosen model on representative
requests. GitHub CI is configured for Python 3.11–3.13; only Python 3.12 was exercised locally.
The documented controls are deliberately narrower than an enterprise multi-tenant service.
