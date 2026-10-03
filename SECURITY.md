# Security policy

## Supported versions and reporting

v0.1.x is an alpha line; fixes target the latest patch. Do not report credentials or exploitable
details in a public issue. Repository owners should enable GitHub private vulnerability
reporting before launch. Use the repository's Security → Report a vulnerability action when
available; otherwise contact its listed maintainer privately. No response SLA is promised.

## Threat model

Untrusted: request text, model output and retrieved documents. Trusted: local operator, catalog
repository, Terraform/provider binaries, kubeconfig, execution environment and GitOps reviewers.
The model has no tools and returns only a catalog ID and parameter object. Schema validation,
engine filtering and a deterministic renderer bound what gets generated.

MCP tools can read the configured catalog/docs and return proposals, but cannot execute or save
runs. Index only documents you permit the MCP client and configured AI provider to see. An
external AI request sends the prompt, catalog schemas and retrieved snippets to that provider.
Keep credentials out of all three. This release has no automated PII/secret classifier.

Approval digests detect changed local artifacts, expire in one hour and cannot be reused after
an execution attempt. They are not a cryptographic identity signature or a boundary against a
malicious user who can edit the run store. Audit events are private local JSONL, not immutable.
Do not expose the CLI as an unauthenticated network service. This is a single-operator tool.

Plans, state, generated configurations, indexed docs and provider error logs may contain
sensitive information. `.forgeiac` is private and ignored by Git. Never upload it as a public
CI artifact. Saved Terraform plans can retain plaintext secrets even when terminal output is
redacted. Review any logs before sharing. Only action names, addresses and selected Kubernetes
condition fields are printed by the execution/status path; `show` intentionally displays your
proposal and therefore depends on your catalog not accepting secrets.

For production: use workload identity and least privilege, locked encrypted remote state,
reviewed exact module/provider versions, restricted runners, protected Git branches,
server-side admission (for example Kyverno), backups and separate dev/prod identities.
No cloud-side authorization controls are installed automatically.

Crossplane dry-run does not preview cloud changes or validate external credentials. Catalog
validation is not a cloud policy engine. Terraform init/plan may execute providers, modules,
external data sources and provisioners from trusted code; neither is a sandbox for untrusted IaC.

No automated rollback, import or destroy is provided. Partial failures require operator review
and replanning against the same state. A successful apply is not proof of application health.
