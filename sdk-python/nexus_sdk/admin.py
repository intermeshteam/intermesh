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
  2. le rôle `admin` ou `org_admin`.

Les deux conditions sont vérifiées ici, à un seul endroit.

CLOISONNEMENT PAR ORGANISATION
-------------------------------
`admin` voit et administre tout le Hub, organisations confondues : c'est
le rôle de l'opérateur du Hub lui-même, inchangé depuis la première
version de cette console.

`org_admin` est plus étroit : il ne voit et n'agit que sur l'organisation
de sa propre clé d'API (`org_id`, porté par le JWT, donc lui aussi
infalsifiable). C'est le rôle à distribuer à chaque entreprise qui
partage un Hub avec d'autres — indispensable dès qu'un portail web laisse
plusieurs organisations générer leurs propres clés sur la même instance :
sans ce cloisonnement, la clé admin d'une entreprise verrait les agents,
tâches et journaux d'audit de toutes les autres.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

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
        caller_org: str = "default",
        scoped: bool = False,
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
        # Organisation du porteur du token, et `True` si son rôle est
        # `org_admin` — auquel cas chaque commande doit filtrer sa vue et
        # ses actions à cette seule organisation. `admin` laisse `scoped`
        # à `False` : comportement hub-wide inchangé.
        self.caller_org = caller_org
        self.scoped = scoped


def authorize(token_payload: dict) -> None:
    """
    Vérifie qu'un porteur de token a le droit d'administrer.

    Raises:
        AdminError: si l'identité n'est pas issue d'une clé d'API, ou si
                    ni le rôle `admin` ni `org_admin` ne sont présents.
    """
    if token_payload.get("auth_method") != "api_key":
        raise AdminError(
            "ADMIN_DENIED: l'administration exige une identité authentifiée "
            "par clé d'API. Les rôles déclarés à l'enregistrement ne suffisent pas."
        )
    roles = token_payload.get("roles", [])
    if "admin" not in roles and "org_admin" not in roles:
        raise AdminError("ADMIN_DENIED: rôle 'admin' ou 'org_admin' requis.")


def caller_scope(token_payload: dict) -> tuple[str, bool]:
    """
    (organisation du porteur du token, `True` s'il doit être cloisonné).

    `admin` l'emporte sur `org_admin` si un token portait les deux : un
    opérateur de Hub qui s'octroie aussi `org_admin` reste hub-wide.
    """
    roles = token_payload.get("roles", [])
    scoped = "admin" not in roles and "org_admin" in roles
    return token_payload.get("org_id", "default"), scoped


def _org_of(qualified_name: Optional[str]) -> str:
    """
    Organisation porteuse d'un nom qualifié Nexus (`"acme/bot"` -> `"acme"`).

    Un nom sans préfixe appartient à l'organisation par défaut du Hub —
    la même convention que `AgentIdentity.qualified_name`.
    """
    if not qualified_name:
        return "default"
    return qualified_name.split("/")[0] if "/" in qualified_name else "default"


# Évènements qui décrivent le Hub lui-même ou sa fédération, pas une
# organisation en particulier : un `org_admin` ne doit jamais les voir,
# même quand leur `sender`/`target` ressemble par accident à son org_id.
_HUB_LEVEL_EVENTS = {"GENESIS", "PEERING_ESTABLISHED", "PEERING_ACCEPTED"}


# ----------------------------------------------------------------------
# Commandes
# ----------------------------------------------------------------------

def _hub_info(ctx: AdminContext, params: dict) -> dict:
    if ctx.scoped:
        identities = [i for i in ctx.identity_registry.values() if i.org_id == ctx.caller_org]
        tasks = [t for t in ctx.task_registry.values()
                 if ctx.caller_org in (_org_of(t.orchestrator), _org_of(t.assignee))]
        audit_entries = sum(
            1 for e in ctx.audit_log.chain
            if e.event_type not in _HUB_LEVEL_EVENTS
            and ctx.caller_org in (_org_of(e.sender), _org_of(e.target))
        )
        api_keys_count = sum(1 for k in ctx.api_keys.describe() if k["org_id"] == ctx.caller_org)
        federation_peers: list[str] = []  # information hub-wide, réservée à `admin`
    else:
        identities = list(ctx.identity_registry.values())
        tasks = list(ctx.task_registry.values())
        audit_entries = len(ctx.audit_log.chain)
        api_keys_count = len(ctx.api_keys)
        federation_peers = sorted(ctx.peered_hubs.keys())

    by_status: dict[str, int] = {}
    for task in tasks:
        by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
    agents_online = sum(1 for i in identities if i.qualified_name in ctx.agents)

    return {
        "org": ctx.caller_org if ctx.scoped else ctx.my_org,
        "version": ctx.hub_version,
        "agents_online": agents_online,
        "agents_known": len(identities),
        "tasks_total": len(tasks),
        "tasks_by_status": by_status,
        "audit_entries": audit_entries,
        "audit_intact": ctx.audit_log.verify_integrity(),
        "federation_peers": federation_peers,
        "state_backend": getattr(ctx.store, "description", "inconnu"),
        "state_ephemeral": getattr(ctx.store, "ephemeral", True),
        "api_keys": api_keys_count,
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
        if ctx.scoped and identity.org_id != ctx.caller_org:
            continue
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
    online = sum(1 for a in out if a["online"])
    return {"agents": out, "online": online, "known": len(out)}


async def _agent_disconnect(ctx: AdminContext, params: dict) -> dict:
    name = params.get("name")
    if ctx.scoped:
        identity = ctx.identity_registry.get(name)
        if identity is None or identity.org_id != ctx.caller_org:
            raise AdminError(f"'{name}' est hors de votre organisation.")
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
    if ctx.scoped:
        tasks = [t for t in tasks
                 if ctx.caller_org in (_org_of(t.orchestrator), _org_of(t.assignee))]
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


def _check_task_in_scope(ctx: AdminContext, task) -> None:
    if ctx.scoped and ctx.caller_org not in (_org_of(task.orchestrator), _org_of(task.assignee)):
        raise AdminError("Cette tâche est hors de votre organisation.")


def _task_cancel(ctx: AdminContext, params: dict) -> dict:
    task = ctx.task_registry.get(params.get("task_id"))
    if task is None:
        raise AdminError("Tâche inconnue.")
    _check_task_in_scope(ctx, task)
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        raise AdminError(f"Tâche déjà terminée ({task.status.value}).")

    task.update_status(TaskStatus.FAILED, error_message="Annulée par un administrateur.")
    ctx.remember_task(task)
    return {"task_id": task.task_id, "status": task.status.value}


async def _task_retry(ctx: AdminContext, params: dict) -> dict:
    task = ctx.task_registry.get(params.get("task_id"))
    if task is None:
        raise AdminError("Tâche inconnue.")
    _check_task_in_scope(ctx, task)

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
    if ctx.scoped:
        entries = [
            e for e in entries
            if e["event_type"] not in _HUB_LEVEL_EVENTS
            and ctx.caller_org in (_org_of(e["sender"]), _org_of(e.get("target")))
        ]
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
    keys = ctx.api_keys.describe()
    if ctx.scoped:
        keys = [k for k in keys if k["org_id"] == ctx.caller_org]
    return {
        "keys": keys,
        "source": ctx.api_keys.source,
        "mutable": ctx.api_keys.mutable,
    }


def _apikey_create(ctx: AdminContext, params: dict) -> dict:
    org_id = params.get("org_id")
    if ctx.scoped:
        # Un `org_admin` ne crée que pour sa propre organisation : accepter
        # un `org_id` différent laisserait une entreprise émettre des clés
        # au nom d'une autre.
        if org_id and org_id != ctx.caller_org:
            raise AdminError("Un org_admin ne peut créer de clé que pour sa propre organisation.")
        org_id = ctx.caller_org
    elif not org_id:
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
    if ctx.scoped:
        matches = [k for k in ctx.api_keys.describe() if k["fingerprint"].startswith(fingerprint)]
        if len(matches) != 1 or matches[0]["org_id"] != ctx.caller_org:
            raise AdminError("Empreinte inconnue ou hors de votre organisation.")
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
