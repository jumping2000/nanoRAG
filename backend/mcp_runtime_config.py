from __future__ import annotations

import os
from dataclasses import dataclass


_ALLOWED_TRANSPORTS = ("stdio", "streamable-http")


@dataclass(slots=True, frozen=True)
class MCPRuntimeConfig:
    transport: str
    http_host: str
    http_port: int


def resolve_mcp_runtime_config() -> MCPRuntimeConfig:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in _ALLOWED_TRANSPORTS:
        allowed = ", ".join(_ALLOWED_TRANSPORTS)
        raise ValueError(f"MCP_TRANSPORT must be one of: {allowed}")

    raw_port = os.getenv("MCP_HTTP_PORT", "8100").strip()
    try:
        http_port = int(raw_port)
    except ValueError as exc:
        raise ValueError("MCP_HTTP_PORT must be an integer") from exc

    if not 1 <= http_port <= 65535:
        raise ValueError("MCP_HTTP_PORT must be between 1 and 65535")

    return MCPRuntimeConfig(
        transport=transport,
        http_host="0.0.0.0",
        http_port=http_port,
    )
