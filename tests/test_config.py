import os
from pathlib import Path
from nexus_sdk.config import Settings

def test_settings_defaults():
    settings = Settings()
    assert settings.hub_port == 8765
    assert settings.default_org == "default"
    assert settings.default_encrypt is True
    assert settings.default_timeout_ask == 10.0

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("NEXUS_HUB_PORT", "9999")
    monkeypatch.setenv("NEXUS_DEFAULT_ORG", "test_org")
    monkeypatch.setenv("NEXUS_ENCRYPT", "false")
    monkeypatch.setenv("NEXUS_TIMEOUT_ASK", "45.5")
    
    settings = Settings()
    assert settings.hub_port == 9999
    assert settings.default_org == "test_org"
    assert settings.default_encrypt is False
    assert settings.default_timeout_ask == 45.5
