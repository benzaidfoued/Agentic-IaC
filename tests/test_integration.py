"""Real Terraform plan/apply/update with built-in terraform_data; no cloud access."""

import shutil

import pytest

from forgeiac.cli import main
from forgeiac.engine import apply, plan, status


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("terraform") is None, reason="Terraform not installed")
def test_real_terraform_lifecycle(store, tf_run):
    receipt = plan(store, tf_run)
    assert receipt["summary"][0]["actions"] == ["create"]
    apply(store, tf_run, receipt["approval"])
    assert status(store, tf_run)["status"] == "applied"
    receipt = plan(store, tf_run)
    assert receipt["summary"][0]["actions"] == ["no-op"]
    from conftest import ROOT

    assert (
        main(
            [
                "--home",
                str(store.root),
                "--catalog",
                str(ROOT / "catalog"),
                "revise",
                tf_run,
                "--set",
                "environment=staging",
            ]
        )
        == 0
    )
    receipt = plan(store, tf_run)
    assert receipt["summary"][0]["actions"] == ["update"]
    apply(store, tf_run, receipt["approval"])
    assert status(store, tf_run)["status"] == "applied"
