"""Tests du magasin de clés d'API (comptes de service)."""

import json
import stat

import pytest

from nexus_sdk.apikeys import (
    DEV_API_KEYS,
    ENV_FILE,
    ENV_INLINE,
    ApiKeyStore,
    generate_key,
    hash_key,
)

SAMPLE = {
    "nx_live_test_key": {
        "org_id": "acme",
        "roles": ["admin", "service_account"],
        "permissions": ["admin:*"],
    }
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_INLINE, raising=False)
    monkeypatch.delenv(ENV_FILE, raising=False)
    # Empêche de retomber sur le ~/.nexus/api_keys.json réel du poste
    monkeypatch.setenv("NEXUS_HOME", str(tmp_path / "home"))


def test_valid_key_grants_declared_privileges():
    store = ApiKeyStore(SAMPLE)
    info = store.lookup("nx_live_test_key")

    assert info is not None
    assert info["org_id"] == "acme"
    assert "service_account" in info["roles"]
    assert info["permissions"] == ["admin:*"]
    print("✓ Clé valide reconnue avec ses privilèges")


def test_unknown_and_empty_keys_are_rejected():
    store = ApiKeyStore(SAMPLE)
    assert store.lookup("nx_live_wrong_key") is None
    assert store.lookup("") is None
    assert store.lookup(None) is None
    print("✓ Clés inconnues rejetées")


def test_raw_keys_are_never_kept_in_memory():
    """
    Le Hub ne doit pas pouvoir révéler une clé, seulement en vérifier une.
    """
    store = ApiKeyStore(SAMPLE)
    dumped = repr(store.__dict__)

    assert "nx_live_test_key" not in dumped
    assert hash_key("nx_live_test_key") in dumped
    print("✓ Seules les empreintes sont conservées")


def test_service_accounts_are_disabled_by_default():
    """
    Sans configuration, aucune clé ne doit fonctionner — surtout pas une
    valeur par défaut devinable.
    """
    store = ApiKeyStore.load()
    assert len(store) == 0
    assert store.lookup("nx_dev_acme_demo_key") is None
    for key in DEV_API_KEYS:
        assert store.lookup(key) is None
    print("✓ Comptes de service désactivés par défaut")


def test_dev_keys_require_explicit_optin():
    disabled = ApiKeyStore.load()
    enabled = ApiKeyStore.load(dev_keys=True)

    assert disabled.lookup("nx_dev_acme_demo_key") is None
    assert enabled.lookup("nx_dev_acme_demo_key") is not None
    assert "DÉMONSTRATION" in enabled.source
    print("✓ Clés de démo seulement sur opt-in explicite")


def test_inline_env_variable_is_loaded(monkeypatch):
    monkeypatch.setenv(ENV_INLINE, json.dumps(SAMPLE))
    store = ApiKeyStore.load()

    assert store.lookup("nx_live_test_key")["org_id"] == "acme"
    assert ENV_INLINE in store.source
    print("✓ Chargement depuis la variable d'environnement")


def test_malformed_configuration_fails_loudly(monkeypatch):
    """Une config illisible ne doit pas dégrader silencieusement en 'aucune clé'."""
    monkeypatch.setenv(ENV_INLINE, "{ceci n'est pas du json")
    with pytest.raises(ValueError, match="JSON"):
        ApiKeyStore.load()
    print("✓ Configuration invalide signalée")


def test_key_file_is_loaded(monkeypatch, tmp_path):
    path = tmp_path / "api_keys.json"
    path.write_text(json.dumps(SAMPLE))
    path.chmod(0o600)
    monkeypatch.setenv(ENV_FILE, str(path))

    store = ApiKeyStore.load()
    assert store.lookup("nx_live_test_key")["org_id"] == "acme"
    assert str(path) in store.source
    print("✓ Chargement depuis un fichier")


def test_env_variable_wins_over_file(monkeypatch, tmp_path):
    path = tmp_path / "api_keys.json"
    path.write_text(json.dumps({"nx_from_file": {"org_id": "file", "roles": []}}))
    monkeypatch.setenv(ENV_FILE, str(path))
    monkeypatch.setenv(ENV_INLINE, json.dumps({"nx_from_env": {"org_id": "env", "roles": []}}))

    store = ApiKeyStore.load()
    assert store.lookup("nx_from_env") is not None
    assert store.lookup("nx_from_file") is None
    print("✓ L'environnement est prioritaire sur le fichier")


def test_generated_keys_are_unique_and_prefixed():
    keys = {generate_key() for _ in range(100)}
    assert len(keys) == 100, "aucune collision attendue"
    assert all(k.startswith("nx_live_") for k in keys)
    assert all(len(k) > 40 for k in keys)
    print("✓ Génération de clés robuste")


def test_no_hardcoded_key_remains_in_the_hub_source():
    """Régression : les clés étaient publiées avec le dépôt."""
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "server" / "hub.py"
    text = source.read_text(encoding="utf-8")

    assert "nx_live_" not in text, "une clé d'API est de nouveau en dur dans le Hub"
    assert "ENTERPRISE_API_KEYS" not in text
    print("✓ Aucune clé en dur dans server/hub.py")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
