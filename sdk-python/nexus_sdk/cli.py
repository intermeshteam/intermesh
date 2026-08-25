import argparse
import asyncio
import http.server
import json
import os
import socketserver
import sys
import time

from nexus_sdk import NexusAgent, NexusMessage, MessageType
from nexus_sdk.crypto import generate_keypair, get_public_key_pem
from nexus_sdk.identity import AgentIdentity


def print_banner():
    print("""
\033[36m    _   ___________  _______
   / | / / ____/   |/  _/   |  NEXUS PROTOCOL
  /  |/ / __/ / /| |/ // /| |  Universal Agent Infrastructure
 / /|  / /___/ ___ / // ___ |  CLI Developer Tool v0.1.0
/_/ |_/_____/_/  |_/___/_/  |_|\033[0m
""")


def run_dashboard(args):
    port = args.port
    dashboard_dir = os.path.expanduser("~/nexus/dashboard")
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args_h, **kwargs_h):
            super().__init__(*args_h, directory=dashboard_dir, **kwargs_h)
            
        def log_message(self, format, *log_args):
            pass  # Mode silencieux

    print(f"\033[32m✓ Nexus Mission Control Dashboard actif !\033[0m")
    print(f"  🌐 Ouvrez dans votre navigateur : \033[36mhttp://localhost:{port}\033[0m")
    print("  (Ctrl+C pour arrêter le serveur web)\n")

    with socketserver.TCPServer(("", port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nArrêt du Dashboard.")


def run_docs(args):
    doc_type = args.topic
    base_docs_path = os.path.expanduser("~/nexus/docs")
    mapping = {
        "rfc": os.path.join(base_docs_path, "RFC-001-CORE-PROTOCOL.md"),
        "security": os.path.join(base_docs_path, "SECURITY-AND-ENCRYPTION.md"),
        "api": os.path.join(base_docs_path, "API-REFERENCE.md"),
    }
    target_file = mapping.get(doc_type)
    if target_file and os.path.exists(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            print(f"\033[33m--- DOCUMENTATION NEXUS : {doc_type.upper()} ---\033[0m\n")
            print(f.read())
    else:
        print(f"\033[31mDocumentation introuvable pour '{doc_type}'.\033[0m")


async def run_discover(args):
    agent = NexusAgent(name="cli_inspector", roles=["admin"], encrypt=False)
    await agent.connect()
    query = {}
    if args.capability: query["capabilities"] = [args.capability]
    if args.role: query["roles"] = [args.role]
    print(f"\033[33m🔍 Recherche d'agents connectés...\033[0m")
    result = await agent.discover(**query, timeout=4.0)
    agents = result.get("agents", [])
    print(f"\n\033[32m✓ {len(agents)} agent(s) trouvé(s) sur le réseau :\033[0m\n")
    print(f"{'NOM':<20} {'RÔLES':<18} {'CAPACITÉS':<30} {'E2E'}")
    print("-" * 75)
    for a in agents:
        caps = ", ".join(a.get("capabilities", [])) or "aucune"
        roles = ", ".join(a.get("roles", [])) or "standard"
        e2e = "🔒 Oui" if a.get("public_key") else "🔓 Non"
        print(f"{a['name']:<20} {roles:<18} {caps:<30} {e2e}")
    print()
    await agent.ws.close()


async def run_ping(args):
    agent = NexusAgent(name="cli_pinger", roles=["admin"], encrypt=False)
    await agent.connect()
    target = args.agent
    print(f"\033[33m📡 Ping vers '{target}'...\033[0m")
    start_time = time.time()
    try:
        identity = await agent.who_is(target, timeout=5.0)
        latency_ms = (time.time() - start_time) * 1000
        print(f"\033[32m✓ Réponse de '{target}' : en ligne | RTT = {latency_ms:.2f} ms\033[0m")
        print(f"  • ID : {identity.get('agent_id')}")
        print(f"  • Capacités : {identity.get('capabilities')}")
        print(f"  • Empreinte : {identity.get('fingerprint')[:16]}...")
    except Exception as e:
        print(f"\033[31m❌ Échec du ping vers '{target}' : {e}\033[0m")
    finally:
        await agent.ws.close()


async def run_ask(args):
    agent = NexusAgent(name="cli_caller", roles=["admin"])
    await agent.connect()
    target = args.agent
    question = args.question
    print(f"\033[33m📤 Envoi de la requête à '{target}' (Chiffrée E2E)...\033[0m")
    try:
        response = await agent.ask(to=target, content=question, timeout=10.0)
        print(f"\n\033[32m🎯 Réponse déchiffrée de '{target}' :\033[0m")
        if isinstance(response, (dict, list)):
            print(json.dumps(response, indent=2, ensure_ascii=False))
        else:
            print(f"  {response}")
    except Exception as e:
        print(f"\033[31m❌ Erreur : {e}\033[0m")
    finally:
        await agent.ws.close()


async def run_task(args):
    agent = NexusAgent(name="cli_orchestrator", roles=["admin"])
    await agent.connect()
    target = args.agent
    title = args.title
    try: input_data = json.loads(args.data)
    except json.JSONDecodeError: input_data = {"raw": args.data}

    print(f"\033[33m📝 Délégation de la tâche '{title}' à '{target}'...\033[0m")
    try:
        result = await agent.submit_task(title=title, assignee=target, input_data=input_data, timeout=15.0)
        print(f"\n\033[32m✅ Tâche exécutée avec succès par '{target}' !\033[0m")
        print(f"\033[36mRésultat retourné :\033[0m")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\033[31m❌ Échec de la tâche : {e}\033[0m")
    finally:
        await agent.ws.close()


def run_keygen(args):
    print("\033[33m🔑 Génération d'une paire de clés RSA-2048 & d'une identité Nexus...\033[0m\n")
    kp = generate_keypair()
    pk_pem = get_public_key_pem(kp)
    name = args.name or "custom_agent"
    caps = args.capabilities.split(",") if args.capabilities else ["compute"]
    roles = args.roles.split(",") if args.roles else ["worker"]
    identity = AgentIdentity(name=name, capabilities=caps, roles=roles, public_key=pk_pem)
    print(f"\033[32m✓ Identité générée avec succès :\033[0m")
    print(f"  • Nom         : {identity.name}")
    print(f"  • ID Unique   : {identity.agent_id}")
    print(f"  • Empreinte   : {identity.fingerprint}")
    print(f"  • Rôles       : {identity.roles}")
    print(f"  • Capacités   : {identity.capabilities}")
    print(f"\n\033[36mClé publique PEM :\033[0m\n{pk_pem}")


def run_hub(args):
    import websockets
    from nexus_sdk.message import MessageType, NexusMessage
    from nexus_sdk.identity import AgentIdentity
    from nexus_sdk.task import NexusTask, TaskStatus
    import secrets, jwt

    HUB_SECRET_KEY = secrets.token_hex(32)
    agents = {}
    identity_registry = {}
    task_registry = {}
    dashboard_observers = set()

    def generate_token(agent_name: str, agent_id: str, roles: list) -> str:
        return jwt.encode({"agent_name": agent_name, "agent_id": agent_id, "roles": roles, "issued_at": time.time(), "expires_at": time.time() + 3600}, HUB_SECRET_KEY, algorithm="HS256")

    def verify_token(token: str, expected_agent: str) -> bool:
        try:
            p = jwt.decode(token, HUB_SECRET_KEY, algorithms=["HS256"])
            return p.get("agent_name") == expected_agent and p.get("expires_at", 0) >= time.time()
        except Exception:
            return False

    async def broadcast_telemetry(event_type: str, data: dict):
        if not dashboard_observers: return
        payload = json.dumps({"type": "telemetry_event", "content": {"event": event_type, **data}})
        for ws in list(dashboard_observers):
            try: await ws.send(payload)
            except Exception: dashboard_observers.discard(ws)

    async def handle_agent(websocket):
        agent_name = None
        try:
            async for raw_data in websocket:
                try: msg = NexusMessage.from_json(raw_data)
                except Exception: continue

                if msg.type == MessageType.REGISTER:
                    agent_name = msg.sender
                    d = msg.content or {}
                    identity = AgentIdentity.from_dict({"name": agent_name, "agent_id": d.get("agent_id"), "capabilities": d.get("capabilities", []), "roles": d.get("roles", ["standard"]), "permissions": d.get("permissions", []), "created_at": d.get("created_at"), "metadata": d.get("metadata", {}), "public_key": d.get("public_key")})
                    
                    if "observer" in identity.roles:
                        dashboard_observers.add(websocket)
                        for aname, aident in identity_registry.items():
                            if aname in agents and aname != agent_name:
                                await websocket.send(json.dumps({"type": "telemetry_event", "content": {"event": "agent_connected", "agent": aident.to_dict()}}))

                    agents[agent_name] = websocket
                    identity_registry[agent_name] = identity
                    token = generate_token(agent_name, identity.agent_id, identity.roles)
                    print(f"\033[32m[+] Agent connecté :\033[0m {agent_name} | Rôles: {identity.roles}")
                    await websocket.send(NexusMessage(type=MessageType.REGISTERED, sender="hub", to=agent_name, content={"status": "ready", "agent_id": identity.agent_id, "fingerprint": identity.fingerprint, "token": token, "online_agents": list(agents.keys())}).to_json())

                    if "observer" not in identity.roles:
                        await broadcast_telemetry("agent_connected", {"agent": identity.to_dict()})

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE, MessageType.WHO_IS, MessageType.DISCOVER, MessageType.TASK_SUBMIT, MessageType.TASK_UPDATE):
                    if not msg.token or not verify_token(msg.token, msg.sender):
                        await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="Token invalide.").to_json())
                        continue

                    if msg.type == MessageType.DISCOVER:
                        q = msg.content or {}
                        req_caps = set(q.get("capabilities", []))
                        res = [
                            {"name": i.name, "agent_id": i.agent_id, "capabilities": i.capabilities, "roles": i.roles, "public_key": i.public_key, "online": n in agents}
                            for n, i in identity_registry.items()
                            if (not req_caps or req_caps.issubset(set(i.capabilities))) and (n in agents)
                        ]
                        await websocket.send(NexusMessage(type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender, reply_to=msg.id, content={"query": q, "count": len(res), "agents": res}, token=msg.token).to_json())

                    elif msg.type == MessageType.TASK_SUBMIT:
                        task = NexusTask.from_dict(msg.content)
                        task_registry[task.task_id] = task
                        print(f"\033[36m[📝 TÂCHE]\033[0m {task.orchestrator} ➜ {task.assignee} | '{task.title}'")
                        await broadcast_telemetry("task_submitted", {"task_id": task.task_id, "title": task.title, "orchestrator": task.orchestrator, "assignee": task.assignee})
                        if task.assignee in agents:
                            await agents[task.assignee].send(NexusMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=msg.id, content=task.to_dict(), token=msg.token).to_json())
                        else:
                            await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content=f"'{task.assignee}' hors ligne.", token=msg.token).to_json())

                    elif msg.type == MessageType.TASK_UPDATE:
                        td = msg.content
                        tid = td.get("task_id")
                        if tid in task_registry:
                            task_registry[tid] = NexusTask.from_dict(td)
                            if td.get("status") == "completed":
                                await broadcast_telemetry("task_completed", {"task_id": tid})
                            orch = td.get("orchestrator")
                            if orch in agents:
                                await agents[orch].send(NexusMessage(type=MessageType.TASK_UPDATE, sender="hub", to=orch, content=td, token=msg.token).to_json())

                    elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                        target = msg.to
                        if target in agents:
                            await agents[target].send(msg.to_json())
                            await broadcast_telemetry("message_routed", {"sender": msg.sender, "to": target})
                            await websocket.send(NexusMessage(type=MessageType.ACK, sender="hub", to=msg.sender, reply_to=msg.id, content={"status": "delivered"}, token=msg.token).to_json())

                    elif msg.type == MessageType.WHO_IS:
                        tn = msg.content
                        if tn in identity_registry:
                            await websocket.send(NexusMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[tn].to_dict(), token=msg.token).to_json())
        except Exception:
            pass
        finally:
            if agent_name:
                agents.pop(agent_name, None)
                dashboard_observers.discard(websocket)
                print(f"\033[31m[-] Agent déconnecté :\033[0m {agent_name}")
                await broadcast_telemetry("agent_disconnected", {"agent_name": agent_name})

    async def start_server():
        port = args.port
        print(f"\033[32m✓ Nexus Hub démarré avec télémétrie sur ws://localhost:{port}\033[0m")
        print("  En attente de connexions... (Ctrl+C pour arrêter)\n")
        async with websockets.serve(handle_agent, "0.0.0.0", port):
            await asyncio.Future()

    asyncio.run(start_server())


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Nexus Protocol Developer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Command: hub
    hub_parser = subparsers.add_parser("hub", help="Démarrer le Hub Nexus")
    hub_parser.add_argument("--port", type=int, default=8765, help="Port d'écoute (défaut: 8765)")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Lancer l'interface Web Mission Control")
    dash_parser.add_argument("--port", type=int, default=8080, help="Port Web (défaut: 8080)")

    # Command: discover
    disc_parser = subparsers.add_parser("discover", help="Rechercher des agents")
    disc_parser.add_argument("--capability", "-c", type=str, help="Capacité")
    disc_parser.add_argument("--role", "-r", type=str, help="Rôle")

    # Command: ping
    ping_parser = subparsers.add_parser("ping", help="Tester un agent")
    ping_parser.add_argument("agent", type=str, help="Nom de l'agent")

    # Command: ask
    ask_parser = subparsers.add_parser("ask", help="Poser une question")
    ask_parser.add_argument("agent", type=str, help="Nom de l'agent")
    ask_parser.add_argument("question", type=str, help="Question")

    # Command: task
    task_parser = subparsers.add_parser("task", help="Déléguer une tâche")
    task_parser.add_argument("agent", type=str, help="Nom de l'agent")
    task_parser.add_argument("title", type=str, help="Titre")
    task_parser.add_argument("data", type=str, help="Données JSON")

    # Command: keygen
    key_parser = subparsers.add_parser("keygen", help="Générer clés & identité")
    key_parser.add_argument("--name", "-n", type=str, help="Nom")
    key_parser.add_argument("--capabilities", "-c", type=str, help="Capacités")
    key_parser.add_argument("--roles", "-r", type=str, help="Rôles")

    # Command: docs
    doc_parser = subparsers.add_parser("docs", help="Afficher documentation")
    doc_parser.add_argument("topic", choices=["rfc", "security", "api"], help="Thème")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "hub": run_hub(args)
    elif args.command == "dashboard": run_dashboard(args)
    elif args.command == "discover": asyncio.run(run_discover(args))
    elif args.command == "ping": asyncio.run(run_ping(args))
    elif args.command == "ask": asyncio.run(run_ask(args))
    elif args.command == "task": asyncio.run(run_task(args))
    elif args.command == "keygen": run_keygen(args)
    elif args.command == "docs": run_docs(args)


if __name__ == "__main__":
    main()
