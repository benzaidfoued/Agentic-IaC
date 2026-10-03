import copy
import json

import pytest

from forgeiac.cli import main
from forgeiac.core import ForgeError, load_catalog, propose, render
from forgeiac.knowledge import index_docs, search


@pytest.mark.parametrize(
    "blueprint,params",
    [
        ("local-demo", {"name": "demo-name"}),
        (
            "azure-resource-group-tf",
            {
                "name": "demo-name",
                "location": "canadacentral",
                "subscription_id": "00000000-0000-0000-0000-000000000000",
            },
        ),
        (
            "azure-resource-group-xr",
            {"name": "demo-name", "namespace": "platform", "location": "canadacentral"},
        ),
    ],
)
def test_starter_blueprints(catalog, blueprint, params):
    result = propose(catalog, blueprint, params)
    assert "{{" not in json.dumps(result["artifact"])
    assert result["parameters"]["environment"] == "dev"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"name": "okay-name", "arbitrary_command": "rm -rf /"},
        {"name": "../../escape"},
        {"name": "$(touch /tmp/bad)"},
        {"name": 123},
        {"name": "hello-world", "environment": "unknown"},
    ],
)
def test_invalid_parameters(catalog, params):
    with pytest.raises(ForgeError):
        propose(catalog, "local-demo", params)


def test_expression_injection(catalog):
    entry = copy.deepcopy(catalog["local-demo"])
    entry["parameters"]["properties"]["name"] = {"type": "string"}
    with pytest.raises(ForgeError, match="expressions"):
        render(entry, {"name": '${file("secret")}'})


def test_no_catalog_mutation(catalog):
    before = copy.deepcopy(catalog)
    propose(catalog, "local-demo", {"name": "hello-world"})
    assert before == catalog


def test_unknown_blueprint(catalog):
    with pytest.raises(ForgeError):
        propose(catalog, "invented", {})


def test_empty_catalog(tmp_path):
    with pytest.raises(ForgeError):
        load_catalog(tmp_path)


def test_rag_sources_and_reindex(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("Azure resource groups use canadacentral for this platform.")
    database = tmp_path / "knowledge.db"
    assert index_docs(docs, database) == 1
    assert index_docs(docs, database) == 1
    result = search(database, 'Azure " OR DROP TABLE chunks')
    assert result[0]["source"] == "guide.md#char-0"
    assert search(database, "!!!") == []
    assert search(tmp_path / "missing", "azure") == []


def test_cli_request_and_revise(tmp_path, capsys):
    from conftest import ROOT

    base = ["--home", str(tmp_path / "home"), "--catalog", str(ROOT / "catalog")]
    assert main(base + ["request", "--blueprint", "local-demo", "--set", "name=hello-world"]) == 0
    run_id = json.loads(capsys.readouterr().out)["run"]
    assert main(base + ["revise", run_id, "--set", "environment=staging"]) == 0
    capsys.readouterr()
    assert main(base + ["show", run_id]) == 0
    assert json.loads(capsys.readouterr().out)["parameters"]["environment"] == "staging"
    assert main(base + ["revise", run_id, "--set", "name=changed-name"]) == 2


def test_run_path_traversal(store):
    with pytest.raises(ForgeError):
        store.path("../../tmp")
