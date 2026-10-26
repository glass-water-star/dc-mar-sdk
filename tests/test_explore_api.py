import asyncio

import pytest

import explore_api


class ClientInitialized(Exception):
    pass


def test_get_api_key_reads_exported_environment_variable(monkeypatch):
    monkeypatch.setenv("DC_MAR_API_KEY", "test-api-key")

    assert explore_api.get_api_key() == "test-api-key"


def test_get_api_key_returns_none_when_environment_variable_is_missing(monkeypatch):
    monkeypatch.delenv("DC_MAR_API_KEY", raising=False)

    assert explore_api.get_api_key() is None


def test_explore_api_passes_exported_key_to_client(monkeypatch):
    captured: dict[str, object] = {}

    def client_factory(*, api_key, enable_telemetry):
        captured["api_key"] = api_key
        captured["enable_telemetry"] = enable_telemetry
        raise ClientInitialized

    monkeypatch.setenv("DC_MAR_API_KEY", "test-api-key")
    monkeypatch.setattr(explore_api, "MARClient", client_factory)

    with pytest.raises(ClientInitialized):
        asyncio.run(explore_api.explore_api())

    assert captured == {"api_key": "test-api-key", "enable_telemetry": True}
