"""Trusted catalog loading, strict parameter validation and deterministic rendering."""

import copy
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


class ForgeError(Exception):
    """An actionable failure safe to present without credentials or model output."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def default_catalog():
    """Prefer the repository catalog; installed wheels include the starter catalog."""
    local = Path("catalog")
    return str(local if local.is_dir() else Path(__file__).parent / "catalog")


def load_catalog(directory):
    catalog = {}
    for path in sorted(Path(directory).glob("*.json")):
        entry = json.loads(path.read_text())
        for key in ("id", "description", "engine", "parameters", "template"):
            if key not in entry:
                raise ForgeError(f"Catalog {path.name}: missing {key}")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", entry["id"]):
            raise ForgeError("Invalid catalog ID")
        if entry["id"] in catalog or entry["engine"] not in ("terraform", "crossplane"):
            raise ForgeError("Duplicate catalog ID or unsupported engine")
        if entry["parameters"].get("additionalProperties") is not False:
            raise ForgeError("Catalog parameter schema must forbid additional properties")
        Draft202012Validator.check_schema(entry["parameters"])
        catalog[entry["id"]] = entry
    if not catalog:
        raise ForgeError(f"No catalog JSON files in {directory}")
    return catalog


def render(entry, supplied):
    params = copy.deepcopy(supplied)
    for key, schema in entry["parameters"].get("properties", {}).items():
        if key not in params and "default" in schema:
            params[key] = copy.deepcopy(schema["default"])
    errors = sorted(
        Draft202012Validator(entry["parameters"]).iter_errors(params),
        key=lambda err: str(list(err.path)),
    )
    if errors:
        # Do not reflect user-provided values, which could contain secrets.
        details = [
            f"{'.'.join(map(str, e.path)) or 'parameters'}: {e.validator} constraint"
            for e in errors
        ]
        missing = [key for key in entry["parameters"].get("required", []) if key not in params]
        raise ForgeError(
            "Invalid parameters: "
            + "; ".join(details)
            + (f". Supply missing fields: {', '.join(missing)}" if missing else "")
        )

    def expand(value):
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            key = value[2:-2].strip()
            if key not in params:
                raise ForgeError(f"Template references unknown parameter: {key}")
            return copy.deepcopy(params[key])
        return value

    # Parameters are data, never Jinja, Python, shell, or arbitrary Terraform expressions.
    if re.search(r"\$\{|%\{", json.dumps(params)):
        raise ForgeError("Template expressions are forbidden in parameter values")
    artifact = expand(entry["template"])
    if entry["engine"] == "crossplane":
        if not artifact.get("metadata", {}).get("namespace"):
            raise ForgeError("Crossplane blueprints must emit a namespaced resource")
        if artifact.get("kind") in {"Secret", "ProviderConfig", "ClusterRole", "Composition"}:
            raise ForgeError("Administrative/credential resources cannot be requested")
    return params, artifact


def propose(catalog, blueprint, parameters):
    if blueprint not in catalog:
        raise ForgeError("Unknown blueprint; run forgeiac catalog")
    entry = catalog[blueprint]
    params, artifact = render(entry, parameters)
    return {
        "schema_version": 1,
        "blueprint": blueprint,
        "engine": entry["engine"],
        "catalog_digest": digest(entry),
        "parameters": params,
        "artifact": artifact,
    }
