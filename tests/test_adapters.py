import asyncio
import os
import sys
import subprocess
import pytest

from intermesh import InterMeshAgent, intermesh_service, from_callable, from_langchain


def mock_legacy_ai_function(input_data):
    """Une fonction Python / IA préexistante ordinaire."""
    text = input_data.get("text", "")
    return {"summary": f"PROCESSED: {text.upper()}"}


class MockLangChainRunnable:
    """Un faux Runnable LangChain avec méthode invoke()."""
    def invoke(self, input_data):
        return f"LangChain Output for {input_data}"


def test_adapter_unit_creation():
    """Vérifie la création des agents adaptés."""
    # 1. Option 1-Line Classmethod
    agent1 = InterMeshAgent.from_callable(mock_legacy_ai_function, name="tool_1", capabilities=["summarize"])
    assert agent1.name == "tool_1"
    assert "summarize" in agent1.identity.capabilities

    # 2. Option LangChain
    lc_mock = MockLangChainRunnable()
    agent2 = InterMeshAgent.from_langchain(lc_mock, name="langchain_bot", capabilities=["chain_exec"])
    assert agent2.name == "langchain_bot"

    # 3. Option Decorator
    @intermesh_service(name="decorated_service", capabilities=["nlp"])
    def my_service(data):
        return "ok"

    assert my_service.name == "decorated_service"
    print("✅ Unit tests for 1-line adapters passed!")


@pytest.mark.asyncio
async def test_1line_integration_live_execution():
    """Vérification complète en direct : connexion et exécution d'un agent adapté en 1 ligne."""
    os.system("fuser -k 8765/tcp || true")
    await asyncio.sleep(0.5)

    hub_proc = subprocess.Popen([sys.executable, "server/hub.py",
                                  "--ephemeral-state", "--ephemeral-secret"])
    await asyncio.sleep(1.0)

    try:
        # 1. CRÉATION EN 1 LIGNE : On adapte notre fonction ordinaire en Agent InterMesh
        worker_agent = InterMeshAgent.from_callable(
            mock_legacy_ai_function, 
            name="1line_worker", 
            capabilities=["summarize"]
        )
        await worker_agent.connect()

        # 2. L'orchestrateur s'exécute et délègue la tâche au worker 1-ligne
        orchestrator = InterMeshAgent(name="caller_agent", roles=["admin"])
        await orchestrator.connect()

        await asyncio.sleep(0.5)

        # 3. Exécution de la tâche chiffrée E2E
        res = await orchestrator.submit_task(
            title="Summary Task",
            assignee="default/1line_worker",
            input_data={"text": "intermesh protocol"}
        )

        assert res == {"summary": "PROCESSED: INTERMESH PROTOCOL"}
        print("\n✅ 1-Line Adapter Live Execution Verified Successfully!")

        await worker_agent.ws.close()
        await orchestrator.ws.close()

    finally:
        hub_proc.terminate()
        hub_proc.wait()


if __name__ == "__main__":
    test_adapter_unit_creation()
    asyncio.run(test_1line_integration_live_execution())
