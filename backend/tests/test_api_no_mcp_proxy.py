from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _install_import_mocks() -> None:
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


def _fake_runtime():
    from test_mcp_server import _fake_runtime as _fr

    return _fr()


def _reload_main(monkeypatch):
    monkeypatch.setattr("bootstrap.build_ingestion_runtime", lambda s: _fake_runtime())
    from config import get_settings

    get_settings.cache_clear()
    import backend.api.main

    return importlib.reload(backend.api.main)


def test_backend_no_longer_exposes_mcp_route(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    with TestClient(main_mod.app) as client:
        response = client.get("/mcp/nanorag_health")

    assert response.status_code == 404


def test_backend_health_route_still_works_after_mcp_proxy_removal(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    with TestClient(main_mod.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
