# Add your infrastructure offerings

A catalog is trusted repository code. Every file is a JSON object with:

| Field | Meaning |
|---|---|
| `id` | Unique lowercase blueprint ID |
| `description` | Model-visible explanation, scope and intended use |
| `engine` | `terraform` or `crossplane` |
| `parameters` | JSON Schema, with `additionalProperties: false` |
| `template` | Terraform JSON configuration or a single namespaced Kubernetes resource |

Copy a starter entry, give it a unique ID, and replace its schema/template. A placeholder such
as `"{{location}}"` must occupy the entire JSON string and replaces it with the original typed
parameter value. Dicts, lists, numbers and booleans keep their types. There are no loops,
includes, dynamic code or string interpolation. Unknown/missing fields fail validation.
Terraform `${...}` and `%{...}` expressions are forbidden in supplied parameter values; reviewed
catalog templates can contain normal Terraform expressions.

Use enums for approved regions/SKUs, bounded integers for capacity, regexes for identifiers,
explicit required fields, and defaults only when operationally safe. Secret parameters are not
supported. Refer to a namespaced ProviderConfig or use Terraform identity from the environment.

## Existing Terraform modules

Example template fragment, after you add matching strict parameters:

```json
{
  "terraform": {"required_version": ">= 1.9.0, < 2.0.0"},
  "module": {
    "database": {
      "source": "git::https://github.com/YOUR_ORG/terraform-database.git?ref=FULL_COMMIT_SHA",
      "name": "{{name}}",
      "location": "{{location}}",
      "ha_enabled": "{{ha_enabled}}"
    }
  }
}
```

Replace that source before use. Review its dependencies and backend/provider configuration.
Model-generated module URLs, provider versions, provisioners, external data sources, shell
commands and IAM documents are not accepted parameters unless you deliberately expose them;
do not expose them. A malicious catalog can execute arbitrary provider/module behavior.

## Existing Crossplane APIs

Set the template's apiVersion/kind to your installed claim/XR and align parameters with its
schema. Set metadata.namespace explicitly. Crossplane owns the composed MRs; request the XR,
not individual MRs. The included blueprint targets only its accompanying sample XRD, not your
private Compositions automatically. Use `--catalog /path/to/your/catalog` for another catalog.

## Contribution acceptance criteria

Each offering must include a documented owner/use case, reviewed schema, supported versions,
minimal privilege requirements, cost/destruction implications, sample request, positive and
negative schema tests, and evidence of sandbox provisioning. Cloud validation evidence must be
redacted and identify tested provider versions. Run the full no-cloud regression suite.
Do not claim broad cloud support from a single resource example.
