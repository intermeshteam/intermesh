"""
InterMesh Hub v1.7 — Asimov Safety Guardrails + Telemetry + Merkle Audit Log + Remote Kill-Switch.
"""
import argparse
import asyncio
import json
import os
import secrets
import ssl
import sys
import time
import websockets
import jwt

from intermesh.message import MessageType, InterMeshMessage
from intermesh.identity import AgentIdentity
from intermesh.task import InterMeshTask
from intermesh.audit import ImmutableAuditLog
from intermesh.ratelimit import RateLimiter
from intermesh.guardrails import AsimovGuardrailEngine, PolicyViolationError

HUB_SECRET = secrets.token_hex(32)
TOKEN_EXPIRY_SECONDS = 3600
MAX_FREE_AGENTS = 15
MAX_FREE_MESSAGES = 10000

total_messages_counter = 0
is_quota_exhausted = False

agents = {}                 # qualified_name -> websocket
identity_registry = {}      # qualified_name -> identity dict
task_registry = {}          # task_id -> InterMeshTask
peered_hubs = {}            # remote_org -> websocket
observers = set()           # dashboard/topology/security_observer websockets
agent_meta = {}             # qualified_name -> meta dict

audit_log = ImmutableAuditLog()
rate_limiter = RateLimiter(default_rate=20.0, default_burst=30.0)
asimov_engine = AsimovGuardrailEngine()


def make_token(name: str, agent_id: str, roles: list) -> str:
    return jwt.encode(
        {
            "agent_name": name,
            "agent_id": agent_id,
            "roles": roles,
            "issued_at": time.time(),
            "expires_at": time.time() + TOKEN_EXPIRY_SECONDS,
        },
        HUB_SECRET,
        algorithm="HS256",
    )


def verify_token(token: str, name: str) -> bool:
    try:
        p = jwt.decode(token, HUB_SECRET, algorithms=["HS256"])
        return p.get("agent_name") == name and p.get("expires_at", 0) >= time.time()
    except Exception:
        return False


async def broadcast(event: str, data: dict):
    if not observers:
        return
    payload = json.dumps({"type": "telemetry_event", "content": {"event": event, **data}})
    dead = []
    for ws in list(observers):
        try:
            await ws.send(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        observers.discard(ws)


def discover_agents(query: dict) -> list[dict]:
    results = []
    limit = query.get("limit", 15)
    online_only = query.get("online_only", True)
    req_caps = set(query.get("capabilities", []))
    req_roles = set(query.get("roles", []))

    for name, ident in identity_registry.items():
        if online_only and name not in agents:
            continue
        if req_caps and not req_caps.issubset(set(ident.get("capabilities", []))):
            continue
        if req_roles and not req_roles.intersection(set(ident.get("roles", []))):
            continue

        results.append({
            "name": ident.get("name"),
            "qualified_name": ident.get("qualified_name", name),
            "agent_id": ident.get("agent_id"),
            "capabilities": ident.get("capabilities", []),
            "roles": ident.get("roles", []),
            "permissions": ident.get("permissions", []),
            "public_key": ident.get("public_key"),
            "schema": ident.get("schema"),
            "online": name in agents
        })
        if len(results) >= limit:
            break
    return results


def _org_of_name(qname, my_org):
    if qname and "/" in qname:
        return qname.split("/")[0]
    return my_org


async def deliver_or_relay(msg, my_org):
    """Livre localement si l'agent cible est connecté à ce Hub, sinon
    relaie vers le Hub pair correspondant à son organisation."""
    target = msg.to
    if not target:
        return
    if target in agents:
        try:
            await agents[target].send(msg.to_json())
        except Exception:
            pass
        return

    org = _org_of_name(target, my_org)
    peer_ws = peered_hubs.get(org)
    if peer_ws is not None:
        relay = InterMeshMessage(type=MessageType.FEDERATION_RELAY, sender=my_org, to=org, content=msg.to_dict())
        try:
            await peer_ws.send(relay.to_json())
        except Exception:
            pass


def snapshot_agents():
    out = []
    now = time.time()
    for name, meta in agent_meta.items():
        ident = identity_registry.get(name, {})
        out.append(
            {
                "name": name,
                "agent_id": ident.get("agent_id"),
                "roles": ident.get("roles", []),
                "capabilities": ident.get("capabilities", []),
                "status": meta.get("status", "healthy"),
                "connected_at": meta.get("connected_at"),
                "last_seen": meta.get("last_seen", now),
                "msg_count": meta.get("msg_count", 0),
                "online": name in agents,
            }
        )
    return out


async def process_relayed(ws, my_org: str, msg: InterMeshMessage):
    """
    Traite un message reçu d'un Hub pair (déjà déballé d'un
    FEDERATION_RELAY) exactement comme s'il venait d'un agent local :
    la réponse (WHO_IS -> IDENTITY, etc.) repart sur la même connexion,
    ce qui la fait naturellement revenir au Hub d'origine.
    """
    global total_messages_counter

    if msg.type == MessageType.WHO_IS:
        target_name = msg.content
        if target_name in identity_registry:
            await ws.send(InterMeshMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender,
                                        reply_to=msg.id, content=identity_registry[target_name],
                                        token=msg.token).to_json())

    elif msg.type == MessageType.DISCOVER:
        query = msg.content or {}
        matched = discover_agents(query)
        await ws.send(InterMeshMessage(type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender,
                                    reply_to=msg.id,
                                    content={"query": query, "count": len(matched), "agents": matched},
                                    token=msg.token).to_json())

    elif msg.type == MessageType.TASK_SUBMIT:
        task_dict = msg.content or {}
        task_id = task_dict.get("task_id", "unknown")
        assignee = task_dict.get("assignee", "unknown")
        title = task_dict.get("title", "")

        task_registry[task_id] = InterMeshTask.from_dict(task_dict)
        entry = audit_log.log("TASK_SUBMITTED", msg.sender, assignee, {"task_id": task_id, "title": title})
        await broadcast("audit_entry", {"entry": entry.to_dict()})

        assign_msg = InterMeshMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=assignee,
                                   reply_to=msg.id, content=task_dict, token=msg.token)
        await deliver_or_relay(assign_msg, my_org)

    elif msg.type == MessageType.TASK_UPDATE:
        td = msg.content or {}
        tid = td.get("task_id", "unknown")
        status = td.get("status", "unknown")
        orch = td.get("orchestrator")

        if status == "completed":
            entry = audit_log.log("TASK_COMPLETED", msg.sender, orch, {"task_id": tid})
            await broadcast("audit_entry", {"entry": entry.to_dict()})

        update_msg = InterMeshMessage(type=MessageType.TASK_UPDATE, sender=msg.sender, to=orch,
                                   content=td, token=msg.token)
        await deliver_or_relay(update_msg, my_org)

    elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE, MessageType.TASK_ASSIGN):
        await deliver_or_relay(msg, my_org)


async def handle(ws, my_org: str):
    global total_messages_counter, is_quota_exhausted
    name = None
    is_observer = False

    try:
        async for raw in ws:
            try:
                msg = InterMeshMessage.from_json(raw)
            except Exception:
                continue

            # KILL-SWITCH
            if msg.type == "disconnect_agent" or (isinstance(msg.content, dict) and msg.content.get("action") == "kill_agent"):
                target_name = msg.to or (msg.content.get("target_agent") if isinstance(msg.content, dict) else None)
                if target_name and target_name in agents:
                    target_ws = agents[target_name]
                    print(f"\033[31m[KILL-SWITCH]\033[0m Disconnecting '{target_name}' per request from {msg.sender}")
                    
                    entry = audit_log.log("REMOTE_KILL_SWITCH", msg.sender, target_name, {"reason": "Control Plane Revocation"})
                    await broadcast("audit_entry", {"entry": entry.to_dict()})

                    try:
                        await target_ws.send(json.dumps({
                            "type": "error",
                            "content": "DISCONNECTED_BY_ADMIN: Connection terminated from Control Plane Portal."
                        }))
                        await target_ws.close(1000, "Disconnected by Admin")
                    except Exception:
                        pass
                continue

            # PEERING (Hub à Hub)
            if msg.type == MessageType.PEER_CONNECT:
                remote_org = (msg.content or {}).get("org") or msg.sender
                peered_hubs[remote_org] = ws
                await ws.send(InterMeshMessage(type=MessageType.PEER_CONNECTED, sender=my_org, content={"org": my_org}).to_json())
                print(f"\033[36m[peering]\033[0m Pair accepté : {remote_org}")
                continue

            if msg.type == MessageType.FEDERATION_RELAY:
                try:
                    inner = InterMeshMessage.from_dict(msg.content)
                except Exception:
                    continue
                await process_relayed(ws, my_org, inner)
                continue

            # Réponse d'un Hub pair à une requête relayée (WHO_IS -> IDENTITY,
            # DISCOVER -> DISCOVER_RESULT) : à renvoyer telle quelle à l'agent
            # local qui l'a demandée, identifié par `to`.
            if msg.type in (MessageType.IDENTITY, MessageType.DISCOVER_RESULT):
                target = msg.to
                if target in agents:
                    try:
                        await agents[target].send(msg.to_json())
                    except Exception:
                        pass
                continue

            # REGISTER
            if msg.type == MessageType.REGISTER:
                d = msg.content or {}
                roles = d.get("roles", ["standard"])
                raw_name = msg.sender
                org_id = d.get("org_id", my_org)

                if "observer" in roles or str(raw_name).startswith("topology_") or str(raw_name).startswith("nexus_dashboard") or str(raw_name).startswith("agents_dir") or str(raw_name).startswith("security_"):
                    is_observer = True
                    observers.add(ws)
                    await ws.send(json.dumps({
                        "type": "telemetry_event",
                        "content": {
                            "event": "snapshot",
                            "agents": snapshot_agents(),
                            "audit_chain": [e.to_dict() for e in audit_log.chain],
                            "server_time": time.time(),
                        }
                    }))
                    await ws.send(InterMeshMessage(type=MessageType.REGISTERED, sender="hub", to=raw_name, content={"status": "ready", "token": "observer"}).to_json())
                    print(f"[observer] {raw_name} connected")
                    continue

                # QUOTA (15 agents gratuits)
                if len(agents) >= MAX_FREE_AGENTS:
                    err_msg = f"AGENT_QUOTA_EXCEEDED: Free tier limit reached ({len(agents)}/{MAX_FREE_AGENTS} agents)."
                    await ws.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content=err_msg).to_json())
                    continue

                identity = AgentIdentity.from_dict({
                    "name": raw_name, "org_id": org_id, "agent_id": d.get("agent_id"),
                    "capabilities": d.get("capabilities", []), "roles": roles,
                    "permissions": d.get("permissions", []), "created_at": d.get("created_at"),
                    "metadata": d.get("metadata", {}), "public_key": d.get("public_key"),
                    "schema": d.get("schema")
                })
                qname = identity.qualified_name
                name = qname

                # Vérification disjoncteur Asimov
                if asimov_engine.circuit_breaker.is_tripped(qname):
                    await ws.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=qname, content="ASIMOV_GUARDRAIL: Agent is isolated by circuit breaker.").to_json())
                    await ws.close(1008, "Asimov Isolated")
                    continue

                agents[qname] = ws
                identity_registry[qname] = identity.to_dict()
                agent_meta[qname] = {"connected_at": time.time(), "last_seen": time.time(), "msg_count": 0, "status": "healthy"}
                token = make_token(qname, identity.agent_id, identity.roles)

                entry = audit_log.log("AGENT_REGISTERED", qname, "hub", {"roles": identity.roles, "caps": identity.capabilities})
                await ws.send(InterMeshMessage(type=MessageType.REGISTERED, sender="hub", to=qname, content={
                    "status": "ready", "token": token, "qualified_name": qname,
                    "roles": identity.roles, "agent_id": identity.agent_id, "online_agents": list(agents.keys())
                }).to_json())
                
                await broadcast("agent_connected", {"agent": {**identity.to_dict(), "status": "healthy", "online": True}})
                await broadcast("audit_entry", {"entry": entry.to_dict()})
                print(f"\033[32m[+] Agent connected:\033[0m {qname}")

            # DISCOVER
            elif msg.type == MessageType.DISCOVER:
                query = msg.content or {}
                matched = discover_agents(query)
                await ws.send(InterMeshMessage(
                    type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                    content={"query": query, "count": len(matched), "agents": matched}, token=msg.token
                ).to_json())

            # WHO_IS
            elif msg.type == MessageType.WHO_IS:
                target_name = msg.content
                if target_name in identity_registry:
                    await ws.send(InterMeshMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[target_name], token=msg.token).to_json())
                else:
                    org = _org_of_name(target_name, my_org)
                    peer_ws = peered_hubs.get(org)
                    if peer_ws is not None:
                        relay = InterMeshMessage(type=MessageType.FEDERATION_RELAY, sender=my_org, to=org, content=msg.to_dict())
                        try:
                            await peer_ws.send(relay.to_json())
                        except Exception:
                            pass

            # TASK_SUBMIT (INSPECTION PAR ASIMOV GUARDRAILS)
            elif msg.type == MessageType.TASK_SUBMIT:
                task_dict = msg.content or {}
                task_id = task_dict.get("task_id", "unknown")
                assignee = task_dict.get("assignee", "unknown")
                title = task_dict.get("title", "")
                parent_id = task_dict.get("parent_task_id")
                input_data = task_dict.get("input_data")

                # INSPECTION PAR LE MOTEUR ASIMOV
                try:
                    payload_str = str(input_data) if input_data else title
                    asimov_engine.validate_task_submission(
                        agent_name=msg.sender,
                        task_id=task_id,
                        parent_task_id=parent_id,
                        estimated_cost=float(task_dict.get("estimated_cost") or 0.0),
                        payload_text=payload_str,
                        org_id=_org_of_name(msg.sender, my_org),
                    )
                except PolicyViolationError as pve:
                    print(f"\033[31m[🛡️ ASIMOV GUARDRAIL VIOLATION]\033[0m {pve}")
                    entry = audit_log.log("ASIMOV_GUARDRAIL_VIOLATION", msg.sender, assignee, {"rule": pve.rule_name, "reason": str(pve), "task_id": task_id})
                    await broadcast("audit_entry", {"entry": entry.to_dict()})
                    await ws.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content=str(pve), token=msg.token).to_json())
                    continue

                task_registry[task_id] = InterMeshTask.from_dict(task_dict)
                entry = audit_log.log("TASK_SUBMITTED", msg.sender, assignee, {"task_id": task_id, "title": title})
                await broadcast("task_submitted", {"task_id": task_id, "title": title, "orchestrator": msg.sender, "assignee": assignee})
                await broadcast("audit_entry", {"entry": entry.to_dict()})

                assign_msg = InterMeshMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=assignee, reply_to=msg.id, content=task_dict, token=msg.token)
                await deliver_or_relay(assign_msg, my_org)

            # TASK_UPDATE
            elif msg.type == MessageType.TASK_UPDATE:
                td = msg.content or {}
                tid = td.get("task_id", "unknown")
                status = td.get("status", "unknown")
                orch = td.get("orchestrator")

                if status == "completed":
                    entry = audit_log.log("TASK_COMPLETED", msg.sender, orch, {"task_id": tid})
                    await broadcast("task_completed", {"task_id": tid})
                    await broadcast("audit_entry", {"entry": entry.to_dict()})

                update_msg = InterMeshMessage(type=MessageType.TASK_UPDATE, sender=msg.sender, to=orch, content=td, token=msg.token)
                await deliver_or_relay(update_msg, my_org)

            # ROUTING MESSAGES
            elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                if name and name in agent_meta:
                    agent_meta[name]["last_seen"] = time.time()
                    agent_meta[name]["msg_count"] = agent_meta[name].get("msg_count", 0) + 1

                await deliver_or_relay(msg, my_org)

    except websockets.ConnectionClosed:
        pass
    finally:
        if is_observer:
            observers.discard(ws)
        if name and name in agents:
            del agents[name]
            if name in agent_meta:
                agent_meta[name]["status"] = "unhealthy"
            
            entry = audit_log.log("AGENT_DISCONNECTED", name, "hub", {"status": "unhealthy"})
            await broadcast("agent_disconnected", {"agent_name": name, "status": "unhealthy"})
            await broadcast("audit_entry", {"entry": entry.to_dict()})
            print(f"\033[31m[-] Agent disconnected:\033[0m {name}")


async def connect_peer(remote_org: str, url: str, my_org: str):
    """Maintient une connexion sortante vers un Hub pair, avec reconnexion."""
    while True:
        try:
            async with websockets.connect(url) as ws:
                await ws.send(InterMeshMessage(type=MessageType.PEER_CONNECT, sender=my_org,
                                            content={"org": my_org}).to_json())
                reply = InterMeshMessage.from_json(await ws.recv())
                if reply.type == MessageType.PEER_CONNECTED:
                    peered_hubs[remote_org] = ws
                    print(f"\033[36m[peering]\033[0m Connecté au pair '{remote_org}' ({url})")
                try:
                    await handle(ws, my_org)
                finally:
                    peered_hubs.pop(remote_org, None)
        except Exception as exc:
            print(f"\033[33m[peering]\033[0m Connexion à '{remote_org}' ({url}) perdue : {exc}. Nouvel essai...")
        await asyncio.sleep(3)


async def main():
    parser = argparse.ArgumentParser(description="InterMesh Hub Enterprise with Asimov Guardrails")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute")
    parser.add_argument("--org", type=str, default="default", help="Nom organisation")
    parser.add_argument("--peer", action="append", default=[],
                         help="Pair à fédérer, au format ORG=ws://host:port. Répétable.")
    args, _ = parser.parse_known_args()

    print("=" * 60)
    print("  INTERMESH HUB v1.7 — Asimov Safety Guardrails Active")
    print(f"  Max Cascade Depth : 4 | Circuit Breaker Threshold : 3")
    print("=" * 60)

    for spec in args.peer:
        if "=" not in spec:
            print(f"\033[33m[peering]\033[0m --peer ignoré (format attendu ORG=ws://...) : {spec}")
            continue
        remote_org, url = spec.split("=", 1)
        asyncio.create_task(connect_peer(remote_org, url, args.org))

    async with websockets.serve(lambda ws: handle(ws, args.org), "0.0.0.0", args.port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
