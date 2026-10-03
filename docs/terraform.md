# Terraform operations

## Execution contract

The adapter runs fixed argument arrays with no shell:

1. `terraform init -input=false -no-color`
2. `terraform validate -no-color`
3. `terraform plan -input=false -no-color -lock-timeout=60s -out=tfplan`
4. `terraform show -json tfplan` for action-policy evaluation
5. After approval, `terraform apply -input=false -no-color -lock-timeout=60s tfplan`

The generated root, provider lock file, proposal, saved plan and additional root configuration
files are fingerprinted. Approval fails if these files change, the plan expires, or its execution
has already been attempted. Terraform also detects stale plans against changed state.

The CLI action summary deliberately excludes values and outputs. Before approval, inspect the
configuration with `forgeiac show RUN_ID`, and the detailed changes locally:

```bash
terraform -chdir=.forgeiac/runs/RUN_ID show tfplan
```

This detailed review matters: `update` is not automatically safe. It may restart a service,
change networking, alter access or incur cost. The built-in policy blocks deletion/replacement,
unknown actions, incomplete plans and more than 20 changed resources. It does not implement
cost, IAM, compliance or availability policy. Add reviewed policy checks before using additional
production blueprints. No unrestricted override or destroy command is included.

## Credentials and subscriptions

Use `az login` for local Azure development, or standard Azure workload identity environment
variables in a controlled runner. The Azure example requires an explicit subscription UUID in
its reviewed parameters. Do not store secrets in a catalog, template, prompt, plan report or Git.

ForgeIaC inherits credentials for the execution process. It does not vend credentials or set
up a workload identity. `TF_CLI_ARGS*` and non-default `TF_WORKSPACE` are rejected because they
can alter reviewed behavior. Keep the executable, Terraform CLI configuration, plugin cache,
backend configuration and execution environment trusted. Per-run directories already isolate
state; Terraform CLI workspaces are not supported by this release.

## Persistent state and team use

Local state is useful for the no-cloud demo and one operator. Back it up privately and retain
`.forgeiac` between sessions. Losing state does not delete real infrastructure.

For a team, add a remote backend to an approved catalog template before the first plan. Example
fragment to merge under `template.terraform` (replace literal storage values):

```json
{
  "backend": {
    "azurerm": {
      "resource_group_name": "platform-state-rg",
      "storage_account_name": "YOUR_UNIQUE_STATE_ACCOUNT",
      "container_name": "tfstate",
      "key": "team-dev-resource-group.tfstate",
      "use_azuread_auth": true
    }
  }
}
```

Create and secure the backend outside this project; use Azure RBAC, encryption, private access
as needed, state versioning and recovery procedures. Give each independent stack a unique,
reviewed state key. Do not use one fixed key for many different runs. Backend credentials must
come from workload identity/environment, not this JSON. State migration from an existing local
run is an explicit operator task using Terraform's documented migration workflow; ForgeIaC does
not run `init -migrate-state` automatically.

Commit reviewed provider lock files for reproducible team catalogs/workflows. The CLI creates
a per-run `.terraform.lock.hcl`; subsequent init reuses it and plan approval fingerprints it.
A new run resolves the catalog's version constraints again. Catalog constraints alone are not
an exact dependency lock.

## Failures and recovery

Provider failures can leave partially created resources. Inspect the private `last-error.log`,
cloud console and state. Repair permissions/configuration, then run `plan` on the same run.
Never delete the run and blindly retry with a new state. `revise` changes parameters while
retaining state and prohibits changes to name, namespace or subscription identity.

For drift, run `plan` on the existing run and review the result; nothing applies automatically.
For deletion, use an organization's explicit Terraform decommissioning process. The Azure
example also sets `prevent_destroy`. The agent does not remove that protection.
