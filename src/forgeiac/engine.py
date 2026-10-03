"""Fixed-argv execution, plan policy, explicit approval and readiness observation."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .core import ForgeError, digest
from .store import write_json


def command(argv, cwd, allowed=(0,), timeout=600):
    env = os.environ.copy()
    if any(key.startswith("TF_CLI_ARGS") for key in env):
        raise ForgeError("Unset TF_CLI_ARGS variables; they can change reviewed command behavior")
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_INPUT"] = "0"
    if env.get("TF_WORKSPACE", "default") != "default":
        raise ForgeError("TF_WORKSPACE must be unset/default; use a separate run per state")
    try:
        result = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        raise ForgeError(f"Executable not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ForgeError("Command timed out; inspect the target before retrying") from exc
    if result.returncode not in allowed:
        # Raw provider output can contain secrets. Keep it in the private run directory.
        log = Path(cwd) / "last-error.log"
        log.write_text(result.stdout + result.stderr)
        os.chmod(log, 0o600)
        raise ForgeError(f"{argv[0]} {argv[1]} failed ({result.returncode}); inspect {log}")
    return result.stdout


def inspect_changes(plan):
    """Fail closed on destructive actions, unknown change kinds, and excessive scope."""
    if not str(plan.get("format_version", "")).startswith("1."):
        raise ForgeError("Unsupported Terraform plan JSON format")
    if plan.get("errored") or plan.get("complete") is False:
        raise ForgeError("Terraform plan is errored or incomplete")
    changes = []
    for resource in plan.get("resource_changes", []):
        actions = resource["change"]["actions"]
        if "delete" in actions or "forget" in actions:
            raise ForgeError("Policy blocks deletion, replacement and state removal")
        if actions not in (["no-op"], ["create"], ["update"], ["read"]):
            raise ForgeError("Policy blocks unrecognized Terraform actions")
        changes.append({"address": resource["address"], "actions": actions})
    if sum(item["actions"] != ["no-op"] for item in changes) > 20:
        raise ForgeError("Policy allows at most 20 resource changes per run")
    return changes


def fingerprints(path, engine):
    names = (
        ["proposal.json", "resource.json"]
        if engine == "crossplane"
        else ["proposal.json", "tfplan", ".terraform.lock.hcl"]
    )
    if engine == "terraform":
        names += [
            p.name
            for p in path.iterdir()
            if p.name.endswith((".tf", ".tf.json", ".tfvars", ".tfvars.json"))
        ]
    return {
        name: hashlib.sha256((path / name).read_bytes()).hexdigest()
        for name in sorted(set(names))
        if (path / name).is_file()
    }


def kube_identity(context, namespace, path, runner):
    config = json.loads(
        runner(["kubectl", "--context", context, "config", "view", "--minify", "-o", "json"], path)
    )
    ns = json.loads(
        runner(["kubectl", "--context", context, "get", "namespace", namespace, "-o", "json"], path)
    )
    return digest({"clusters": config["clusters"], "namespace_uid": ns["metadata"]["uid"]})


def validate_artifact(store, run_id):
    proposal = store.read(run_id, "proposal.json")
    if proposal.get("schema_version") != 1:
        raise ForgeError("Unsupported run schema version")
    filename = "main.tf.json" if proposal["engine"] == "terraform" else "resource.json"
    if store.read(run_id, filename) != proposal["artifact"]:
        raise ForgeError("Artifact differs from proposal; use revise to make reviewed changes")
    return proposal


def plan(store, run_id, context=None, runner=command):
    with store.lock(run_id):
        path = store.path(run_id)
        proposal = validate_artifact(store, run_id)
        # Invalidate old approval even if replanning later fails.
        (path / "plan.json").unlink(missing_ok=True)
        engine = proposal["engine"]
        if engine == "terraform":
            runner(["terraform", "init", "-input=false", "-no-color"], path)
            runner(["terraform", "validate", "-no-color"], path)
            runner(
                [
                    "terraform",
                    "plan",
                    "-input=false",
                    "-no-color",
                    "-lock-timeout=60s",
                    "-out=tfplan",
                ],
                path,
            )
            raw = json.loads(runner(["terraform", "show", "-json", "tfplan"], path))
            summary = inspect_changes(raw)
            identity = None
        else:
            if not context:
                raise ForgeError("Crossplane plan requires an explicit --context")
            namespace = proposal["artifact"]["metadata"]["namespace"]
            identity = kube_identity(context, namespace, path, runner)
            runner(
                [
                    "kubectl",
                    "--context",
                    context,
                    "apply",
                    "--server-side",
                    "--field-manager=forgeiac",
                    "--dry-run=server",
                    "-f",
                    "resource.json",
                ],
                path,
            )
            # Diff is a Kubernetes object diff, not a cloud execution plan.
            diff = runner(
                [
                    "kubectl",
                    "--context",
                    context,
                    "diff",
                    "--server-side",
                    "--field-manager=forgeiac",
                    "-f",
                    "resource.json",
                ],
                path,
                allowed=(0, 1),
            )
            (path / "kubernetes.diff").write_text(diff)
            os.chmod(path / "kubernetes.diff", 0o600)
            summary = {
                "kind": proposal["artifact"]["kind"],
                "namespace": namespace,
                "name": proposal["artifact"]["metadata"]["name"],
                "cloud_plan": False,
                "diff_file": "kubernetes.diff",
            }
        receipt = {
            "engine": engine,
            "created_at": time.time(),
            "context": context,
            "target_identity": identity,
            "summary": summary,
            "files": fingerprints(path, engine),
        }
        receipt["approval"] = digest(receipt)
        write_json(path / "plan.json", receipt)
        store.event(run_id, "planned", {"approval": receipt["approval"]})
        return receipt


def verify(store, run_id, approval):
    receipt = store.read(run_id, "plan.json")
    payload = {key: value for key, value in receipt.items() if key != "approval"}
    if approval != receipt["approval"] or digest(payload) != approval:
        raise ForgeError("Approval does not match this plan")
    if not 0 <= time.time() - receipt["created_at"] <= 3600:
        raise ForgeError("Plan expired (one hour); create and review a new plan")
    if fingerprints(store.path(run_id), receipt["engine"]) != receipt["files"]:
        raise ForgeError("Artifacts changed after planning; replan and review")
    if (store.path(run_id) / "applied.json").exists():
        if store.read(run_id, "applied.json")["approval"] == approval:
            raise ForgeError("Plan already used; replan before another execution")
    return receipt


def apply(store, run_id, approval, direct=False, runner=command):
    with store.lock(run_id):
        receipt = verify(store, run_id, approval)
        path = store.path(run_id)
        if receipt["engine"] == "crossplane" and not direct:
            raise ForgeError("Crossplane defaults to GitOps; use export or explicitly --direct")
        if receipt["engine"] == "crossplane":
            namespace = receipt["summary"]["namespace"]
            identity = kube_identity(receipt["context"], namespace, path, runner)
            if identity != receipt["target_identity"]:
                raise ForgeError("Kubernetes target changed; replan")
        # Consume before execution: failures require replanning, never silent replay.
        write_json(path / "applied.json", {"status": "started", "approval": approval})
        store.event(run_id, "apply_started", {"approval": approval})
        try:
            if receipt["engine"] == "terraform":
                runner(
                    [
                        "terraform",
                        "apply",
                        "-input=false",
                        "-no-color",
                        "-lock-timeout=60s",
                        "tfplan",
                    ],
                    path,
                )
            else:
                runner(
                    [
                        "kubectl",
                        "--context",
                        receipt["context"],
                        "apply",
                        "--server-side",
                        "--field-manager=forgeiac",
                        "-f",
                        "resource.json",
                    ],
                    path,
                )
        except Exception:
            write_json(path / "applied.json", {"status": "failed", "approval": approval})
            store.event(run_id, "apply_failed")
            raise
        status = "applied" if receipt["engine"] == "terraform" else "submitted"
        write_json(path / "applied.json", {"status": status, "approval": approval})
        store.event(run_id, status)
        return {"status": status, "next": "Run status to check observed readiness"}


def export_gitops(store, run_id, approval, destination):
    with store.lock(run_id):
        receipt = verify(store, run_id, approval)
        if receipt["engine"] != "crossplane":
            raise ForgeError("GitOps export is for Crossplane; Terraform uses its saved plan")
        target = Path(destination).resolve()
        if target.exists():
            raise ForgeError("Export destination must not exist; choose a new resource directory")
        target.mkdir(parents=True)
        shutil.copyfile(store.path(run_id) / "resource.json", target / "resource.json")
        write_json(
            target / "kustomization.yaml",
            {
                "apiVersion": "kustomize.config.k8s.io/v1beta1",
                "kind": "Kustomization",
                "resources": ["resource.json"],
            },
        )
        store.event(run_id, "gitops_exported", {"approval": approval})
        return {
            "directory": str(target),
            "status": "exported",
            "next": "Include this directory in your GitOps root, review a PR and merge",
        }


def status(store, run_id, runner=command):
    proposal = store.read(run_id, "proposal.json")
    path = store.path(run_id)
    if proposal["engine"] == "terraform":
        if not (path / "applied.json").exists():
            return {"status": "not_applied"}
        applied = store.read(run_id, "applied.json")
        return {
            "status": applied["status"],
            "note": "Provider completion; use plan to detect drift",
        }
    receipt = store.read(run_id, "plan.json")
    obj = proposal["artifact"]
    identity = kube_identity(receipt["context"], obj["metadata"]["namespace"], path, runner)
    if identity != receipt["target_identity"]:
        raise ForgeError("Kubernetes target changed; replan")
    raw = json.loads(
        runner(
            [
                "kubectl",
                "--context",
                receipt["context"],
                "get",
                "-f",
                "resource.json",
                "-o",
                "json",
            ],
            path,
        )
    )
    conditions = raw.get("status", {}).get("conditions", [])
    ready = any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)
    synced = any(c["type"] == "Synced" and c["status"] == "True" for c in conditions)
    observed = raw.get("status", {}).get("observedGeneration")
    if observed is not None and observed < raw["metadata"].get("generation", 1):
        ready = False
    for condition in conditions:
        generation = condition.get("observedGeneration")
        if generation is not None and generation < raw["metadata"].get("generation", 1):
            if condition["type"] in ("Ready", "Synced"):
                ready = False
    spec_matches = _contains(raw.get("spec", {}), obj.get("spec", {}))
    return {
        "status": "ready" if ready and synced and spec_matches else "reconciling",
        "desired_spec_matches": spec_matches,
        "conditions": [
            {k: c[k] for k in ("type", "status", "reason") if k in c} for c in conditions
        ],
        "note": "Crossplane-reported readiness, not an application health check",
    }


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value) for key, value in expected.items()
        )
    return actual == expected
