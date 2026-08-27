import asyncio
import os
import subprocess
import sys
import tempfile
import pytest
from nexus_sdk.agent import NexusAgent


@pytest.mark.asyncio
async def test_strict_tenant_isolation_by_default():
    """
    Verifie que par defaut, deux agents de tenants distincts (acme vs globex)
    ne peuvent pas communiquer ni se decouvrir sur le Hub.
    """
    port = 8840
    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub_proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port),
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    await asyncio.sleep(1.5)

    try:
        agent_acme = NexusAgent(name="worker", org_id="acme", hub_url=f"ws://localhost:{port}", encrypt=False)
        agent_globex = NexusAgent(name="analyzer", org_id="globex", hub_url=f"ws://localhost:{port}", encrypt=False)

        await agent_acme.connect()
        await agent_globex.connect()
        await asyncio.sleep(0.3)

        # 1. Verifier le blocage d'une requete croisee acme -> globex
        with pytest.raises(Exception) as exc:
            await agent_acme.ask("globex/analyzer", "ping", timeout=2.0)
        assert "Multi-Tenant" in str(exc.value)

        # 2. Verifier que l'agent Acme ne decouvre pas Globex
        discovery = await agent_acme.discover(limit=10)
        agent_names = [a["name"] for a in discovery["agents"]]
        assert "globex/analyzer" not in agent_names

        await agent_acme.ws.close()
        await agent_globex.ws.close()
    finally:
        hub_proc.terminate()
        hub_proc.wait()
