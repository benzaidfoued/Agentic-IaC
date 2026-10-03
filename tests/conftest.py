from pathlib import Path

import pytest

from forgeiac.core import load_catalog, propose
from forgeiac.store import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog():
    return load_catalog(ROOT / "catalog")


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "private")


@pytest.fixture
def tf_run(store, catalog):
    return store.create(propose(catalog, "local-demo", {"name": "hello-world"}))


@pytest.fixture
def xr_run(store, catalog):
    return store.create(
        propose(
            catalog,
            "azure-resource-group-xr",
            {"name": "hello-cloud", "namespace": "platform", "location": "canadacentral"},
        )
    )
