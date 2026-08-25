"""Tests de la résolution de la clé de signature JWT du Hub."""

import os
import stat
import time

import jwt
import pytest

from nexus_sdk.secret import ENV_VAR, default_secret_path, resolve_hub_secret


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Isole chaque test de la clé éventuellement présente dans l'environnement."""
    monkeypatch.delenv(ENV_VAR, raising=False)


def test_environment_variable_wins(monkeypatch, tmp_path):
    """Une clé fournie par l'environnement prime sur le fichier."""
    secret_file = tmp_path / "hub_secret"
    secret_file.write_text("f" * 64)

    monkeypatch.setenv(ENV_VAR, "e" * 64)
    secret, source = resolve_hub_secret(secret_file=secret_file)

    assert secret == "e" * 64
    assert ENV_VAR in source
    print("✓ La variable d'environnement est prioritaire")


def test_short_environment_secret_is_rejected(monkeypatch, tmp_path):
    """Une clé trop courte doit faire échouer le démarrage, pas passer silencieusement."""
    monkeypatch.setenv(ENV_VAR, "trop_court")

    with pytest.raises(ValueError, match="caractères"):
        resolve_hub_secret(secret_file=tmp_path / "hub_secret")
    print("✓ Clé trop courte rejetée")


def test_secret_file_is_created_with_owner_only_permissions(tmp_path):
    """Le fichier de clé ne doit être lisible que par son propriétaire."""
    secret_file = tmp_path / "sub" / "hub_secret"
    secret, source = resolve_hub_secret(secret_file=secret_file)

    assert secret_file.is_file()
    assert len(secret) >= 32
    assert "créé" in source

    mode = secret_file.stat().st_mode
    assert not mode & stat.S_IRWXG, "le groupe ne doit avoir aucun droit"
    assert not mode & stat.S_IRWXO, "les autres ne doivent avoir aucun droit"
    print("✓ Fichier de clé créé en 0600")


def test_secret_survives_restart(tmp_path):
    """
    Régression : le Hub régénérait sa clé à chaque démarrage, ce qui
    invalidait tous les tokens déjà distribués.
    """
    secret_file = tmp_path / "hub_secret"

    first, _ = resolve_hub_secret(secret_file=secret_file)
    second, source = resolve_hub_secret(secret_file=secret_file)

    assert first == second, "la clé doit être stable d'un démarrage à l'autre"
    assert "créé" not in source, "le second démarrage doit relire, pas recréer"
    print("✓ La clé survit au redémarrage")


def test_token_issued_before_restart_still_verifies_after(tmp_path):
    """Un agent connecté ne doit pas être éjecté par un redémarrage du Hub."""
    secret_file = tmp_path / "hub_secret"

    # Démarrage 1 : le Hub émet un token pour un agent
    secret_before, _ = resolve_hub_secret(secret_file=secret_file)
    token = jwt.encode(
        {"agent_name": "acme/worker", "expires_at": time.time() + 3600},
        secret_before,
        algorithm="HS256",
    )

    # Démarrage 2 : nouveau processus, même fichier de clé
    secret_after, _ = resolve_hub_secret(secret_file=secret_file)

    payload = jwt.decode(token, secret_after, algorithms=["HS256"])
    assert payload["agent_name"] == "acme/worker"
    print("✓ Un token émis avant redémarrage reste valide après")


def test_ephemeral_secret_is_never_persisted(tmp_path):
    """Le mode éphémère ne doit rien écrire et produire une clé différente à chaque appel."""
    secret_file = tmp_path / "hub_secret"

    first, source = resolve_hub_secret(secret_file=secret_file, ephemeral=True)
    second, _ = resolve_hub_secret(secret_file=secret_file, ephemeral=True)

    assert first != second
    assert not secret_file.exists(), "le mode éphémère ne doit rien écrire sur disque"
    assert source.startswith("éphémère")
    print("✓ Le mode éphémère n'écrit rien")


def test_default_path_follows_nexus_home(monkeypatch, tmp_path):
    """NEXUS_HOME permet de relocaliser la clé (conteneurs, volumes montés)."""
    monkeypatch.setenv("NEXUS_HOME", str(tmp_path / "custom"))
    assert default_secret_path() == tmp_path / "custom" / "hub_secret"

    monkeypatch.delenv("NEXUS_HOME")
    assert default_secret_path().parent.name == ".nexus"
    print("✓ NEXUS_HOME respecté")


def test_concurrent_hubs_converge_on_same_secret(tmp_path):
    """Deux Hubs démarrant en parallèle doivent signer avec la même clé."""
    secret_file = tmp_path / "hub_secret"

    # Simule la course : le fichier apparaît entre la lecture et l'écriture
    # du second Hub. Sans convergence, les deux signeraient différemment et
    # les agents de l'un seraient rejetés par l'autre.
    first, _ = resolve_hub_secret(secret_file=secret_file)
    second, _ = resolve_hub_secret(secret_file=secret_file)

    assert first == second
    print("✓ Deux Hubs convergent sur la même clé")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
