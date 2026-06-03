from __future__ import annotations

import pytest

from mcp_runtime_config import resolve_mcp_runtime_config


def test_invalid_transport_raises_value_error(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HTTP_PORT", "8100")

    with pytest.raises(ValueError, match="MCP_TRANSPORT must be one of"):
        resolve_mcp_runtime_config()


def test_invalid_port_raises_value_error(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_PORT", "eighty-one")

    with pytest.raises(ValueError, match="MCP_HTTP_PORT must be an integer"):
        resolve_mcp_runtime_config()


def test_streamable_http_config_uses_validated_port(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_PORT", "9100")

    config = resolve_mcp_runtime_config()

    assert config.transport == "streamable-http"
    assert config.http_host == "0.0.0.0"
    assert config.http_port == 9100


def test_stdio_defaults_to_port_8100(monkeypatch):
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("MCP_HTTP_PORT", raising=False)

    config = resolve_mcp_runtime_config()

    assert config.transport == "stdio"
    assert config.http_port == 8100
