# Roadmap

Shipped: CLI and bounded agent workflow, Terraform and Crossplane adapters, LangChain provider
selection, strict catalog rendering, local lexical RAG, proposal MCP, GitOps export, local audit,
real no-cloud Terraform integration test and GitHub release packaging.

Next, in priority order:

1. Sandbox cloud acceptance matrix for Azure, AWS and GCP catalog contributions.
2. Real XRD schema import with explicit catalog-review step and Composition revision pinning.
3. Provider-neutral cost reporting and external plan policy hooks (without changing approval).
4. GitHub App PR creation with minimal permissions and no merge authority.
5. Remote run/approval service, signed receipts and separate execution identity.
6. Hybrid retrieval/vector adapter with a measured request-to-blueprint evaluation dataset.
7. Backstage scaffolder integration and a small authenticated request UI.
8. OpenTofu compatibility certification and a supported executable selector.

Good first contributions: explain a troubleshooting case; add a negative schema test; contribute
a tested sandbox blueprint; improve local model JSON reliability tests; add a recorded,
redacted CLI walkthrough. No dates are commitments. Discuss broad changes before building them.
