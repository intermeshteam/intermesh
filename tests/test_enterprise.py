import asyncio
import os
import sys
import subprocess
import pytest

from nexus_sdk import NexusAgent, ImmutableAuditLog, RateLimiter


def test_immutable_audit_log_integrity():
    """Vérifie l'intégrité de la chaîne cryptographique d'audit."""
    log = ImmutableAuditLog()

    # 1. Écrire des événements
    log.log("AGENT_REGISTERED", "acme/agent_1", None, {"role": "admin"})
    log.log("TASK_SUBMITTED", "acme/agent_1", "globex/worker_2", {"task_id": "123"})
    log.log("TASK_COMPLETED", "globex/worker_2", "acme/agent_1", {"result": 42})

    # 2. Vérifier que la chaîne est 100% valide
    assert log.verify_integrity() is True
    assert len(log.chain) == 4  # Genesis + 3 événements

    # 3. Test de Détection de Fraude / Altération
    # Un pirate tente d'altérer rétroactivement le 2ème événement
    log.chain[2].metadata = {"task_id": "HACKED_DATA"}

    # La vérification mathématique doit immédiatement échouer
    assert log.verify_integrity() is False
    print("✓ Détection d'altération de journal d'audit validée !")


def test_rate_limiter_token_bucket():
    """Vérifie le blocage des requêtes en rafale (Burst & Rate Limiting)."""
    limiter = RateLimiter(default_rate=5.0, default_burst=5.0)
    client = "agent_spammer"

    # Les 5 premières requêtes passent (capacité burst)
    for _ in range(5):
        assert limiter.is_allowed(client) is True

    # La 6ème requête consécutive immédiate doit être bloquée
    assert limiter.is_allowed(client) is False
    print("✓ Rate Limiting (Token Bucket) validé !")


@pytest.mark.asyncio
async def test_service_account_api_key_authentication():
    """Vérifie l'authentification automatique par Clé d'API Entreprise."""
    os.system("fuser -k 8765/tcp || true")
    await asyncio.sleep(0.5)

    hub_proc = subprocess.Popen([sys.executable, "server/hub.py", "--port", "8765", "--org", "acme"])
    await asyncio.sleep(1.0)

    try:
        # Connexion avec une clé d'API Entreprise valide
        agent = NexusAgent(
            name="backend_microservice",
            api_key="nx_live_acme_super_secret_key_123",
            hub_url="ws://localhost:8765"
        )
        await agent.connect()
        assert agent.token is not None
        assert "service_account" in agent.identity.roles
        print("✓ Authentification par Clé d'API Entreprise validée !")
        await agent.ws.close()

    finally:
        hub_proc.terminate()
        hub_proc.wait()


if __name__ == "__main__":
    test_immutable_audit_log_integrity()
    test_rate_limiter_token_bucket()
    asyncio.run(test_service_account_api_key_authentication())
    print("\n🎉 TOUTES LES FONCTIONNALITÉS ENTERPRISE SONT VALIDÉES !")
