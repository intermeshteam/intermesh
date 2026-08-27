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

HUB_SECRET_KEY = secrets.token_hex(32)
TOKEN_EXPIRY_SECONDS = 3600
MAX_FREE_AGENTS_QUOTA = 10  # Limite stricte du plan gratuit

ENTERPRISE_API_KEYS = {
    "nx_live_acme_super_secret_key_123": {
        "org_id": "acme", "roles": ["admin", "service_account"], "permissions": ["admin:*"]
    },
    "nx_live_globex_production_key_456": {
        "org_id": "globex", "roles": ["worker", "service_account"], "permissions": ["compute:execute"]
    }
}

agents = {}
identity_registry = {}
task_registry = {}
peered_hubs = {}

audit_log = ImmutableAuditLog()
rate_limiter = RateLimiter(default_rate=15.0, default_burst=20.0)


def generate_token(agent_name: str, agent_id: str, roles: list) -> str:
    payload = {
        "agent_name": agent_name, "agent_id": agent_id, "roles": roles,
        "issued_at": time.time(), "expires_at": time.time() + TOKEN_EXPIRY_SECONDS, "issuer": "nexus-hub"
    }
    return jwt.encode(payload, HUB_SECRET_KEY, algorithm="HS256")


def verify_token(token: str, expected_agent: str) -> bool:
    try:
        p = jwt.decode(token, HUB_SECRET_KEY, algorithms=["HS256"])
        return p.get("agent_name") == expected_agent and p.get("expires_at", 0) >= time.time()
    except Exception:
        return False


async def handle_agent(websocket, my_org: str):
    agent_name = None
    try:
        async for raw_data in websocket:
            try:
                msg = NexusMessage.from_json(raw_data)
            except Exception as e:
                await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", content=str(e)).to_json())
                continue

            if msg.type == MessageType.REGISTER:
                d = msg.content or {}
                raw_name = msg.sender
                
                # --- VÉRIFICATION DU QUOTA D'AGENTS (MAX 10 EN FREE TIER) ---
                current_active = len([a for a in agents.keys() if not a.endswith("/nexus_dashboard_observer")])
                license_key = d.get("license_key") or os.getenv("NEXUS_LICENSE_KEY")
                
                # Si pas de licence Pro/Enterprise et quota atteint (>= 10 agents)
                if current_active >= MAX_FREE_AGENTS_QUOTA and not license_key:
                    err_msg = f"QUOTA_EXCEEDED: Free tier limit reached ({current_active}/{MAX_FREE_AGENTS_QUOTA} active agents). Upgrade to Pro at https://nexusprotocol.org/pricing"
                    audit_log.log("QUOTA_REJECTED", raw_name, None, {"current": current_active, "max": MAX_FREE_AGENTS_QUOTA})
                    print(f"\033[31m[🚫 QUOTA EXCEEDED]\033[0m Connexion refusée pour '{raw_name}' ({current_active}/{MAX_FREE_AGENTS_QUOTA} agents)")
                    await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content=err_msg).to_json())
                    continue

                api_key = d.get("api_key")
                if api_key:
                    if api_key not in ENTERPRISE_API_KEYS:
                        audit_log.log("AUTH_FAILED", raw_name, None, {"reason": "INVALID_API_KEY"})
                        await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content="API Key Entreprise invalide.").to_json())
                        continue
                    key_info = ENTERPRISE_API_KEYS[api_key]
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
                identity_registry[agent_name] = identity
                token = generate_token(agent_name, identity.agent_id, identity.roles)

                audit_log.log("AGENT_REGISTERED", agent_name, None, {"roles": identity.roles, "caps": identity.capabilities})
                print(f"\033[32m[+] Agent connecté ({len(agents)}/{MAX_FREE_AGENTS_QUOTA}) :\033[0m {agent_name}")
                
                await websocket.send(NexusMessage(type=MessageType.REGISTERED, sender="hub", to=agent_name, content={
                    "status": "ready", "agent_id": identity.agent_id, "qualified_name": agent_name,
                    "roles": identity.roles, "permissions": identity.permissions, "org_id": identity.org_id,
                    "token": token, "online_agents": list(agents.keys())
                }).to_json())

            elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE, MessageType.TASK_SUBMIT, MessageType.TASK_UPDATE, MessageType.WHO_IS, MessageType.DISCOVER):
                if not msg.token or not verify_token(msg.token, msg.sender):
                    await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="Token invalide.").to_json())
                    continue

                if not rate_limiter.is_allowed(msg.sender):
                    await websocket.send(NexusMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="RATE_LIMIT_EXCEEDED").to_json())
                    continue

                if msg.type == MessageType.WHO_IS:
                    tn = msg.content
                    if tn in identity_registry:
                        await websocket.send(NexusMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=identity_registry[tn].to_dict(), token=msg.token).to_json())

                elif msg.type == MessageType.TASK_SUBMIT:
                    task = NexusTask.from_dict(msg.content)
                    task_registry[task.task_id] = task
                    if task.assignee in agents:
                        await agents[task.assignee].send(NexusMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=msg.id, content=task.to_dict(), token=msg.token).to_json())

                elif msg.type == MessageType.TASK_UPDATE:
                    td = msg.content
                    tid = td.get("task_id")
                    if tid in task_registry: task_registry[tid] = NexusTask.from_dict(td)
                    orch = td.get("orchestrator")
                    if orch in agents: await agents[orch].send(NexusMessage(type=MessageType.TASK_UPDATE, sender="hub", to=orch, content=td, token=msg.token).to_json())

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                    target = msg.to
                    if target in agents: await agents[target].send(msg.to_json())

    except websockets.ConnectionClosed:
        pass
    finally:
        if agent_name and agent_name in agents:
            del agents[agent_name]
            print(f"\033[31m[-] Agent déconnecté :\033[0m {agent_name}")


async def main():
    parser = argparse.ArgumentParser(description="Nexus Hub Enterprise with Quota Limit")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute")
    parser.add_argument("--org", type=str, default="default", help="Nom organisation")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  NEXUS HUB v1.5 — Control Plane Quota Enforcement")
    print(f"  Quota Plan Gratuit : \033[36m{MAX_FREE_AGENTS_QUOTA} agents simultanés max\033[0m")
    print("=" * 60)

    async with websockets.serve(lambda ws: handle_agent(ws, args.org), "0.0.0.0", args.port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
