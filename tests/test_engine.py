import json
import time

import pytest

from forgeiac.core import ForgeError, digest
from forgeiac.engine import apply, export_gitops, inspect_changes, plan, status, verify
from forgeiac.store import write_json


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.server = "https://cluster-a"
        self.fail_apply = False

    def __call__(self, argv, cwd, **kwargs):
        self.calls.append(argv)
        if argv[0] == "terraform":
            if argv[1] == "plan":
                (cwd / "tfplan").write_bytes(b"saved-plan")
            if argv[1] == "show":
                return json.dumps(
                    {
                        "format_version": "1.2",
                        "resource_changes": [
                            {"address": "terraform_data.demo", "change": {"actions": ["create"]}}
                        ],
                    }
                )
            if argv[1] == "apply" and self.fail_apply:
                raise ForgeError("simulated provider failure")
        if "config" in argv:
            return json.dumps({"clusters": [{"cluster": {"server": self.server}}]})
        if "namespace" in argv:
            return json.dumps({"metadata": {"uid": "namespace-uid"}})
        if "get" in argv and "-f" in argv:
            obj = json.loads((cwd / "resource.json").read_text())
            obj["status"] = {
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "Synced", "status": "True"},
                ]
            }
            return json.dumps(obj)
        return ""


def test_exact_saved_plan_and_replay(store, tf_run):
    runner = FakeRunner()
    receipt = plan(store, tf_run, runner=runner)
    result = apply(store, tf_run, receipt["approval"], runner=runner)
    assert result["status"] == "applied"
    assert runner.calls[-1][-1] == "tfplan"
    assert "-auto-approve" not in runner.calls[-1]
    with pytest.raises(ForgeError, match="already used"):
        apply(store, tf_run, receipt["approval"], runner=runner)


@pytest.mark.parametrize(
    "actions", [["delete"], ["delete", "create"], ["create", "delete"], ["forget"], ["unknown"]]
)
def test_destructive_and_unknown_policy(actions):
    with pytest.raises(ForgeError):
        inspect_changes(
            {
                "format_version": "1.0",
                "resource_changes": [{"address": "x", "change": {"actions": actions}}],
            }
        )


def test_scope_limit():
    with pytest.raises(ForgeError, match="at most"):
        inspect_changes(
            {
                "format_version": "1.0",
                "resource_changes": [
                    {"address": str(i), "change": {"actions": ["create"]}} for i in range(21)
                ],
            }
        )


@pytest.mark.parametrize(
    "extra", [{"format_version": "2.0"}, {"complete": False}, {"errored": True}]
)
def test_incomplete_or_unsupported_plan(extra):
    with pytest.raises(ForgeError):
        inspect_changes({"format_version": "1.0", **extra})


def test_modified_artifact_blocks_apply(store, tf_run):
    runner = FakeRunner()
    receipt = plan(store, tf_run, runner=runner)
    (store.path(tf_run) / "main.tf.json").write_text("{}")
    with pytest.raises(ForgeError, match="changed"):
        apply(store, tf_run, receipt["approval"], runner=runner)
    assert not any(c[1] == "apply" for c in runner.calls)


def test_added_terraform_file_blocks_apply(store, tf_run):
    receipt = plan(store, tf_run, runner=FakeRunner())
    (store.path(tf_run) / "other.tf").write_text("# a change")
    with pytest.raises(ForgeError, match="changed"):
        verify(store, tf_run, receipt["approval"])


def test_wrong_approval(store, tf_run):
    plan(store, tf_run, runner=FakeRunner())
    with pytest.raises(ForgeError, match="does not match"):
        verify(store, tf_run, "wrong")


def test_expired_approval(store, tf_run):
    receipt = plan(store, tf_run, runner=FakeRunner())
    receipt.pop("approval")
    receipt["created_at"] = time.time() - 4000
    receipt["approval"] = digest(receipt)
    write_json(store.path(tf_run) / "plan.json", receipt)
    with pytest.raises(ForgeError, match="expired"):
        verify(store, tf_run, receipt["approval"])


def test_failure_consumes_plan(store, tf_run):
    runner = FakeRunner()
    receipt = plan(store, tf_run, runner=runner)
    runner.fail_apply = True
    with pytest.raises(ForgeError):
        apply(store, tf_run, receipt["approval"], runner=runner)
    assert store.read(tf_run, "applied.json")["status"] == "failed"
    with pytest.raises(ForgeError, match="already used"):
        verify(store, tf_run, receipt["approval"])


def test_crossplane_default_export(store, xr_run, tmp_path):
    runner = FakeRunner()
    receipt = plan(store, xr_run, "dev-cluster", runner)
    assert receipt["summary"]["cloud_plan"] is False
    assert any("--dry-run=server" in call for call in runner.calls)
    with pytest.raises(ForgeError, match="GitOps"):
        apply(store, xr_run, receipt["approval"], runner=runner)
    target = tmp_path / "gitops" / "my-resource"
    export_gitops(store, xr_run, receipt["approval"], target)
    assert (target / "resource.json").exists()
    assert json.loads((target / "kustomization.yaml").read_text())["resources"] == ["resource.json"]
    with pytest.raises(ForgeError, match="must not exist"):
        export_gitops(store, xr_run, receipt["approval"], target)


def test_crossplane_requires_context(store, xr_run):
    with pytest.raises(ForgeError, match="context"):
        plan(store, xr_run, runner=FakeRunner())


def test_crossplane_changed_target(store, xr_run):
    runner = FakeRunner()
    receipt = plan(store, xr_run, "dev-cluster", runner)
    runner.server = "https://other-cluster"
    with pytest.raises(ForgeError, match="target changed"):
        apply(store, xr_run, receipt["approval"], direct=True, runner=runner)


def test_crossplane_submit_then_readiness(store, xr_run):
    runner = FakeRunner()
    receipt = plan(store, xr_run, "dev-cluster", runner)
    assert (
        apply(store, xr_run, receipt["approval"], direct=True, runner=runner)["status"]
        == "submitted"
    )
    assert status(store, xr_run, runner)["status"] == "ready"


def test_apply_requires_plan(store, tf_run):
    with pytest.raises(ForgeError, match="preceding step"):
        apply(store, tf_run, "not-a-plan")


def test_lock(store, tf_run):
    with store.lock(tf_run):
        with pytest.raises(ForgeError, match="active"):
            with store.lock(tf_run):
                pass


def test_plan_retains_last_apply_status(store, tf_run):
    runner = FakeRunner()
    receipt = plan(store, tf_run, runner=runner)
    apply(store, tf_run, receipt["approval"], runner=runner)
    plan(store, tf_run, runner=runner)
    assert status(store, tf_run)["status"] == "applied"


def test_stale_condition_generation_is_not_ready(store, xr_run):
    base = FakeRunner()
    plan(store, xr_run, "dev-cluster", base)

    def runner(argv, cwd, **kwargs):
        output = base(argv, cwd, **kwargs)
        if "get" in argv and "-f" in argv:
            obj = json.loads(output)
            obj["metadata"]["generation"] = 2
            obj["status"]["conditions"][0]["observedGeneration"] = 1
            return json.dumps(obj)
        return output

    assert status(store, xr_run, runner)["status"] == "reconciling"
