# Crossplane setup and GitOps delivery

## Prerequisites

The included example targets Crossplane v2 namespaced XRs and namespaced Azure managed
resources. Before making requests, a platform administrator must supply:

- A working Crossplane v2 control plane and a namespace such as `platform`.
- A reviewed Azure provider version exposing `azure.m.upbound.io/v1beta1 ResourceGroup`.
  Upbound provider-family-azure v2.5.2 documents that API; select and pin a version compatible
  with your control plane and organizational support/licensing requirements.
- Activation of that MR API if your provider uses ManagedResourceActivationPolicy.
- A `function-patch-and-transform` Function, pinned to your approved release.
- A namespaced `azure.m.upbound.io/v1beta1 ProviderConfig` named `default` (or your chosen name),
  authenticated for the target Azure subscription. Credential setup is deliberately outside
  the developer request API. Use your existing workload identity or secret integration.
- The XRD and Composition under `examples/crossplane`, deployed through your platform GitOps
  process. Composition templates use `deletionPolicy: Orphan` to avoid deleting the cloud group
  when the MR is removed; this may leave billable resources and is not an ownership backup.

No providers, credentials, namespaces or cluster permissions are silently installed by the agent.
The resource group's Azure external name follows the XR name; keep it unique within the
subscription, including across Kubernetes namespaces.

Read-only prerequisite checks (replace context/namespace):

```bash
kubectl --context YOUR_CONTEXT get providers.pkg.crossplane.io
kubectl --context YOUR_CONTEXT get functions.pkg.crossplane.io
kubectl --context YOUR_CONTEXT api-resources --api-group=azure.m.upbound.io
kubectl --context YOUR_CONTEXT get providerconfigs.azure.m.upbound.io -n platform
kubectl --context YOUR_CONTEXT get xrd xresourcegroups.platform.forgeiac.dev
kubectl --context YOUR_CONTEXT get composition forgeiac-azure-resource-group
```

Review your installed CRD schema before relying on an example. The Kubernetes server dry-run
will fail if versions, schema, namespace, RBAC or admission requirements do not match.

## Platform manifests

`examples/crossplane/kustomization.yaml` includes only the XRD and Composition. Reference this
base from your Flux/Argo platform root once the provider and function are healthy. The generated
XRD must be Established before the first XR request. If your Compositions are Helm packages,
put equivalent reviewed manifests in your existing chart and point the catalog at its API.

The example composes an Azure ResourceGroup, patches location, environment and ProviderConfig,
and maps the XR name to the cloud external name. The XR includes its Composition selection
under `spec.crossplane`. The XRD enforces the example Composition.

## Plan and export

`plan --context NAME` reads cluster identity and namespace UID, performs server-side dry-run,
and saves a Kubernetes object diff. RBAC must allow reading the namespace and resource plus the
verbs required for server-side apply/diff. Dry-run enforces admission but does not provision
cloud resources and cannot show the cloud consequences of Composition reconciliation.

```bash
cat .forgeiac/runs/RUN_ID/kubernetes.diff
forgeiac export RUN_ID --approve FULL_DIGEST --destination ../gitops/clusters/dev/my-rg
```

The destination must be new to avoid overwriting existing GitOps files. It contains a
`resource.json` and `kustomization.yaml` (JSON is valid YAML). Add its relative directory to the
parent Kustomization, create a branch/PR, and merge under repository policy. The agent does not
track your Git remote or verify that Flux watches a particular path; that wiring is your
platform's responsibility.

Flux/Argo service accounts and Kubernetes admission policies remain authoritative. Apply
Kyverno constraints to allowed XR types, namespaces, tags and regions if these are mandatory
platform rules; CLI validation alone can always be bypassed by another client.

## Direct mode and observation

For a sandbox you can explicitly use `apply --direct`. It submits the XR using server-side
apply with field manager `forgeiac` and does not force conflicts. Do not directly apply an XR
already managed by Flux/Argo. If ownership conflicts occur, reconcile through the owning tool.

`status --wait 600` observes Ready and Synced conditions, checks that desired spec fields are
present, and checks observedGeneration when the controller supplies it. It reports conditions
without connection secrets. Controllers may briefly retain older conditions; reported readiness
is not an independent cloud/application health check. Run your normal cloud validation after
provisioning. A timeout does not delete or roll back the resource; inspect Crossplane events.

For existing v1 claims, add your own namespaced claim catalog entry with the exact claim schema.
Do not translate old cluster-scoped MRs to namespaced APIs without an explicit migration plan.

## Optional bootstrap samples

For a fresh sandbox, `examples/crossplane/bootstrap/packages.yaml` supplies pinned Provider and
Function objects (Azure family v2.6.0; patch-and-transform v0.11.0). These are explicit example
pins, not a tested compatibility matrix or an instruction to upgrade an existing installation.
They are excluded from the main Kustomization to avoid unexpectedly changing your platform.
Review and include them in your platform's package-install GitOps layer if needed; wait for both
packages to be Healthy, and activate the MR API if required by that provider/control plane.

`bootstrap/provider-config.yaml` references an existing Secret in `platform`. Your existing
External Secrets/secret manager can create that Secret with key `credentials`, whose value is
the provider's Azure service-principal JSON (`clientId`, `clientSecret`, `subscriptionId`,
`tenantId`). The service principal must have the required Azure permissions; do not commit that
JSON. This is a sandbox secret-reference example; use your platform's workload identity
configuration for production. Include ProviderConfig only after its CRD exists and the namespace
and Secret are present. Then deploy the XRD/Composition layer, wait for XRD establishment, and
finally submit the developer XR through GitOps.
