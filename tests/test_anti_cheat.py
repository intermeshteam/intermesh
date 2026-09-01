import asyncio
import os
import sys
import subprocess
import pytest

from intermesh.hardware import get_machine_fingerprint, verify_machine_fingerprint
from intermesh import InterMeshAgent


def test_hardware_fingerprint_generation():
    """Vérifie la stabilité et le format de l'empreinte matérielle du PC."""
    fp1 = get_machine_fingerprint()
    fp2 = get_machine_fingerprint()

    assert len(fp1) == 64  # SHA-256
    assert fp1 == fp2      # Déterministe sur le même PC
    assert verify_machine_fingerprint(fp1) is True
    assert verify_machine_fingerprint("fake_hacked_fingerprint") is False
    print("✅ Hardware Fingerprint (Anti-Theft) Verified!")


@pytest.mark.asyncio
async def test_agent_cap_is_unlimited_by_default():
    """Aucun plafond sans configuration explicite.

    Le Hub imposait 15 agents en dur, et refusait le 16e *avant* même de
    regarder la clé d'API — une clé entreprise n'y changeait donc rien.
    Comme le dépôt est public, la constante était de toute façon éditable :
    elle ne protégeait aucun modèle économique, elle empêchait seulement de
    se servir du produit. Le défaut est désormais illimité, ce qui est aussi
    ce qu'annonce la page de tarification.
    """
    os.system("fuser -k 8765/tcp || true")
    await asyncio.sleep(0.5)

    hub_proc = subprocess.Popen([sys.executable, "server/hub.py",
                                 "--ephemeral-state", "--ephemeral-secret"])
    await asyncio.sleep(1.5)

    agents = []
    try:
        for i in range(18):   # au-delà de l'ancien plafond
            agent = InterMeshAgent(name=f"worker_bot_{i}", hub_url="ws://localhost:8765")
            await agent.connect()
            agents.append(agent)

        assert len(agents) == 18
        print("✅ 18 agents connectés — aucun plafond par défaut")
    finally:
        for a in agents:
            if a.ws:
                await a.ws.close()
        hub_proc.terminate()
        hub_proc.wait()


@pytest.mark.asyncio
async def test_agent_cap_is_enforced_when_configured():
    """Le plafond existe toujours, mais il se déclare."""
    os.system("fuser -k 8766/tcp || true")
    await asyncio.sleep(0.5)

    hub_proc = subprocess.Popen([sys.executable, "server/hub.py",
                                 "--port", "8766", "--max-agents", "3",
                                 "--ephemeral-state", "--ephemeral-secret"])
    await asyncio.sleep(1.5)

    agents = []
    try:
        for i in range(3):
            agent = InterMeshAgent(name=f"capped_{i}", hub_url="ws://localhost:8766")
            await agent.connect()
            agents.append(agent)

        extra = InterMeshAgent(name="one_too_many", hub_url="ws://localhost:8766")
        with pytest.raises(PermissionError) as exc_info:
            await extra.connect()

        assert "AGENT_LIMIT_REACHED" in str(exc_info.value)
        print("✅ Plafond respecté quand il est déclaré")
    finally:
        for a in agents:
            if a.ws:
                await a.ws.close()
        hub_proc.terminate()
        hub_proc.wait()


if __name__ == "__main__":
    test_hardware_fingerprint_generation()
    asyncio.run(test_agent_cap_is_unlimited_by_default())
    asyncio.run(test_agent_cap_is_enforced_when_configured())
    print("\n🎉 TOUTES LES PROTECTIONS ANTI-TRICHERIE & FACTURATION SONT VALIDÉES !")
