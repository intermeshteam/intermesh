import argparse
import asyncio
import json
import os
import sys
import time
import websockets
import jwt

from nexus_sdk.message import MessageType, NexusMessage
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask, TaskStatus
from nexus_sdk.audit import ImmutableAuditLog
from nexus_sdk.ratelimit import RateLimiter
from nexus_sdk.secret import resolve_hub_secret
from nexus_sdk.store import NexusStore
from nexus_sdk.apikeys import ApiKeyStore
from nexus_sdk.admin import AdminContext, AdminError, MUTATING, authorize, execute

# Résolue au démarrage dans main(), pas à l'import : écrire un fichier de
# clé comme effet de bord d'un import serait inattendu.
HUB_SECRET_KEY = None
TOKEN_EXPIRY_SECONDS = 3600

# Chargé au démarrage depuis une source externe (voir nexus_sdk.apikeys).
# Seules les empreintes SHA-256 des clés sont conservées en mémoire.
api_keys = ApiKeyStore()

# `agents` mappe un nom vers une connexion WebSocket vivante : être « en
# ligne » est une propriété du processus courant, jamais un fait durable.
# C'est le seul registre qui ne doit pas survivre à un redémarrage.
agents = {}
peered_hubs = {}

# Consoles et dashboards abonnés au flux temps réel.
observers = set()

# Rechargés depuis le magasin au démarrage, dans main().
identity_registry = {}
task_registry = {}
store = None
audit_log = ImmutableAuditLog()

rate_limiter = RateLimiter(default_rate=15.0, default_burst=20.0)


def remember_identity(identity) -> None:
    """Enregistre une identité en mémoire et sur disque."""
    identity_registry[identity.qualified_name] = identity
    if store:
        store.save_identity(identity)


def remember_task(task) -> None:
    """Enregistre une tâche en mémoire et sur disque."""
    task_registry[task.task_id] = task
    if store:
        store.save_task(task)


def generate_token(agent_name: str, agent_id: str, roles: list,
                   auth_method: str = "self_declared") -> str:
    """
    `auth_method` distingue une identité prouvée par clé d'API d'une
    identité simplement déclarée à l'enregistrement. Il est porté par le
    JWT, donc signé par le Hub et infalsifiable par le client — c'est ce
    qui permet de refuser l'administration à un agent qui s'est
    lui-même attribué le rôle admin.
    """
    payload = {
        "agent_name": agent_name, "agent_id": agent_id, "roles": roles,
        "auth_method": auth_method,
        "issued_at": time.time(), "expires_at": time.time() + TOKEN_EXPIRY_SECONDS, "issuer": "nexus-hub"
    }
    return jwt.encode(payload, HUB_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, HUB_SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


async def broadcast(event: str, data: dict) -> None:
    """Diffuse un événement aux consoles abonnées, sans jamais bloquer le routage."""
    if not observers:
        return
    payload = NexusMessage(
        type=MessageType.TELEMETRY, sender="hub",
        content={"event": event, "at": time.time(), **data},
    ).to_json()
    for ws in list(observers):
        try:
            await ws.send(payload)
        except Exception:
            observers.discard(ws)


def verify_token(token: str, expected_agent: str) -> bool:
    try:
        p = jwt.decode(token, HUB_SECRET_KEY, algorithms=["HS256"])
        return p.get("agent_name") == expected_agent and p.get("expires_at", 0) >= time.time()
    except Exception:
        return False


def unfinished_tasks_for(assignee: str) -> list:
    """Tâches confiées à cet agent et jamais menées à terme."""
    return [
        t for t in task_registry.values()
        if t.assignee == assignee
        and t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
    ]


async def resume_unfinished_tasks(agent_name: str, websocket, token: str) -> None:
    """
    Réassigne à un agent qui vient de se connecter les tâches restées en
    suspens — typiquement celles interrompues par un arrêt du Hub, ou par
    la déconnexion de l'agent lui-même.

    Une tâche RUNNING est repassée à PENDING avant réémission : le travail
    précédent est perdu, prétendre le contraire induirait l'orchestrateur
    en erreur. Les exécutants doivent donc être idempotents.
    """
    pending = unfinished_tasks_for(agent_name)
    if not pending:
        return

    print(f"\033[36m↻ Reprise de {len(pending)} tâche(s) pour {agent_name}\033[0m")

    for task in pending:
        was = task.status.value
        task.update_status(TaskStatus.PENDING, output_data=task.output_data)
        remember_task(task)
        audit_log.log("TASK_RESUMED", "hub", agent_name,
                      {"task_id": task.task_id, "title": task.title, "previous_status": was})
        await websocket.send(NexusMessage(
            type=MessageType.TASK_ASSIGN, sender="hub", to=agent_name,
            content=task.to_dict(), token=token,
        ).to_json())


async def deliver_task(task) -> bool:
    """Pousse une tâche à son exécutant s'il est connecté."""
    ws = agents.get(task.assignee)
    if ws is None:
        return False
    await ws.send(NexusMessage(
        type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee,
        content=task.to_dict()).to_json())
    return True


def admin_context(my_org: str) -> AdminContext:
    return AdminContext(
        agents=agents, identity_registry=identity_registry,
        task_registry=task_registry, audit_log=audit_log,
        api_keys=api_keys, peered_hubs=peered_hubs, store=store,
        my_org=my_org, remember_task=remember_task,
        send_to_agent=deliver_task,
    )


async def connect_to_peer(peer_org: str, peer_url: str, my_org: str):
    while True:
        try:
            ws = await websockets.connect(peer_url)
            init_msg = NexusMessage(type=MessageType.PEER_CONNECT, sender=my_org, content={"org_id": my_org})
            await ws.send(init_msg.to_json())
            res = NexusMessage.from_json(await ws.recv())

            if res.type == MessageType.PEER_CONNECTED:
                peered_hubs[peer_org] = ws
                audit_log.log("PEERING_ESTABLISHED", my_org, peer_org, {"peer_url": peer_url})
                print(f"\033[32m🌐 [FÉDÉRATION] Peering actif avec '{peer_org}' ({peer_url})\033[0m")
                await listen_peer(ws, peer_org, my_org)
                break
        except Exception:
            await asyncio.sleep(1)


async def listen_peer(ws, peer_org: str, my_org: str):
    try:
        async for raw in ws:
            msg = NexusMessage.from_json(raw)
            if msg.type == MessageType.FEDERATION_RELAY:
                inner_dict = msg.content
                inner_msg = NexusMessage.from_dict(inner_dict)
                target = inner_msg.to

                if inner_msg.type == MessageType.WHO_IS:
                    target_name = inner_msg.content
                    if target_name in identity_registry:
                        ident_resp = NexusMessage(type=MessageType.IDENTITY, sender="hub", to=inner_msg.sender, reply_to=inner_msg.id, content=identity_registry[target_name].to_dict())
                        await ws.send(NexusMessage(type=MessageType.FEDERATION_RELAY, sender=my_org, to=inner_msg.sender, content=ident_resp.to_dict()).to_json())

                elif inner_msg.type == MessageType.TASK_SUBMIT:
                    task = NexusTask.from_dict(inner_msg.content)
                    remember_task(task)
                    audit_log.log("TASK_RELAYED_IN", inner_msg.sender, task.assignee, {"task_id": task.task_id, "title": task.title})
                    if task.assignee in agents:
                        await agents[task.assignee].send(NexusMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=inner_msg.id, content=task.to_dict()).to_json())

                elif inner_msg.type == MessageType.TASK_UPDATE:
                    td = inner_msg.content
                    tid = td.get("task_id")
                    if tid in task_registry: remember_task(NexusTask.from_dict(td))
                    orch = td.get("orchestrator")
                    if orch in agents: await agents[orch].send(inner_msg.to_json())

                elif inner_msg.type in (MessageType.RESPONSE, MessageType.IDENTITY, MessageType.ERROR, MessageType.MESSAGE, MessageType.REQUEST):
                    if target in agents: await agents[target].send(inner_msg.to_json())

    except websockets.ConnectionClosed:
        peered_hubs.pop(peer_org, None)


async def handle_agent(websocket, my_org: str):
    agent_name = None
    try:
        async for raw_data in websocket:
            try:
                msg = NexusMessage.from_json(raw_data)
            except Exception as e:
                await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", content=str(e)).to_json())
                continue

            if msg.type == MessageType.PEER_CONNECT:
                remote_org = msg.sender
                peered_hubs[remote_org] = websocket
                print(f"\033[32m🌐 [FÉDÉRATION] Peering accepté de '{remote_org}'\033[0m")
                audit_log.log("PEERING_ACCEPTED", remote_org, my_org)
                await websocket.send(NexusMessage(type=MessageType.PEER_CONNECTED, sender=my_org, content={"status": "peered"}).to_json())
                await listen_peer(websocket, remote_org, my_org)
                return

            elif msg.type == MessageType.REGISTER:
                d = msg.content or {}
                raw_name = msg.sender
                
                api_key = d.get("api_key")
                auth_method = "api_key" if api_key else "self_declared"
                if api_key:
                    key_info = api_keys.lookup(api_key)
                    if key_info is None:
                        # Ne jamais journaliser la clé présentée : le journal
                        # d'audit est lisible par plus de monde qu'elle.
                        audit_log.log("AUTH_FAILED", raw_name, None, {"reason": "INVALID_API_KEY"})
                        await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content="API Key Entreprise invalide.").to_json())
                        continue
                    org_id = key_info["org_id"]
                    roles = key_info["roles"]
                    perms = key_info["permissions"]
                else:
                    org_id = d.get("org_id", my_org)
                    roles = d.get("roles", ["standard"])
                    perms = d.get("permissions", [])

                identity = AgentIdentity.from_dict({
                    "name": raw_name, "org_id": org_id, "agent_id": d.get("agent_id"),
                    "capabilities": d.get("capabilities", []), "roles": roles,
                    "permissions": perms, "created_at": d.get("created_at"),
                    "metadata": d.get("metadata", {}), "public_key": d.get("public_key")
                })

                agent_name = identity.qualified_name
                agents[agent_name] = websocket
                remember_identity(identity)
                token = generate_token(agent_name, identity.agent_id, identity.roles, auth_method)

                audit_log.log("AGENT_REGISTERED", agent_name, None, {"roles": identity.roles, "caps": identity.capabilities})
                print(f"\033[32m[+] Agent connecté :\033[0m {agent_name} | Rôles: {identity.roles}")
                
                # Renvoyer les rôles et permissions confirmés par le Hub
                await websocket.send(NexusMessage(type=MessageType.REGISTERED, sender="hub", to=agent_name, content={
                    "status": "ready", "agent_id": identity.agent_id, "qualified_name": agent_name,
                    "roles": identity.roles, "permissions": identity.permissions, "org_id": identity.org_id,
                    "token": token, "online_agents": list(agents.keys())
                }).to_json())

                # Une identité admin prouvée par clé d'API reçoit la
                # télémétrie sans avoir à réclamer le rôle observer : les
                # rôles viennent de la clé, pas de la déclaration du client.
                if "observer" in identity.roles or (
                    auth_method == "api_key" and "admin" in identity.roles
                ):
                    observers.add(websocket)

                await broadcast("agent_connected", {
                    "name": agent_name, "roles": identity.roles,
                    "capabilities": identity.capabilities,
                    "org_id": identity.org_id,
                    "auth_method": auth_method,
                })

                await resume_unfinished_tasks(agent_name, websocket, token)

            elif msg.type == MessageType.ADMIN_REQUEST:
                payload = decode_token(msg.token or "")
                content = msg.content or {}
                command = content.get("command", "")

                if payload is None or payload.get("agent_name") != msg.sender:
                    audit_log.log("ADMIN_DENIED", msg.sender, None, {"reason": "BAD_TOKEN", "command": command})
                    await websocket.send(NexusMessage(
                        type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"ok": False, "error": "Token invalide."}).to_json())
                    continue

                try:
                    authorize(payload)
                except AdminError as exc:
                    audit_log.log("ADMIN_DENIED", msg.sender, None,
                                  {"reason": str(exc), "command": command})
                    await broadcast("admin_denied", {"actor": msg.sender, "command": command})
                    await websocket.send(NexusMessage(
                        type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"ok": False, "error": str(exc)}).to_json())
                    continue

                try:
                    result = await execute(command, content.get("params") or {}, admin_context(my_org))
                    if command in MUTATING:
                        # Toute mutation est tracée avec son auteur. La
                        # valeur d'une clé créée n'est jamais journalisée.
                        audit_log.log("ADMIN_ACTION", msg.sender, None,
                                      {"command": command,
                                       "params": {k: v for k, v in (content.get("params") or {}).items()
                                                  if k not in ("key",)}})
                        await broadcast("admin_action", {"actor": msg.sender, "command": command})
                    await websocket.send(NexusMessage(
                        type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"ok": True, "command": command, "result": result}).to_json())
                except AdminError as exc:
                    await websocket.send(NexusMessage(
                        type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"ok": False, "error": str(exc)}).to_json())
                except Exception as exc:
                    audit_log.log("ADMIN_FAILED", msg.sender, None, {"command": command, "error": str(exc)})
                    await websocket.send(NexusMessage(
                        type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"ok": False, "error": f"Erreur interne : {exc}"}).to_json())

            elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE, MessageType.TASK_SUBMIT, MessageType.TASK_UPDATE, MessageType.WHO_IS, MessageType.DISCOVER):
                if not msg.token or not verify_token(msg.token, msg.sender):
                    audit_log.log("TOKEN_REJECTED", msg.sender, msg.to)
                    await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="Token invalide.").to_json())
                    continue

                if not rate_limiter.is_allowed(msg.sender):
                    audit_log.log("RATE_LIMIT_EXCEEDED", msg.sender, msg.to)
                    await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="RATE_LIMIT_EXCEEDED: Trop de requêtes par seconde.").to_json())
                    continue

                if msg.type == MessageType.WHO_IS:
                    target_name = msg.content
                    if "/" in target_name and target_name.split("/")[0] != my_org:
                        target_org = target_name.split("/")[0]
                        if target_org in peered_hubs:
                            await peered_hubs[target_org].send(NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=target_name, content=msg.to_dict()).to_json())
                            continue
                    elif target_name in identity_registry:
                        await websocket.send(NexusMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[target_name].to_dict(), token=msg.token).to_json())
                        continue

                elif msg.type == MessageType.TASK_SUBMIT:
                    task = NexusTask.from_dict(msg.content)
                    target = task.assignee
                    audit_log.log("TASK_SUBMITTED", task.orchestrator, target, {"task_id": task.task_id, "title": task.title})

                    if target and "/" in target and target.split("/")[0] != my_org:
                        target_org = target.split("/")[0]
                        if target_org in peered_hubs:
                            remember_task(task)
                            await peered_hubs[target_org].send(NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=target, content=msg.to_dict()).to_json())
                            continue

                    remember_task(task)
                    await broadcast("task_submitted", {
                        "task_id": task.task_id, "title": task.title,
                        "orchestrator": task.orchestrator, "assignee": task.assignee,
                    })
                    if task.assignee in agents:
                        await agents[task.assignee].send(NexusMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=msg.id, content=task.to_dict(), token=msg.token).to_json())
                    else:
                        await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content=f"'{task.assignee}' hors ligne.", token=msg.token).to_json())

                elif msg.type == MessageType.TASK_UPDATE:
                    td = msg.content
                    tid = td.get("task_id")
                    if tid in task_registry: remember_task(NexusTask.from_dict(td))
                    audit_log.log("TASK_UPDATED", msg.sender, None, {"task_id": tid, "status": td.get("status")})
                    await broadcast("task_updated", {
                        "task_id": tid, "status": td.get("status"),
                        "assignee": msg.sender, "title": td.get("title"),
                        "error_message": td.get("error_message"),
                    })
                    orch = td.get("orchestrator")
                    if orch in agents:
                        await agents[orch].send(NexusMessage(type=MessageType.TASK_UPDATE, sender="hub", to=orch, content=td, token=msg.token).to_json())
                    elif orch and "/" in orch and orch.split("/")[0] in peered_hubs:
                        await peered_hubs[orch.split("/")[0]].send(NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=orch, content=msg.to_dict()).to_json())

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                    target = msg.to
                    audit_log.log("MESSAGE_ROUTED", msg.sender, target, {"type": msg.type.value})
                    await broadcast("message_routed", {
                        "sender": msg.sender, "to": target, "type": msg.type.value,
                    })
                    if target and "/" in target and target.split("/")[0] != my_org:
                        target_org = target.split("/")[0]
                        if target_org in peered_hubs:
                            await peered_hubs[target_org].send(NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=target, content=msg.to_dict()).to_json())
                            continue
                    if target in agents:
                        await agents[target].send(msg.to_json())
                    else:
                        await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content=f"'{target}' introuvable.", token=msg.token).to_json())

    except websockets.ConnectionClosed:
        pass
    finally:
        observers.discard(websocket)
        if agent_name and agent_name in agents:
            del agents[agent_name]
            audit_log.log("AGENT_DISCONNECTED", agent_name)
            asyncio.create_task(broadcast("agent_disconnected", {"name": agent_name}))
            print(f"\033[31m[-] Agent déconnecté :\033[0m {agent_name}")


async def main():
    parser = argparse.ArgumentParser(description="Nexus Hub Enterprise")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute")
    parser.add_argument("--org", type=str, default="default", help="Nom organisation")
    parser.add_argument("--peer", type=str, help="Peering: 'org=ws://host:port'")
    parser.add_argument("--secret-file", type=str, default=None,
                        help="Fichier de clé JWT (défaut: ~/.nexus/hub_secret)")
    parser.add_argument("--ephemeral-secret", action="store_true",
                        help="Clé jetable : tous les tokens meurent au redémarrage")
    parser.add_argument("--state-file", type=str, default=None,
                        help="Base d'état SQLite (défaut: ~/.nexus/hub_state.db)")
    parser.add_argument("--ephemeral-state", action="store_true",
                        help="État en mémoire : tout est perdu à l'arrêt")
    parser.add_argument("--dev-api-keys", action="store_true",
                        help="Active des clés d'API de démonstration PUBLIQUES (tests uniquement)")
    args = parser.parse_args()

    global HUB_SECRET_KEY, store, identity_registry, task_registry, audit_log, api_keys
    try:
        HUB_SECRET_KEY, secret_source = resolve_hub_secret(
            secret_file=args.secret_file,
            ephemeral=args.ephemeral_secret,
        )
    except ValueError as exc:
        print(f"\033[31m❌ Clé de signature invalide : {exc}\033[0m")
        sys.exit(1)

    try:
        api_keys = ApiKeyStore.load(dev_keys=args.dev_api_keys)
    except ValueError as exc:
        print(f"\033[31m❌ Clés d'API illisibles : {exc}\033[0m")
        sys.exit(1)

    store = NexusStore(path=args.state_file, ephemeral=args.ephemeral_state)
    identity_registry.update(store.load_identities())
    task_registry.update(store.load_tasks())

    # Le journal reprend la chaîne existante ; chaque nouvelle entrée est
    # écrite immédiatement via le callback, sans quoi un arrêt brutal
    # perdrait les derniers événements — exactement ceux qui comptent.
    audit_log = ImmutableAuditLog(
        entries=store.load_audit(),
        on_append=store.append_audit,
    )

    persistent = not secret_source.startswith("éphémère")
    secret_status = "\033[32mPERSISTANTE\033[0m" if persistent else "\033[33mÉPHÉMÈRE\033[0m"
    state_status = "\033[33mÉPHÉMÈRE\033[0m" if store.ephemeral else "\033[32mPERSISTANT\033[0m"

    print("=" * 60)
    print(f"  NEXUS HUB v1.4 — Enterprise Infrastructure")
    print(f"  Audit Cryptographique : \033[32mACTIF\033[0m | Rate Limiting : \033[32mACTIF\033[0m")
    print(f"  Clé de signature JWT  : {secret_status} — {secret_source}")
    print(f"  État du Hub           : {state_status} — {store.description}")
    print(f"  Comptes de service    : {len(api_keys)} clé(s) — {api_keys.source}")
    print("=" * 60)

    if args.dev_api_keys:
        print("\033[31m⚠️  Clés d'API de DÉMONSTRATION actives — elles sont publiques.\033[0m")
        print("   N'utilisez jamais --dev-api-keys en production.")

    if not persistent:
        print("\033[33m⚠️  Les tokens émis seront invalidés au prochain redémarrage.\033[0m")
    if store.ephemeral:
        print("\033[33m⚠️  Identités, tâches et journal d'audit seront perdus à l'arrêt.\033[0m")

    restored = len(identity_registry) or len(task_registry) or len(audit_log.chain) > 1
    if restored:
        counts = store.count_tasks_by_status()
        pending = counts.get("pending", 0) + counts.get("running", 0)
        print(
            f"\033[36m↻ État restauré :\033[0m {len(identity_registry)} identité(s), "
            f"{len(task_registry)} tâche(s) dont {pending} inachevée(s), "
            f"{len(audit_log.chain)} entrée(s) d'audit"
        )
        if not audit_log.verify_integrity():
            print(
                "\033[31m🚨 ALERTE : la chaîne d'audit persistée est rompue.\033[0m\n"
                "   Le journal a été modifié en dehors du Hub. "
                "Traitez-le comme compromis et enquêtez avant de poursuivre."
            )
        elif len(audit_log.chain) > 1:
            print("\033[32m✓ Intégrité de la chaîne d'audit vérifiée.\033[0m")
        if pending:
            print(
                f"\033[33m↻ {pending} tâche(s) inachevée(s) : elles seront "
                "réassignées dès que leur exécutant se reconnectera.\033[0m"
            )

    if args.peer:
        peer_org, peer_url = args.peer.split("=")
        asyncio.create_task(connect_to_peer(peer_org, peer_url, args.org))

    async with websockets.serve(lambda ws: handle_agent(ws, args.org), "0.0.0.0", args.port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
