"""Integration tests for the /mcp proxy endpoint — stdio and streamable-http transports."""

from __future__ import annotations

import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Pre-import mocking — avoid pulling in heavy/optional transitive deps
# ---------------------------------------------------------------------------


def _install_import_mocks():
    """Inject lightweight mocks for transitive dependencies not needed
    for testing the /mcp proxy logic.  Only mock packages that are NOT
    already installed in the environment."""
    mocks = {
        "tiktoken": MagicMock(),
        "pypdf": MagicMock(),
        "rank_bm25": MagicMock(),
        "torch": MagicMock(),
    }
    for mod_name, mock_mod in mocks.items():
        if mod_name not in sys.modules:
            sys.modules[mod_name] = mock_mod


_install_import_mocks()


# ---------------------------------------------------------------------------
# Helpers — reuse the fake runtime from test_mcp_server to avoid real init
# ---------------------------------------------------------------------------


def _fake_runtime():
    from test_mcp_server import _fake_runtime as _fr
    return _fr()


def _reload_main(monkeypatch) -> object:
    """Import (or reload) backend.api.main with a patched ingestion runtime."""
    monkeypatch.setattr("bootstrap.build_ingestion_runtime", lambda s: _fake_runtime())
    from config import get_settings
    get_settings.cache_clear()
    import backend.api.main
    return importlib.reload(backend.api.main)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stdio_env(monkeypatch):
    """Set environment for stdio transport tests."""
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    monkeypatch.setenv("MCP_HTTP_PORT", "8100")


@pytest.fixture
def streamable_http_env(monkeypatch):
    """Set environment for streamable-http transport tests."""
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    monkeypatch.setenv("MCP_HTTP_PORT", "8100")
    monkeypatch.delenv("MCP_HTTP_URL", raising=False)


@pytest.fixture
def client_stdio(stdio_env, monkeypatch):
    """Return a TestClient with stdio transport; subprocess is mocked."""
    # Create a configured mock that the startup handler will use.
    fake_manager = AsyncMock()
    fake_manager.start = AsyncMock()
    monkeypatch.setattr("mcp_subprocess.AsyncMCPSubprocess", lambda: fake_manager)
    main_mod = _reload_main(monkeypatch)
    main_mod.mcp_transport = "stdio"
    main_mod.mcp_http_url = "http://localhost:8100/mcp"
    with TestClient(main_mod.app) as client:
        yield client, fake_manager


@pytest.fixture
def client_streamable_http(streamable_http_env, monkeypatch):
    """Return a TestClient with streamable-http transport."""
    fake_manager = AsyncMock()
    fake_manager.start = AsyncMock()
    monkeypatch.setattr("mcp_subprocess.AsyncMCPSubprocess", lambda: fake_manager)
    main_mod = _reload_main(monkeypatch)
    main_mod.mcp_transport = "streamable-http"
    main_mod.mcp_http_url = "http://localhost:8100/mcp"
    with TestClient(main_mod.app) as client:
        yield client


# ---------------------------------------------------------------------------
# Auth tests (transport-agnostic)
# ---------------------------------------------------------------------------


def test_mcp_proxy_unauthorized_no_header(client_stdio):
    client, _ = client_stdio
    resp = client.get("/mcp/nanorag_health")
    assert resp.status_code == 401


def test_mcp_proxy_unauthorized_wrong_key(client_stdio):
    client, _ = client_stdio
    resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_mcp_proxy_authorized(client_stdio):
    client, _ = client_stdio
    resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "test-key"})
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Stdio transport tests
# ---------------------------------------------------------------------------


def test_stdio_proxy_non_streaming(client_stdio):
    client, fake_manager = client_stdio
    fake_manager.call_tool.return_value = {"status": "ok", "indexed_chunks": 42}

    resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "indexed_chunks": 42}
    fake_manager.call_tool.assert_called_once()
    args, kwargs = fake_manager.call_tool.call_args
    assert args[0] == "nanorag_health"
    assert kwargs.get("stream") is False


def test_stdio_proxy_streaming(client_stdio):
    client, fake_manager = client_stdio
    fake_manager.call_tool.return_value = _async_gen(
        b'{"type":"meta","matches":0}\n',
        b'{"type":"done"}\n',
    )

    resp = client.post(
        "/mcp/nanorag_chat",
        json={"kb_id": "test", "message": "hello"},
        headers={"X-API-Key": "test-key", "Accept": "application/x-ndjson"},
    )
    assert resp.status_code == 200
    lines = [line for line in resp.iter_lines()]
    assert len(lines) >= 2
    fake_manager.call_tool.assert_called_once()
    kwargs = fake_manager.call_tool.call_args.kwargs
    assert kwargs.get("stream") is True


def test_stdio_proxy_subprocess_not_started(stdio_env, monkeypatch):
    """When mcp_manager is None and transport is stdio, expect 503."""
    # Must mock AsyncMCPSubprocess to prevent real subprocess startup
    monkeypatch.setattr("mcp_subprocess.AsyncMCPSubprocess", lambda: AsyncMock())
    main_mod = _reload_main(monkeypatch)
    main_mod.mcp_transport = "stdio"
    with TestClient(main_mod.app) as client:
        # Override after startup handler has run
        main_mod.mcp_manager = None
        resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 503
        assert "not started" in resp.json()["detail"]


def test_stdio_proxy_call_tool_error(client_stdio):
    client, fake_manager = client_stdio
    fake_manager.call_tool.side_effect = RuntimeError("subprocess crashed")

    resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 502
    assert "subprocess crashed" in resp.json()["detail"]


def test_stdio_proxy_unwraps_result_field(client_stdio):
    client, fake_manager = client_stdio
    fake_manager.call_tool.return_value = {"result": {"data": "unwrapped"}}

    resp = client.get("/mcp/nanorag_health", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200
    assert resp.json() == {"data": "unwrapped"}


# ---------------------------------------------------------------------------
# Streamable-http transport tests
# ---------------------------------------------------------------------------


def test_streamable_http_proxy_non_streaming(client_streamable_http):
    """Forward a GET request to the upstream MCP HTTP server (non-streaming)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"status": "ok", "llm_provider": "ollama"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        resp = client_streamable_http.get(
            "/mcp/nanorag_health", headers={"X-API-Key": "test-key"}
        )
        assert resp.status_code == 200
        mock_client.request.assert_called_once()
        args, _ = mock_client.request.call_args
        assert args[0] == "GET"
        assert "nanorag_health" in args[1]


def test_streamable_http_proxy_streaming(client_streamable_http):
    """Forward a streaming POST — verify byte-level NDJSON pass-through."""
    mock_stream = MagicMock()
    mock_stream.headers = {"content-type": "application/x-ndjson"}
    mock_stream.aiter_bytes = MagicMock()
    mock_stream.aiter_bytes.return_value = _async_gen(
        b'{"type":"meta"}\n',
        b'{"type":"done"}\n',
    )
    mock_stream.aclose = AsyncMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.stream.return_value = mock_stream
        mock_client_class.return_value.__aenter__.return_value = mock_client

        resp = client_streamable_http.post(
            "/mcp/nanorag_chat",
            json={"kb_id": "test", "message": "hello"},
            headers={"X-API-Key": "test-key", "Accept": "application/x-ndjson"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-ndjson"
        lines = [line for line in resp.iter_lines()]
        assert len(lines) >= 2


def test_streamable_http_proxy_upstream_error(client_streamable_http):
    """Upstream error → 502."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("upstream down")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        resp = client_streamable_http.get(
            "/mcp/nanorag_health", headers={"X-API-Key": "test-key"}
        )
        assert resp.status_code == 502
        assert "upstream down" in resp.json()["detail"]


def test_streamable_http_preserves_empty_path(client_streamable_http):
    """GET /mcp (empty path) should forward to upstream /mcp/."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"status": "ok"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # FastAPI redirects /mcp → /mcp/, so path becomes empty
        resp = client_streamable_http.get("/mcp/", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        args, _ = mock_client.request.call_args
        # Upstream URL ends with /mcp/ (empty path appended)
        assert args[1].rstrip("/").endswith("/mcp")


def test_streamable_http_proxy_uses_custom_port(streamable_http_env, monkeypatch):
    """When MCP_HTTP_PORT is overridden, the upstream URL uses it."""
    monkeypatch.setenv("MCP_HTTP_PORT", "8200")
    main_mod = _reload_main(monkeypatch)
    main_mod.mcp_manager = None
    main_mod.mcp_transport = "streamable-http"
    # The URL should now be constructed from MCP_HTTP_PORT=8200
    assert main_mod.mcp_http_url == "http://localhost:8200/mcp"


def test_streamable_http_proxy_uses_mcp_http_url_override(streamable_http_env, monkeypatch):
    """When MCP_HTTP_URL is set, it takes precedence over MCP_HTTP_PORT."""
    monkeypatch.setenv("MCP_HTTP_URL", "http://remote:9999/mcp")
    main_mod = _reload_main(monkeypatch)
    main_mod.mcp_manager = None
    main_mod.mcp_transport = "streamable-http"
    assert main_mod.mcp_http_url == "http://remote:9999/mcp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_gen(*chunks: bytes):
    """Async generator that yields each chunk once."""
    for chunk in chunks:
        yield chunk
