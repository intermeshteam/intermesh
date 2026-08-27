"""
Nexus Hub Telemetry + CLI Argument Parser (--port, --org, --peer) + Federation + Merkle Audit.
"""
import argparse
import asyncio
import json
import os
import secrets
import sys
import time
import websockets
import jwt

from nexus_sdk.message import MessageType, NexusMessage
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask, TaskStatus
from nexus_sdk.audit import ImmutableAuditLog
from nexus_sdk.ratelimit import RateLimiter

HUB_SECRET = secrets.token_hex(32)
TOKEN_EXPIRY_SECONDS = 3600

agents = {}             # qualified_name -> websocket
identity_registry = {}  # qualified_name -> identity dict
task_registry = {}      # task_id -> NexusTask
peered_hubs = {}        # remote_org -> websocket
observers = set()       # telemetry observer websockets
agent_meta = {}         # qualified_name -> meta dict

audit_log = ImmutableAuditLog()
rate_limiter = RateLimiter(default_rate=20.0, default_burst=30.0)


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


async def connect_to_peer(peer_org: str, peer_url: str, my_org: str):
    """Établit et maintient un canal de peering sortant vers un Hub distant."""
    while True:
        try:
            ws = await websockets.connect(peer_url)
            init_msg = NexusMessage(
                type=MessageType.PEER_CONNECT,
                sender=my_org,
                content={"org_id": my_org}
            )
            await ws.send(init_msg.to_json())
            res = NexusMessage.from_json(await ws.recv())

            if res.type == MessageType.PEER_CONNECTED:
                peered_hubs[peer_org] = ws
                print(f"\033[32m🌐 [FÉDÉRATION] Peering actif avec '{peer_org}' ({peer_url})\033[0m")
                await listen_peer(ws, peer_org, my_org)
                break
        except Exception:
            await asyncio.sleep(1)


async def listen_peer(ws, peer_org: str, my_org: str):
    """Écoute et route tous les messages relayés par le Hub distant."""
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
                        ident_resp = NexusMessage(
                            type=MessageType.IDENTITY,
                            sender="hub",
                            to=inner_msg.sender,
                            reply_to=inner_msg.id,
                            content=identity_registry[target_name]
                        )
                        relay_back = NexusMessage(
                            type=MessageType.FEDERATION_RELAY,
                            sender=my_org,
                            to=inner_msg.sender,
                            content=ident_resp.to_dict()
                        )
                        await ws.send(relay_back.to_json())

                elif inner_msg.type == MessageType.TASK_SUBMIT:
                    task = NexusTask.from_dict(inner_msg.content)
                    task_registry[task.task_id] = task
                    print(f"\033[36m[🌐 TÂCHE FEDERÉE REÇUE DE {peer_org.upper()}]\033[0m {task.orchestrator} ➜ {task.assignee}")
                    if task.assignee in agents:
                        assign_msg = NexusMessage(
                            type=MessageType.TASK_ASSIGN,
                            sender="hub",
                            to=task.assignee,
                            reply_to=inner_msg.id,
                            content=task.to_dict()
                        )
                        await agents[task.assignee].send(assign_msg.to_json())

                elif inner_msg.type == MessageType.TASK_UPDATE:
                    td = inner_msg.content
                    tid = td.get("task_id")
                    if tid in task_registry:
                        task_registry[tid] = NexusTask.from_dict(td)
                    orch = td.get("orchestrator")
                    if orch in agents:
                        await agents[orch].send(inner_msg.to_json())

                elif inner_msg.type in (MessageType.RESPONSE, MessageType.IDENTITY, MessageType.ERROR, MessageType.MESSAGE, MessageType.REQUEST):
                    if target in agents:
                        await agents[target].send(inner_msg.to_json())

    except websockets.ConnectionClosed:
        pass
    finally:
        peered_hubs.pop(peer_org, None)
        print(f"\033[31m[-] Peering fermé avec '{peer_org}'\033[0m")


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
            "online": name in agents
        })
        if len(results) >= limit:
            break
    return results


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


async def handle(ws, my_org: str):
    name = None
    is_observer = False
    try:
        async for raw in ws:
            try:
                msg = NexusMessage.from_json(raw)
            except Exception:
                continue

            # 1. PEERING ENTRANT D'UN AUTRE HUB
            if msg.type == MessageType.PEER_CONNECT:
                remote_org = msg.sender
                peered_hubs[remote_org] = ws
                print(f"\033[32m🌐 [FÉDÉRATION] Peering entrant accepté depuis '{remote_org}'\033[0m")
                await ws.send(NexusMessage(
                    type=MessageType.PEER_CONNECTED,
                    sender=my_org,
                    content={"status": "peered"}
                ).to_json())
                await listen_peer(ws, remote_org, my_org)
                return

            # 2. REMOTE KILL-SWITCH
            if msg.type == "disconnect_agent" or (isinstance(msg.content, dict) and msg.content.get("action") == "kill_agent"):
                target_name = msg.to or (msg.content.get("target_agent") if isinstance(msg.content, dict) else None)
                if target_name and target_name in agents:
                    target_ws = agents[target_name]
                    print(f"\033[31m[KILL-SWITCH]\033[0m Déconnexion forcée de '{target_name}' demandée par {msg.sender}")
                    try:
                        await target_ws.send(json.dumps({
                            "type": "error",
                            "content": "DISCONNECTED_BY_ADMIN: Connection terminated from Control Plane Portal."
                        }))
                        await target_ws.close(1000, "Disconnected by Admin")
                    except Exception:
                        pass
                continue

            # 3. REGISTER
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
                    await ws.send(NexusMessage(type=MessageType.REGISTERED, sender="hub", to=raw_name, content={"status": "ready", "token": "observer"}).to_json())
                    print(f"[observer] {raw_name} connecté")
                    continue

                identity = AgentIdentity.from_dict({
                    "name": raw_name, "org_id": org_id, "agent_id": d.get("agent_id"),
                    "capabilities": d.get("capabilities", []), "roles": roles,
                    "permissions": d.get("permissions", []), "created_at": d.get("created_at"),
                    "metadata": d.get("metadata", {}), "public_key": d.get("public_key")
                })
                qname = identity.qualified_name
                name = qname
                agents[qname] = ws
                identity_registry[qname] = identity.to_dict()
                agent_meta[qname] = {"connected_at": time.time(), "last_seen": time.time(), "msg_count": 0, "status": "healthy"}
                token = make_token(qname, identity.agent_id, identity.roles)

                entry = audit_log.log("AGENT_REGISTERED", qname, "hub", {"roles": identity.roles, "caps": identity.capabilities})
                await ws.send(NexusMessage(type=MessageType.REGISTERED, sender="hub", to=qname, content={
                    "status": "ready", "token": token, "qualified_name": qname,
                    "roles": identity.roles, "agent_id": identity.agent_id, "online_agents": list(agents.keys())
                }).to_json())

                await broadcast("agent_connected", {"agent": {**identity.to_dict(), "status": "healthy", "online": True}})
                await broadcast("audit_entry", {"entry": entry.to_dict()})
                print(f"\033[32m[+] Agent connecté ({my_org.upper()}) :\033[0m {qname}")

            # 4. DISCOVER
            elif msg.type == MessageType.DISCOVER:
                query = msg.content or {}
                matched = discover_agents(query)
                await ws.send(NexusMessage(
                    type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                    content={"query": query, "count": len(matched), "agents": matched}, token=msg.token
                ).to_json())

            # 5. WHO_IS (LOCAL OU RELAIS PEERING)
            elif msg.type == MessageType.WHO_IS:
                target_name = msg.content
                if "/" in target_name and target_name.split("/")[0] != my_org:
                    target_org = target_name.split("/")[0]
                    if target_org in peered_hubs:
                        relay_env = NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=target_name, content=msg.to_dict())
                        await peered_hubs[target_org].send(relay_env.to_json())
                        continue
                elif target_name in identity_registry:
                    await ws.send(NexusMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[target_name], token=msg.token).to_json())

            # 6. TASK_SUBMIT (LOCAL OU RELAIS PEERING)
            elif msg.type == MessageType.TASK_SUBMIT:
                task_dict = msg.content or {}
                task_id = task_dict.get("task_id", "unknown")
                assignee = task_dict.get("assignee", "unknown")

                entry = audit_log.log("TASK_SUBMITTED", msg.sender, assignee, {"task_id": task_id, "title": task_dict.get("title")})
                await broadcast("task_submitted", {"task_id": task_id, "title": task_dict.get("title"), "orchestrator": msg.sender, "assignee": assignee})
                await broadcast("audit_entry", {"entry": entry.to_dict()})

                if assignee and "/" in assignee and assignee.split("/")[0] != my_org:
                    target_org = assignee.split("/")[0]
                    if target_org in peered_hubs:
                        task_registry[task_id] = NexusTask.from_dict(task_dict)
                        print(f"\033[36m[🌐 RELAY TÂCHE ➜ {target_org.upper()}]\033[0m {msg.sender} ➜ {assignee}")
                        relay_env = NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=assignee, content=msg.to_dict())
                        await peered_hubs[target_org].send(relay_env.to_json())
                        continue

                task_registry[task_id] = NexusTask.from_dict(task_dict)
                if assignee in agents:
                    assign_msg = NexusMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=assignee, reply_to=msg.id, content=task_dict, token=msg.token)
                    await agents[assignee].send(assign_msg.to_json())

            # 7. TASK_UPDATE
            elif msg.type == MessageType.TASK_UPDATE:
                td = msg.content or {}
                tid = td.get("task_id", "unknown")
                status = td.get("status", "unknown")
                orch = td.get("orchestrator")

                if status == "completed":
                    entry = audit_log.log("TASK_COMPLETED", msg.sender, orch, {"task_id": tid})
                    await broadcast("task_completed", {"task_id": tid})
                    await broadcast("audit_entry", {"entry": entry.to_dict()})

                if orch in agents:
                    await agents[orch].send(msg.to_json())
                elif orch and "/" in orch and orch.split("/")[0] in peered_hubs:
                    target_org = orch.split("/")[0]
                    relay_env = NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=orch, content=msg.to_dict())
                    await peered_hubs[target_org].send(relay_env.to_json())

            # 8. ROUTAGE GENERAL
            elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                target = msg.to
                if target and "/" in target and target.split("/")[0] != my_org:
                    target_org = target.split("/")[0]
                    if target_org in peered_hubs:
                        relay_env = NexusMessage(type=MessageType.FEDERATION_RELAY, sender=msg.sender, to=target, content=msg.to_dict())
                        await peered_hubs[target_org].send(relay_env.to_json())
                        continue

                if target in agents:
                    await agents[target].send(msg.to_json())

    except websockets.ConnectionClosed:
        pass
    finally:
        if is_observer:
            observers.discard(ws)
        if name and name in agents:
            del agents[name]
            entry = audit_log.log("AGENT_DISCONNECTED", name, "hub", {"status": "unhealthy"})
            await broadcast("agent_disconnected", {"agent_name": name, "status": "unhealthy"})
            await broadcast("audit_entry", {"entry": entry.to_dict()})
            print(f"\033[31m[-] Agent déconnecté :\033[0m {name}")


async def main():
    parser = argparse.ArgumentParser(description="Nexus Hub Fédéré & Télémétrie")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute")
    parser.add_argument("--org", type=str, default="default", help="Nom organisation")
    parser.add_argument("--peer", type=str, help="Peering: 'org=ws://host:port'")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  NEXUS HUB v1.6 — Federation & Telemetry Engine")
    print(f"  Organisation : \033[36m{args.org.upper()}\033[0m | Port : \033[32m{args.port}\033[0m")
    print("=" * 60)

    if args.peer:
        peer_org, peer_url = args.peer.split("=")
        asyncio.create_task(connect_to_peer(peer_org, peer_url, args.org))

    async with websockets.serve(lambda ws: handle(ws, args.org), "0.0.0.0", args.port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
