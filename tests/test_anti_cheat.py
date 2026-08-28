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
async def test_quota_15_agents_enforcement():
    """Vérifie le blocage strict au-delà de 15 agents simultanés."""
    os.system("fuser -k 8765/tcp || true")
    await asyncio.sleep(0.5)

    hub_proc = subprocess.Popen([sys.executable, "server/hub_telemetry.py"])
    await asyncio.sleep(1.0)

    connected_agents = []
    try:
        # 1. Connecter 15 agents autorisés
        for i in range(15):
            agent = InterMeshAgent(name=f"worker_bot_{i}", hub_url="ws://localhost:8765")
            await agent.connect()
            connected_agents.append(agent)

        print("✓ 15 agents connectés simultanément (Plafond atteint)")

        # 2. Le 16ème agent DOIT être rejeté avec AGENT_QUOTA_EXCEEDED
        agent_16 = InterMeshAgent(name="illegal_worker_16", hub_url="ws://localhost:8765")
        
        with pytest.raises(PermissionError) as exc_info:
            await agent_16.connect()

        assert "AGENT_QUOTA_EXCEEDED" in str(exc_info.value)
        print("✅ 16th Agent rejection verified! (Strict 15-Agent Quota)")

    finally:
        for a in connected_agents:
            if a.ws:
                await a.ws.close()
        hub_proc.terminate()
        hub_proc.wait()


if __name__ == "__main__":
    test_hardware_fingerprint_generation()
    asyncio.run(test_quota_15_agents_enforcement())
    print("\n🎉 TOUTES LES PROTECTIONS ANTI-TRICHERIE & FACTURATION SONT VALIDÉES !")
