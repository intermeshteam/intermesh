import asyncio
import secrets
import time
import pytest
import websockets
import jwt

from intermesh import InterMeshAgent, InterMeshMessage, MessageType, InterMeshTask, TaskStatus
from intermesh.identity import AgentIdentity


@pytest.fixture
async def local_hub():
    """Démarre un Hub InterMesh éphémère en mémoire pour le test."""
    port = 8769
    hub_secret = secrets.token_hex(32)
    agents = {}
    identity_registry = {}
    task_registry = {}

    def generate_token(name, aid, roles):
        return jwt.encode({"agent_name": name, "agent_id": aid, "roles": roles, "issued_at": time.time(), "expires_at": time.time() + 3600}, hub_secret, algorithm="HS256")

    def verify_token(token, name):
        try:
            p = jwt.decode(token, hub_secret, algorithms=["HS256"])
            return p.get("agent_name") == name
        except Exception:
            return False

    async def handler(websocket):
        agent_name = None
        try:
            async for raw in websocket:
                msg = InterMeshMessage.from_json(raw)
                if msg.type == MessageType.REGISTER:
                    agent_name = msg.sender
                    d = msg.content or {}
                    ident = AgentIdentity.from_dict({
                        "name": agent_name, "agent_id": d.get("agent_id"),
                        "capabilities": d.get("capabilities", []), "roles": d.get("roles", ["standard"]),
                        "permissions": d.get("permissions", []), "created_at": d.get("created_at"),
                        "public_key": d.get("public_key")
                    })
                    agents[agent_name] = websocket
                    identity_registry[agent_name] = ident
                    token = generate_token(agent_name, ident.agent_id, ident.roles)
                    await websocket.send(InterMeshMessage(type=MessageType.REGISTERED, sender="hub", to=agent_name, content={"status": "ready", "token": token, "online_agents": list(agents.keys())}).to_json())

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE, MessageType.WHO_IS, MessageType.TASK_SUBMIT, MessageType.TASK_UPDATE):
                    if not msg.token or not verify_token(msg.token, msg.sender):
                        continue

                    if msg.type == MessageType.TASK_SUBMIT:
                        t = InterMeshTask.from_dict(msg.content)
                        task_registry[t.task_id] = t
                        if t.assignee in agents:
                            await agents[t.assignee].send(InterMeshMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=t.assignee, reply_to=msg.id, content=t.to_dict(), token=msg.token).to_json())

                    elif msg.type == MessageType.TASK_UPDATE:
                        td = msg.content
                        tid = td.get("task_id")
                        if tid in task_registry:
                            task_registry[tid] = InterMeshTask.from_dict(td)
                            orch = td.get("orchestrator")
                            if orch in agents:
                                await agents[orch].send(InterMeshMessage(type=MessageType.TASK_UPDATE, sender="hub", to=orch, content=td, token=msg.token).to_json())

                    elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                        if msg.to in agents:
                            await agents[msg.to].send(msg.to_json())
                            await websocket.send(InterMeshMessage(type=MessageType.ACK, sender="hub", to=msg.sender, reply_to=msg.id, content={"status": "delivered"}, token=msg.token).to_json())

                    elif msg.type == MessageType.WHO_IS:
                        if msg.content in identity_registry:
                            await websocket.send(InterMeshMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[msg.content].to_dict(), token=msg.token).to_json())
        except Exception:
            pass
        finally:
            if agent_name and agent_name in agents:
                del agents[agent_name]

    server = await websockets.serve(handler, "127.0.0.1", port)
    yield f"ws://127.0.0.1:{port}"
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_full_agent_to_agent_encrypted_workflow(local_hub):
    """Test d'intégration complet : 2 agents s'enregistrent, s'authentifient et exécutent une tâche chiffrée E2E."""
    hub_url = local_hub

    # 1. Création de l'agent Worker (Calculateur)
    worker = InterMeshAgent(name="test_worker_calc", capabilities=["calculate"], roles=["worker"], hub_url=hub_url)
    
    @worker.on_task
    async def handle_task(input_data, task):
        return {"result": input_data["val"] * 2}
        
    await worker.connect()

    # 2. Création de l'agent Orchestrator
    orchestrator = InterMeshAgent(name="test_orchestrator", capabilities=["orchestration"], roles=["admin"], hub_url=hub_url)
    await orchestrator.connect()
    
    await asyncio.sleep(0.5)

    # 3. Délégation d'une tâche chiffrée
    result = await orchestrator.submit_task(
        title="Test Doubler",
        assignee="test_worker_calc",
        input_data={"val": 21},
        timeout=5.0
    )

    # 4. Validation du résultat
    assert result == {"result": 42}

    # Nettoyage des connexions
    await worker.ws.close()
    await orchestrator.ws.close()
