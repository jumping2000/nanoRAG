"""Standalone entry point for the nanoRAG MCP server.

Supports running the MCP app either over STDIO (default) or as a
streamable HTTP server (transport="streamable-http").
"""

from __future__ import annotations

import os
from mcp_server import mcp


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_HTTP_PORT", "8100"))
        # Configure FastMCP settings before running the streamable HTTP server
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
