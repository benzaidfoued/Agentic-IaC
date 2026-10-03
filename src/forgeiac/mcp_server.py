"""Stdio MCP interface exposes catalog and pure proposals, never provisioning tools."""

import os

from .core import default_catalog, load_catalog, propose
from .knowledge import search


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit('Install MCP extras: pip install -e ".[mcp]"') from exc
    server = FastMCP("ForgeIaC")
    catalog_path = os.getenv("FORGEIAC_CATALOG", default_catalog())
    knowledge_path = os.getenv("FORGEIAC_KNOWLEDGE", ".forgeiac/knowledge.db")

    @server.tool()
    def list_blueprints() -> list[dict]:
        """List approved infrastructure offerings and their input schemas."""
        return [
            {key: value for key, value in entry.items() if key != "template"}
            for entry in load_catalog(catalog_path).values()
        ]

    @server.tool()
    def propose_infrastructure(blueprint: str, parameters: dict) -> dict:
        """Render a validated proposal. Does not save, plan, approve or apply anything."""
        return propose(load_catalog(catalog_path), blueprint, parameters)

    @server.tool()
    def search_knowledge(query: str) -> list[dict]:
        """Retrieve locally indexed documentation with source references."""
        return search(knowledge_path, query)

    return server


def main():
    build_server().run(transport="stdio")
