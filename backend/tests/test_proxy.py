"""End-to-end integration test for MCP streamable-http proxy flow.

Validates the full proxy chain: auth → initialize → tool call → response.
Requires the MCP server to be running on the configured MCP_HTTP_URL.
Skip with: pytest -m "not integration"
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.skip(reason="Requires running MCP server — run manually via: uv run python -m pytest tests/test_proxy.py -v -s")
class TestMCPProxyEndToEnd:
    """End-to-end tests validating the full proxy chain.

    Prerequisites:
      - MCP server running: uv run --directory backend python mcp_server_start.py
      - Backend running: uv run --directory backend uvicorn api.main:app --port 8000
      - .env: MCP_TRANSPORT=streamable-http, MCP_API_KEY set
    """

    async def test_proxy_initialize_session(self):
        """POST /mcp with initialize → 200 + serverInfo."""
        import httpx
        from config import get_settings

        settings = get_settings()
        api_key = settings.mcp_api_key
        base = "http://localhost:8000"

        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{base}/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "X-API-Key": api_key,
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "1"},
                    },
                    "id": 1,
                },
            )
            assert r.status_code == 200
            body = r.text
            assert "nanoRAG" in body
            assert "serverInfo" in body

    async def test_proxy_health_tool(self):
        """Initialize session + call nanorag_health → status ok."""
        import httpx
        from config import get_settings

        settings = get_settings()
        api_key = settings.mcp_api_key
        base = "http://localhost:8000"

        async with httpx.AsyncClient() as c:
            # Initialize
            r = await c.post(
                f"{base}/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "X-API-Key": api_key,
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "1"},
                    },
                    "id": 1,
                },
            )
            assert r.status_code == 200
            sid = r.headers.get("mcp-session-id")
            assert sid, f"No mcp-session-id in headers: {dict(r.headers)}"

            # Call health tool
            r2 = await c.post(
                f"{base}/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "X-API-Key": api_key,
                    "mcp-session-id": sid,
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "nanorag_health", "arguments": {}},
                    "id": 2,
                },
            )
            assert r2.status_code == 200
            assert "indexed_chunks" in r2.text
            assert "status" in r2.text
