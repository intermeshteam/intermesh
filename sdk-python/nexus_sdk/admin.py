"""
Moteur de commandes de la console d'administration.

Séparé du Hub pour rester testable sans serveur en marche, et pour que
la surface d'administration soit lisible d'un seul tenant — c'est elle
qui concentre le risque.

MODÈLE D'AUTORISATION
---------------------
À l'enregistrement, un agent sans clé d'API choisit lui-même ses rôles :

    roles = d.get("roles", ["standard"])

C'est acceptable pour un maillage où les agents s'échangent des messages,
et inacceptable pour une console capable de révoquer des clés ou de
déconnecter des agents. Toute commande d'administration exige donc :

  1. une identité authentifiée par CLÉ D'API — jamais des rôles déclarés
     par le client. La preuve est portée par le JWT signé par le Hub,
     donc infalsifiable ;
  2. le rôle `admin`.

Les deux conditions sont vérifiées ici, à un seul endroit.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from nexus_sdk.task import NexusTask, TaskStatus

# Commandes qui modifient l'état. Isolées pour être journalisées
# distinctement des simples lectures.
MUTATING = {
    "agent.disconnect",
    "task.cancel",
    "task.retry",
    "apikey.create",
    "apikey.revoke",
}


class AdminError(Exception):
    """Commande refusée ou impossible à exécuter."""


class AdminContext:
    """Vue sur l'état du Hub fournie au moteur de commandes."""

    def __init__(
        self,
        *,
        agents: dict,
        identity_registry: dict,
        task_registry: dict,
        audit_log,
        api_keys,
        peered_hubs: dict,
        store,
        my_org: str,
        remember_task: Callable,
        send_to_agent: Callable,
        hub_version: str = "1.5",
    ):
        self.agents = agents
        self.identity_registry = identity_registry
        self.task_registry = task_registry
        self.audit_log = audit_log
        self.api_keys = api_keys
        self.peered_hubs = peered_hubs
        self.store = store
        self.my_org = my_org
        self.remember_task = remember_task
        self.send_to_agent = send_to_agent
        self.hub_version = hub_version


def authorize(token_payload: dict) -> None:
    """
    Vérifie qu'un porteur de token a le droit d'administrer.

    Raises:
        AdminError: si l'identité n'est pas issue d'une clé d'API, ou si
                    le rôle admin manque.
    """
    if token_payload.get("auth_method") != "api_key":
        raise AdminError(
            "ADMIN_DENIED: l'administration exige une identité authentifiée "
            "par clé d'API. Les rôles déclarés à l'enregistrement ne suffisent pas."
        )
    if "admin" not in token_payload.get("roles", []):
        raise AdminError("ADMIN_DENIED: rôle 'admin' requis.")


# ----------------------------------------------------------------------
# Commandes
# ----------------------------------------------------------------------

def _hub_info(ctx: AdminContext, params: dict) -> dict:
    by_status: dict[str, int] = {}
    for task in ctx.task_registry.values():
        by_status[task.status.value] = by_status.get(task.status.value, 0) + 1

    return {
        "org": ctx.my_org,
        "version": ctx.hub_version,
        "agents_online": len(ctx.agents),
        "agents_known": len(ctx.identity_registry),
        "tasks_total": len(ctx.task_registry),
        "tasks_by_status": by_status,
        "audit_entries": len(ctx.audit_log.chain),
        "audit_intact": ctx.audit_log.verify_integrity(),
        "federation_peers": sorted(ctx.peered_hubs.keys()),
        "state_backend": getattr(ctx.store, "description", "inconnu"),
        "state_ephemeral": getattr(ctx.store, "ephemeral", True),
        "api_keys": len(ctx.api_keys),
        "api_keys_source": ctx.api_keys.source,
        "api_keys_mutable": ctx.api_keys.mutable,
        "server_time": time.time(),
    }


def _agents_list(ctx: AdminContext, params: dict) -> dict:
    """
    Inventaire complet : les agents connectés, mais aussi ceux connus et
    actuellement hors ligne — invisibles jusqu'ici faute de persistance.
    """
    out = []
    for name, identity in sorted(ctx.identity_registry.items()):
        pending = sum(
            1 for t in ctx.task_registry.values()
            if t.assignee == name and t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        )
        out.append({
            "name": name,
            "agent_id": identity.agent_id,
            "org_id": identity.org_id,
            "capabilities": identity.capabilities,
            "roles": identity.roles,
            "permissions": identity.permissions,
            "metadata": identity.metadata,
            "fingerprint": identity.fingerprint,
            "encrypted": bool(identity.public_key),
            "online": name in ctx.agents,
            "pending_tasks": pending,
        })
    return {"agents": out, "online": len(ctx.agents), "known": len(out)}


async def _agent_disconnect(ctx: AdminContext, params: dict) -> dict:
    name = params.get("name")
    ws = ctx.agents.get(name)
    if ws is None:
        raise AdminError(f"'{name}' n'est pas connecté.")
    await ws.close()
    return {"disconnected": name}


def _tasks_list(ctx: AdminContext, params: dict) -> dict:
    status = params.get("status")
    assignee = params.get("assignee")
    limit = min(int(params.get("limit", 100)), 500)

    tasks = list(ctx.task_registry.values())
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    if assignee:
        tasks = [t for t in tasks if t.assignee == assignee]
    tasks.sort(key=lambda t: t.updated_at, reverse=True)

    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "orchestrator": t.orchestrator,
                "assignee": t.assignee,
                "status": t.status.value,
                "error_message": t.error_message,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                # input_data et output_data sont chiffrés de bout en bout :
                # le Hub ne peut pas les lire, la console non plus.
                "encrypted_payload": isinstance(t.input_data, str),
            }
            for t in tasks[:limit]
        ],
        "total": len(tasks),
    }


def _task_cancel(ctx: AdminContext, params: dict) -> dict:
    task = ctx.task_registry.get(params.get("task_id"))
    if task is None:
        raise AdminError("Tâche inconnue.")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        raise AdminError(f"Tâche déjà terminée ({task.status.value}).")

    task.update_status(TaskStatus.FAILED, error_message="Annulée par un administrateur.")
    ctx.remember_task(task)
    return {"task_id": task.task_id, "status": task.status.value}


async def _task_retry(ctx: AdminContext, params: dict) -> dict:
    task = ctx.task_registry.get(params.get("task_id"))
    if task is None:
        raise AdminError("Tâche inconnue.")

    task.update_status(TaskStatus.PENDING)
    ctx.remember_task(task)

    delivered = await ctx.send_to_agent(task)
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        # Si l'exécutant est absent, la tâche reste en attente : elle lui
        # sera repoussée à sa reconnexion par le mécanisme de reprise.
        "delivered": delivered,
    }


def _audit_list(ctx: AdminContext, params: dict) -> dict:
    limit = min(int(params.get("limit", 100)), 1000)
    offset = int(params.get("offset", 0))
    event_type = params.get("event_type")

    chain = ctx.audit_log.chain
    entries = [e.to_dict() for e in chain]
    if event_type:
        entries = [e for e in entries if e["event_type"] == event_type]
    entries.reverse()

    return {
        "entries": entries[offset:offset + limit],
        "total": len(entries),
        "chain_length": len(chain),
        "intact": ctx.audit_log.verify_integrity(),
    }


def _audit_verify(ctx: AdminContext, params: dict) -> dict:
    """
    Revérifie la chaîne et localise la première rupture s'il y en a une.
    """
    chain = ctx.audit_log.chain
    broken_at = None
    for i in range(1, len(chain)):
        if chain[i].prev_hash != chain[i - 1].hash or chain[i].hash != chain[i].compute_hash():
            broken_at = i
            break

    return {
        "intact": broken_at is None,
        "chain_length": len(chain),
        "broken_at_index": broken_at,
        "verified_at": time.time(),
    }


def _apikeys_list(ctx: AdminContext, params: dict) -> dict:
    return {
        "keys": ctx.api_keys.describe(),
        "source": ctx.api_keys.source,
        "mutable": ctx.api_keys.mutable,
    }


def _apikey_create(ctx: AdminContext, params: dict) -> dict:
    org_id = params.get("org_id")
    if not org_id:
        raise AdminError("org_id requis.")
    try:
        raw = ctx.api_keys.create(
            org_id=org_id,
            roles=params.get("roles") or ["service_account"],
            permissions=params.get("permissions") or [],
            label=params.get("label", ""),
        )
    except PermissionError as exc:
        raise AdminError(str(exc)) from exc

    # Unique occasion où la valeur en clair transite. Elle n'est pas
    # journalisée et le Hub ne peut plus la retrouver ensuite.
    return {"key": raw, "warning": "Cette clé ne sera plus jamais affichée."}


def _apikey_revoke(ctx: AdminContext, params: dict) -> dict:
    fingerprint = params.get("fingerprint")
    if not fingerprint:
        raise AdminError("fingerprint requis.")
    try:
        ok = ctx.api_keys.revoke(fingerprint)
    except PermissionError as exc:
        raise AdminError(str(exc)) from exc
    if not ok:
        raise AdminError("Empreinte inconnue ou ambiguë.")
    return {"revoked": fingerprint}


HANDLERS: dict[str, Callable[..., Any]] = {
    "hub.info": _hub_info,
    "agents.list": _agents_list,
    "agent.disconnect": _agent_disconnect,
    "tasks.list": _tasks_list,
    "task.cancel": _task_cancel,
    "task.retry": _task_retry,
    "audit.list": _audit_list,
    "audit.verify": _audit_verify,
    "apikeys.list": _apikeys_list,
    "apikey.create": _apikey_create,
    "apikey.revoke": _apikey_revoke,
}


async def execute(command: str, params: dict, ctx: AdminContext) -> dict:
    """Exécute une commande d'administration déjà autorisée."""
    handler = HANDLERS.get(command)
    if handler is None:
        raise AdminError(f"Commande inconnue : '{command}'. "
                         f"Disponibles : {', '.join(sorted(HANDLERS))}")

    result = handler(ctx, params or {})
    if hasattr(result, "__await__"):
        result = await result
    return result
