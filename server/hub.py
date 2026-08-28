"""
InterMesh Hub — routage central, console d'administration, persistance.
"""
import argparse
import asyncio
import time

import jwt
import websockets

from intermesh.admin import MUTATING, AdminContext, AdminError, authorize, caller_scope
from intermesh.admin import execute as admin_execute
from intermesh.apikeys import ApiKeyStore
from intermesh.audit import ImmutableAuditLog
from intermesh.escrow import EscrowError, EscrowManager
from intermesh.guardrails import AsimovGuardrailEngine, PolicyViolationError
from intermesh.health import HealthCheckHandler
from intermesh.identity import AgentIdentity
from intermesh.message import MessageType, InterMeshMessage
from intermesh.ratelimit import RateLimiter
from intermesh.secret import resolve_hub_secret
from intermesh.store import InterMeshStore
from intermesh.task import InterMeshTask, TaskStatus

TOKEN_EXPIRY_SECONDS = 3600
MAX_FREE_AGENTS = 15

# État partagé du Hub, peuplé par main() au démarrage.
agents: dict[str, "websockets.ServerConnection"] = {}       # qualified_name -> websocket
identity_registry: dict[str, AgentIdentity] = {}             # qualified_name -> AgentIdentity
task_registry: dict[str, InterMeshTask] = {}                     # task_id -> InterMeshTask
peered_hubs: dict[str, object] = {}                           # org -> websocket pair

store: InterMeshStore | None = None
api_keys: ApiKeyStore | None = None
audit_log: ImmutableAuditLog | None = None
rate_limiter = RateLimiter(default_rate=20.0, default_burst=30.0)
asimov_engine = AsimovGuardrailEngine()
escrow_manager = EscrowManager()

HUB_SECRET: str = ""
HUB_ORG: str = "default"
SNAPSHOT_DIR: str | None = None   # None => ~/.intermesh/snapshots (ou $INTERMESH_HOME)


# ----------------------------------------------------------------------
# Jetons
# ----------------------------------------------------------------------

def generate_token(agent_name: str, agent_id: str, roles: list, org_id: str, auth_method: str) -> str:
    payload = {
        "agent_name": agent_name, "agent_id": agent_id, "roles": roles,
        "org_id": org_id, "auth_method": auth_method,
        "issued_at": time.time(), "expires_at": time.time() + TOKEN_EXPIRY_SECONDS,
        "issuer": "nexus-hub",
    }
    return jwt.encode(payload, HUB_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, HUB_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def verify_token(token: str, expected_agent: str) -> bool:
    payload = decode_token(token) if token else None
    if payload is None:
        return False
    return payload.get("agent_name") == expected_agent and payload.get("expires_at", 0) >= time.time()


# ----------------------------------------------------------------------
# Aides
# ----------------------------------------------------------------------

def _qualified_name(identity: AgentIdentity) -> str:
    # Convention partagée avec intermesh.store et intermesh.admin::_org_of :
    # un nom sans préfixe appartient à l'organisation "default". AgentIdentity
    # préfixe pourtant systématiquement ("default/x") ; on l'enlève ici.
    if identity.org_id == "default":
        return identity.name
    return identity.qualified_name


def _agent_org(qualified_name: str) -> str:
    ident = identity_registry.get(qualified_name)
    if ident is not None:
        return ident.org_id
    if qualified_name and "/" in qualified_name:
        return qualified_name.split("/")[0]
    return HUB_ORG


def remember_task(task: InterMeshTask) -> None:
    task_registry[task.task_id] = task
    if store is not None:
        store.save_task(task)


async def send_task_to_agent(task: InterMeshTask) -> bool:
    ws = agents.get(task.assignee)
    if ws is None:
        return False
    await ws.send(InterMeshMessage(
        type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, content=task.to_dict(),
    ).to_json())
    return True


def discover_agents(query: dict, caller_org: str) -> list[dict]:
    """Recherche d'agents, strictement cloisonnée à l'organisation de l'appelant."""
    limit = int(query.get("limit", 15))
    online_only = query.get("online_only", True)
    req_caps = set(query.get("capabilities") or [])
    req_roles = set(query.get("roles") or [])
    req_meta = query.get("metadata") or {}
    name_contains = query.get("name_contains")

    results = []
    for name, ident in identity_registry.items():
        if ident.org_id != caller_org:
            continue
        if online_only and name not in agents:
            continue
        if req_caps and not req_caps.issubset(set(ident.capabilities)):
            continue
        if req_roles and not req_roles.intersection(set(ident.roles)):
            continue
        if req_meta and not all(ident.metadata.get(k) == v for k, v in req_meta.items()):
            continue
        if name_contains and name_contains not in name:
            continue
        results.append({
            "name": name, "qualified_name": name, "agent_id": ident.agent_id,
            "capabilities": ident.capabilities, "roles": ident.roles,
            "permissions": ident.permissions, "public_key": ident.public_key, "schema": ident.schema,
            "online": name in agents,
        })
        if len(results) >= limit:
            break
    return results


# ----------------------------------------------------------------------
# Probes HTTP (/healthz, /readyz, /metrics) sur le même port que le WS
# ----------------------------------------------------------------------

_health_handler = HealthCheckHandler(
    readiness_evaluator=lambda: True,
    state_metrics_provider=lambda: {
        "intermesh_connected_agents": len(agents),
        "intermesh_registered_identities": len(identity_registry),
    },
)


async def process_request(connection, request=None):
    path = getattr(request, "path", None) if request is not None else None
    if path is None:
        path = getattr(connection, "path", None)
    if isinstance(connection, str):
        path = connection

    if not path:
        return None

    result = _health_handler.handle_request(path)
    if result is None:
        return None

    status, headers, body = result
    if hasattr(connection, "respond"):
        response = connection.respond(status, body.decode("utf-8"))
        for key, value in headers:
            response.headers[key] = value
        return response

    return (status, headers, body)


# ----------------------------------------------------------------------
# Console d'administration
# ----------------------------------------------------------------------

async def _handle_admin_request(websocket, msg: InterMeshMessage) -> None:
    content = msg.content if isinstance(msg.content, dict) else {}
    command = content.get("command")
    params = content.get("params") or {}

    try:
        payload = decode_token(msg.token) if msg.token else None
        if payload is None:
            raise AdminError("ADMIN_DENIED: token absent ou invalide.")
        authorize(payload)
        caller_org, scoped = caller_scope(payload)

        ctx = AdminContext(
            agents=agents, identity_registry=identity_registry, task_registry=task_registry,
            audit_log=audit_log, api_keys=api_keys, peered_hubs=peered_hubs, store=store,
            my_org=HUB_ORG, remember_task=remember_task, send_to_agent=send_task_to_agent,
            caller_org=caller_org, scoped=scoped, asimov_engine=asimov_engine, escrow_manager=escrow_manager,
            snapshot_dir=SNAPSHOT_DIR,
        )
        result = await admin_execute(command, params, ctx)

        if command in MUTATING:
            audit_log.log("ADMIN_ACTION", msg.sender, None, {"command": command})

        await websocket.send(InterMeshMessage(
            type=MessageType.ADMIN_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
            content=result, token=msg.token,
        ).to_json())

    except AdminError as exc:
        audit_log.log("ADMIN_DENIED", msg.sender, None, {"command": command, "reason": str(exc)})
        await websocket.send(InterMeshMessage(
            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
            content=str(exc), token=msg.token,
        ).to_json())


# ----------------------------------------------------------------------
# Boucle principale par connexion
# ----------------------------------------------------------------------

AUTHENTICATED_TYPES = (
    MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE,
    MessageType.TASK_SUBMIT, MessageType.TASK_UPDATE,
    MessageType.WHO_IS, MessageType.DISCOVER, MessageType.ADMIN_REQUEST,
)


async def handle_agent(websocket, my_org: str):
    agent_name = None
    try:
        async for raw_data in websocket:
            try:
                msg = InterMeshMessage.from_json(raw_data)
            except Exception as e:
                await websocket.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", content=str(e)).to_json())
                continue

            if msg.type == MessageType.REGISTER:
                d = msg.content or {}
                raw_name = msg.sender

                current_active = len(agents)
                if current_active >= MAX_FREE_AGENTS:
                    err_msg = f"AGENT_QUOTA_EXCEEDED: Free tier limit reached ({current_active}/{MAX_FREE_AGENTS} agents)."
                    await websocket.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content=err_msg).to_json())
                    continue

                api_key = d.get("api_key")
                if api_key:
                    info = api_keys.lookup(api_key)
                    if info is None:
                        await websocket.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=raw_name, content="API Key Entreprise invalide.").to_json())
                        continue
                    org_id = info["org_id"]
                    roles = info["roles"]
                    perms = info["permissions"]
                    auth_method = "api_key"
                else:
                    org_id = d.get("org_id", my_org)
                    roles = d.get("roles", ["standard"])
                    perms = d.get("permissions", [])
                    auth_method = "self_declared"

                identity = AgentIdentity.from_dict({
                    "name": raw_name, "org_id": org_id, "agent_id": d.get("agent_id"),
                    "capabilities": d.get("capabilities", []), "roles": roles,
                    "permissions": perms, "created_at": d.get("created_at"),
                    "metadata": d.get("metadata", {}), "public_key": d.get("public_key"),
                    "schema": d.get("schema"),
                })

                agent_name = _qualified_name(identity)

                if asimov_engine.circuit_breaker.is_tripped(agent_name):
                    await websocket.send(InterMeshMessage(
                        type=MessageType.ERROR, sender="hub", to=agent_name,
                        content="ASIMOV_GUARDRAIL: agent isolé par le disjoncteur de sécurité.",
                    ).to_json())
                    await websocket.close(1008, "Asimov Isolated")
                    agent_name = None
                    continue

                agents[agent_name] = websocket
                identity_registry[agent_name] = identity
                if store is not None:
                    store.save_identity(identity)
                token = generate_token(agent_name, identity.agent_id, identity.roles, identity.org_id, auth_method)

                audit_log.log("AGENT_REGISTERED", agent_name, "hub", {"roles": identity.roles, "org_id": identity.org_id})

                await websocket.send(InterMeshMessage(type=MessageType.REGISTERED, sender="hub", to=agent_name, content={
                    "status": "ready", "agent_id": identity.agent_id, "qualified_name": agent_name,
                    "roles": identity.roles, "permissions": identity.permissions, "org_id": identity.org_id,
                    "token": token, "online_agents": list(agents.keys()),
                }).to_json())

                # Reprise des tâches restées en attente pour cet exécutant.
                pending = [t for t in task_registry.values()
                           if t.assignee == agent_name and t.status == TaskStatus.PENDING]
                for task in pending:
                    await websocket.send(InterMeshMessage(
                        type=MessageType.TASK_ASSIGN, sender="hub", to=agent_name, content=task.to_dict(),
                    ).to_json())
                    audit_log.log("TASK_RESUMED", "hub", agent_name, {"task_id": task.task_id})

            elif msg.type in AUTHENTICATED_TYPES:
                if not msg.token or not verify_token(msg.token, msg.sender):
                    await websocket.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id, content="Token invalide.").to_json())
                    continue

                if msg.type == MessageType.WHO_IS:
                    target_name = msg.content
                    ident = identity_registry.get(target_name)
                    sender_org = _agent_org(msg.sender)
                    if ident is not None and ident.org_id == sender_org:
                        await websocket.send(InterMeshMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=ident.to_dict(), token=msg.token).to_json())

                elif msg.type == MessageType.DISCOVER:
                    query = msg.content or {}
                    caller_org = _agent_org(msg.sender)
                    matched = discover_agents(query, caller_org)
                    await websocket.send(InterMeshMessage(
                        type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
                        content={"query": query, "count": len(matched), "agents": matched}, token=msg.token,
                    ).to_json())

                elif msg.type == MessageType.TASK_SUBMIT:
                    raw_task = msg.content or {}
                    task_org = _agent_org(msg.sender)
                    try:
                        asimov_engine.validate_task_submission(
                            agent_name=msg.sender,
                            task_id=raw_task.get("task_id"),
                            parent_task_id=raw_task.get("parent_task_id"),
                            estimated_cost=float(raw_task.get("estimated_cost") or 0.0),
                            payload_text=str(raw_task.get("input_data", raw_task.get("title", ""))),
                            org_id=task_org,
                        )
                    except PolicyViolationError as pve:
                        audit_log.log("ASIMOV_GUARDRAIL_VIOLATION", msg.sender, raw_task.get("assignee"), {
                            "rule": pve.rule_name, "reason": str(pve), "task_id": raw_task.get("task_id"),
                        })
                        await websocket.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                            content=str(pve), token=msg.token,
                        ).to_json())
                        continue

                    escrow_req = raw_task.get("escrow")
                    if escrow_req:
                        payee_org = _agent_org(raw_task.get("assignee"))
                        try:
                            hold = escrow_manager.create_hold(
                                task_id=raw_task.get("task_id"), payer_org=task_org, payee_org=payee_org,
                                amount=float(escrow_req.get("amount", 0) or 0),
                                currency=escrow_req.get("currency", "USD"),
                                auto_release=bool(escrow_req.get("auto_release", True)),
                            )
                        except EscrowError as ee:
                            audit_log.log("ESCROW_REJECTED", msg.sender, raw_task.get("assignee"), {
                                "reason": str(ee), "task_id": raw_task.get("task_id"),
                            })
                            await websocket.send(InterMeshMessage(
                                type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                                content=str(ee), token=msg.token,
                            ).to_json())
                            continue
                        audit_log.log("ESCROW_HELD", msg.sender, raw_task.get("assignee"), {
                            "task_id": hold.task_id, "amount": hold.amount, "currency": hold.currency,
                        })

                    task = InterMeshTask.from_dict(msg.content)
                    remember_task(task)
                    audit_log.log("TASK_SUBMITTED", msg.sender, task.assignee, {"task_id": task.task_id, "title": task.title})
                    if task.assignee in agents:
                        await agents[task.assignee].send(InterMeshMessage(type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=msg.id, content=task.to_dict(), token=msg.token).to_json())

                elif msg.type == MessageType.TASK_UPDATE:
                    td = msg.content or {}
                    tid = td.get("task_id")
                    orch = td.get("orchestrator")
                    if tid in task_registry:
                        task = InterMeshTask.from_dict(td)
                        remember_task(task)
                        if task.status == TaskStatus.COMPLETED:
                            audit_log.log("TASK_COMPLETED", msg.sender, orch, {"task_id": tid})
                            hold = escrow_manager.get(tid)
                            if hold and hold.status.value == "held" and hold.auto_release:
                                escrow_manager.release(tid)
                                audit_log.log("ESCROW_RELEASED", "hub", hold.payee_org, {
                                    "task_id": tid, "amount": hold.amount, "currency": hold.currency,
                                })
                        elif task.status == TaskStatus.FAILED:
                            audit_log.log("TASK_FAILED", msg.sender, orch, {"task_id": tid, "error": task.error_message})
                            hold = escrow_manager.get(tid)
                            if hold and hold.status.value == "held":
                                escrow_manager.refund(tid)
                                audit_log.log("ESCROW_REFUNDED", "hub", hold.payer_org, {
                                    "task_id": tid, "amount": hold.amount, "currency": hold.currency,
                                })
                    if orch in agents:
                        await agents[orch].send(InterMeshMessage(type=MessageType.TASK_UPDATE, sender="hub", to=orch, content=td, token=msg.token).to_json())

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                    target = msg.to
                    sender_org = _agent_org(msg.sender)
                    target_org = _agent_org(target) if target else sender_org
                    if target and target_org != sender_org:
                        await websocket.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                            content=f"Isolement Multi-Tenant : '{target}' appartient à une autre organisation.",
                        ).to_json())
                        continue
                    if target in agents:
                        await agents[target].send(msg.to_json())

                elif msg.type == MessageType.ADMIN_REQUEST:
                    await _handle_admin_request(websocket, msg)

    except websockets.ConnectionClosed:
        pass
    finally:
        if agent_name and agent_name in agents:
            del agents[agent_name]


async def main():
    global store, api_keys, audit_log, HUB_SECRET, HUB_ORG, SNAPSHOT_DIR

    parser = argparse.ArgumentParser(description="InterMesh Hub")
    parser.add_argument("--port", type=int, default=8765, help="Port")
    parser.add_argument("--org", type=str, default="default", help="Org")
    parser.add_argument("--ephemeral-state", action="store_true", help="État en mémoire, rien sur disque")
    parser.add_argument("--state-file", type=str, default=None, help="Chemin de la base d'état")
    parser.add_argument("--ephemeral-secret", action="store_true", help="Clé JWT jetable")
    parser.add_argument("--secret-file", type=str, default=None, help="Chemin du fichier de clé JWT")
    parser.add_argument("--snapshot-dir", type=str, default=None, help="Dossier des instantanés d'état")
    parser.add_argument("--dev-api-keys", action="store_true", help="Active les clés de démonstration")
    parser.add_argument("--peer", action="append", default=[], help="Pair fédéré ORG=ws://host:port")

    # Tolérance : tout argument inconnu (utilisé par un autre point d'entrée) est ignoré.
    args, _ = parser.parse_known_args()

    HUB_ORG = args.org
    SNAPSHOT_DIR = args.snapshot_dir

    if args.ephemeral_state:
        store = InterMeshStore(ephemeral=True)
    elif args.state_file:
        store = InterMeshStore(path=args.state_file)
    else:
        store = InterMeshStore()

    identity_registry.update(store.load_identities())
    task_registry.update(store.load_tasks())

    secret, secret_desc = resolve_hub_secret(secret_file=args.secret_file, ephemeral=args.ephemeral_secret)
    HUB_SECRET = secret

    api_keys = ApiKeyStore.load(dev_keys=args.dev_api_keys)

    audit_log = ImmutableAuditLog(entries=store.load_audit(), on_append=store.append_audit)

    print(f"InterMesh Hub — org={HUB_ORG} port={args.port}")
    print(f"  secret : {secret_desc}")
    print(f"  état   : {store.description}")
    print(f"  clés   : {api_keys.source}")

    async with websockets.serve(
        lambda ws: handle_agent(ws, args.org),
        "0.0.0.0",
        args.port,
        process_request=process_request,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
