"""Standalone entry point for the nanoRAG MCP server."""

from __future__ import annotations

from mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
