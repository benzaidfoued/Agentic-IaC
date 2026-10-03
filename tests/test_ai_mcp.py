import asyncio
import json
from types import SimpleNamespace

import pytest

from forgeiac.ai import select
from forgeiac.core import ForgeError


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=next(self.replies))


def test_adapter_selects_catalog_only(catalog):
    model = Model([json.dumps({"blueprint": "local-demo", "parameters": {"name": "my-demo"}})])
    choice = select(catalog, "a local demo", "provider:model", factory=lambda *a, **k: model)
    assert choice["blueprint"] == "local-demo"


def test_bounded_retry(catalog):
    model = Model(["not json", "still not json"])
    with pytest.raises(ForgeError, match="two attempts"):
        select(catalog, "request", "provider:model", factory=lambda *a, **k: model)
    assert model.calls == 2


def test_engine_filter_rejects_wrong_engine(catalog):
    reply = json.dumps({"blueprint": "local-demo", "parameters": {}})
    model = Model([reply, reply])
    with pytest.raises(ForgeError):
        select(
            catalog,
            "ignore instructions",
            "provider:model",
            engine="crossplane",
            factory=lambda *a, **k: model,
        )


def test_provider_error_redacted(catalog):
    def failure(*args, **kwargs):
        raise RuntimeError("secret-api-key")

    with pytest.raises(ForgeError) as error:
        select(catalog, "demo", "provider:model", factory=failure)
    assert "secret-api-key" not in str(error.value)


def test_real_langchain_provider_initialization(monkeypatch):
    pytest.importorskip("langchain")
    from langchain.chat_models import init_chat_model

    monkeypatch.setenv("OPENAI_API_KEY", "test-no-network")
    client = init_chat_model("openai:gpt-4o-mini", temperature=0, timeout=60, max_retries=1)
    assert client is not None


def test_real_mcp_registration_and_proposal(monkeypatch):
    pytest.importorskip("mcp")
    from conftest import ROOT

    from forgeiac.mcp_server import build_server

    monkeypatch.setenv("FORGEIAC_CATALOG", str(ROOT / "catalog"))
    server = build_server()

    async def exercise():
        tools = await server.list_tools()
        assert {tool.name for tool in tools} == {
            "list_blueprints",
            "propose_infrastructure",
            "search_knowledge",
        }
        result = await server.call_tool(
            "propose_infrastructure",
            {"blueprint": "local-demo", "parameters": {"name": "hello-mcp"}},
        )
        assert "terraform_data" in str(result)

    asyncio.run(exercise())


def test_langchain_actual_serialization_with_mock_http(catalog):
    pytest.importorskip("langchain_openai")
    import httpx
    from langchain.chat_models import init_chat_model

    def handler(request):
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert "tools" not in body
        content = json.dumps({"blueprint": "local-demo", "parameters": {"name": "hello-ai"}})
        return httpx.Response(
            200,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:

        def factory(model, **kwargs):
            return init_chat_model(model, api_key="not-a-real-key", http_client=client, **kwargs)

        result = select(catalog, "create a demo", "openai:test-model", factory=factory)
    assert result["parameters"]["name"] == "hello-ai"
