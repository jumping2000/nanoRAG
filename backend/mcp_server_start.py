"""Standalone entry point for the nanoRAG MCP server."""

from __future__ import annotations

from mcp_runtime_config import resolve_mcp_runtime_config
from mcp_server import mcp


def main() -> None:
    config = resolve_mcp_runtime_config()
    if config.transport == "streamable-http":
        mcp.settings.host = config.http_host
        mcp.settings.port = config.http_port
        mcp.run(transport="streamable-http")
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
