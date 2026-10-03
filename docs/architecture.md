# Architecture and boundaries

## What is an agent here?

ForgeIaC is a bounded infrastructure workflow, with optional model reasoning at its entry.
It is intentionally not an autonomous shell loop. The user supplies intent; the model chooses
an approved capability and parameters; deterministic code validates and renders; the operator
reviews and authorizes; Terraform or Crossplane reconciles infrastructure.

This makes successful provisioning depend primarily on tested platform APIs, rather than a
model's ability to invent an entire correct Terraform module or Composition.

## Components

| Component | Responsibility | Authority |
|---|---|---|
| CLI | Request, inspect, plan, revise, approve, apply, export, observe | Local operator |
| LangChain adapter | Select catalog ID and typed parameters | No tools or execution |
| Catalog | Parameter schema and trusted template | Reviewed repository code |
| SQLite FTS5 | Retrieve approved docs with source references | Context only |
| Renderer | Exact-value placeholder substitution into JSON | No template language execution |
| Terraform adapter | init, validate, saved plan, policy inspection, apply | Operator cloud identity |
| Crossplane adapter | Server dry-run, object diff, optional apply, status | Explicit Kubernetes context |
| GitOps export | XR and Kustomization in a new directory | No GitHub authentication or remote writes |
| Run store | State, plans, approval receipts, events | Private local files |
| MCP server | Catalog, pure proposal, search | No plan/apply/approval tools |

## Why no vector database yet?

The starter corpus is small, owned and terminology-heavy. FTS5 gives deterministic local
retrieval and source citations without another service. Retrieval only enriches intent mapping;
it cannot add executable blueprints. The adapter returns `[{source, text}]`, making future
Qdrant, pgvector or hybrid retrieval straightforward without changing the execution engine.
Measure wrong-blueprint selection and missing-field rates before adding that dependency.

## State model

`request` creates a random run ID and immutable-at-review proposal. `revise` retains the run's
Terraform state while invalidating its previous plan. `plan` validates and records a digest of
inputs, relevant files, target and creation time. `apply` requires the full digest and records
an execution attempt before contacting the provider. Failed attempts require a new plan.

Each run is one independently locked Terraform root, not a complete multi-user orchestration
service. Separate runs are not deduplicated. Repeating a request may attempt to create the same
cloud resource: retain run IDs and use `revise` for updates. Do not point multiple runs at the
same backend state key. Do not let Terraform and Crossplane manage the same cloud object.

A saved plan protects the reviewed actions; Terraform's own state lock and stale-plan checks
protect its state. A local one-hour receipt is not a signed authorization, identity proof,
multi-person approval, distributed lock or tamper-proof audit trail.

## Existing platform integration

For Helm-packaged Compositions delivered by Flux, maintain that distribution unchanged.
Add catalog templates emitting your exact XRD version, kind and parameters. Developers request
an XR, review the resulting GitOps PR, and the existing control plane reconciles it.
Crossplane v1 claims may be added as namespaced catalog templates; the included API and examples
are v2 namespaced XRs. Cluster-scoped resources are intentionally outside this release's request
renderer. There is no automatic v1/v2 schema inference or import/adoption logic.

Terraform module consumers add a reviewed template with a `module` block and pinned source.
Models fill schema-controlled inputs only. Provider/module installation during `init` executes
trusted third-party code: a catalog is executable supply-chain material, not arbitrary RAG text.

## What belongs outside v0.1

Production authentication/RBAC, tenant isolation, remote approval services, cloud cost estimates,
automatic PR creation, background workers, provider discovery, live XRD schema ingestion,
self-healing changes, destroy/import workflows, and embedding retrieval are roadmap items.
Use repository protections, workload identity, locked remote state, restricted execution workers
and cluster admission policy to supply organizational controls today.
