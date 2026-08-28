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

import dataclasses
import time
from typing import Any, Callable, Optional

from intermesh import snapshot as snapshot_store
from intermesh.escrow import EscrowError
from intermesh.guardrails import GuardrailPolicy
from intermesh.snapshot import SnapshotError
from intermesh.task import InterMeshTask, TaskStatus

# Commandes qui modifient l'état. Isolées pour être journalisées
# distinctement des simples lectures.
MUTATING = {
    "agent.disconnect",
    "task.cancel",
    "task.retry",
    "apikey.create",
    "apikey.revoke",
    "guardrails.set_policy",
    "escrow.grant",
    "escrow.release",
    "escrow.refund",
    "snapshot.create",
    "snapshot.restore",
    "snapshot.delete",
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
        asimov_engine: Any = None,
        escrow_manager: Any = None,
        snapshot_dir: Any = None,
    ):
        self.snapshot_dir = snapshot_dir
        self.agents = agents
        self.identity_registry = identity_registry
        self.task_registry = task_registry
        self.audit_log = audit_log
        self.api_keys = api_keys
        self.peered_hubs = peered_hubs
        self.store = store
        self.asimov_engine = asimov_engine
        self.escrow_manager = escrow_manager
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
    Organisation porteuse d'un nom qualifié InterMesh (`"acme/bot"` -> `"acme"`).

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


def _policy_to_dict(policy: GuardrailPolicy) -> dict:
    return dataclasses.asdict(policy)


def _resolve_target_org(ctx: AdminContext, params: dict) -> str:
    """
    Organisation ciblée par une commande de garde-fous.

    Un `org_admin` ne peut lire/modifier que sa propre organisation : un
    `org_id` différent dans les paramètres est refusé plutôt qu'ignoré, pour
    ne jamais laisser croire qu'une action a porté sur la bonne cible.
    """
    org_id = params.get("org_id")
    if ctx.scoped:
        if org_id and org_id != ctx.caller_org:
            raise AdminError("Un org_admin ne peut consulter/modifier que sa propre organisation.")
        return ctx.caller_org
    return org_id or ctx.my_org


def _guardrails_policy(ctx: AdminContext, params: dict) -> dict:
    if ctx.asimov_engine is None:
        raise AdminError("Moteur de garde-fous indisponible sur ce Hub.")
    org_id = _resolve_target_org(ctx, params)
    return {"org_id": org_id, "policy": _policy_to_dict(ctx.asimov_engine.get_policy(org_id))}


def _guardrails_set_policy(ctx: AdminContext, params: dict) -> dict:
    """
    Met à jour la policy d'une organisation en ne remplaçant que les champs
    fournis — les autres restent hérités de la policy actuelle de cette
    organisation (ou de la policy par défaut du Hub si elle n'en a pas encore).
    """
    if ctx.asimov_engine is None:
        raise AdminError("Moteur de garde-fous indisponible sur ce Hub.")
    org_id = _resolve_target_org(ctx, params)

    current = _policy_to_dict(ctx.asimov_engine.get_policy(org_id))
    editable = {f.name for f in dataclasses.fields(GuardrailPolicy)} - {"name"}
    for key, value in params.items():
        if key in editable:
            current[key] = value

    new_policy = GuardrailPolicy(**current)
    ctx.asimov_engine.set_org_policy(org_id, new_policy)
    return {"org_id": org_id, "policy": _policy_to_dict(new_policy)}


def _require_escrow(ctx: AdminContext):
    if ctx.escrow_manager is None:
        raise AdminError("Le module Escrow n'est pas actif sur ce Hub.")
    return ctx.escrow_manager


def _escrow_balance(ctx: AdminContext, params: dict) -> dict:
    manager = _require_escrow(ctx)
    org_id = _resolve_target_org(ctx, params)
    currency = params.get("currency", "USD")
    return {"org_id": org_id, "currency": currency, "balance": manager.ledger.balance(org_id, currency)}


def _escrow_grant(ctx: AdminContext, params: dict) -> dict:
    """
    Crédite un solde SIMULÉ pour une organisation — un robinet de démo/test,
    jamais un vrai mouvement d'argent (voir le docstring de `escrow.py`).
    """
    manager = _require_escrow(ctx)
    org_id = _resolve_target_org(ctx, params)
    amount = params.get("amount")
    if not amount:
        raise AdminError("amount requis.")
    currency = params.get("currency", "USD")
    try:
        new_balance = manager.ledger.grant(org_id, float(amount), currency)
    except EscrowError as exc:
        raise AdminError(str(exc)) from exc
    return {"org_id": org_id, "currency": currency, "balance": new_balance, "simulated": True}


def _escrow_list(ctx: AdminContext, params: dict) -> dict:
    manager = _require_escrow(ctx)
    org_id = ctx.caller_org if ctx.scoped else params.get("org_id")
    holds = manager.list_holds(org_id)
    return {"holds": [h.to_dict() for h in holds], "total": len(holds)}


def _check_hold_in_scope(ctx: AdminContext, hold) -> None:
    if ctx.scoped and ctx.caller_org not in (hold.payer_org, hold.payee_org):
        raise AdminError("Ce séquestre est hors de votre organisation.")


def _escrow_release(ctx: AdminContext, params: dict) -> dict:
    manager = _require_escrow(ctx)
    task_id = params.get("task_id")
    hold = manager.get(task_id) if task_id else None
    if hold is None:
        raise AdminError("Aucun séquestre pour cette tâche.")
    _check_hold_in_scope(ctx, hold)
    try:
        released = manager.release(task_id)
    except EscrowError as exc:
        raise AdminError(str(exc)) from exc
    return released.to_dict()


def _escrow_refund(ctx: AdminContext, params: dict) -> dict:
    manager = _require_escrow(ctx)
    task_id = params.get("task_id")
    hold = manager.get(task_id) if task_id else None
    if hold is None:
        raise AdminError("Aucun séquestre pour cette tâche.")
    _check_hold_in_scope(ctx, hold)
    try:
        refunded = manager.refund(task_id)
    except EscrowError as exc:
        raise AdminError(str(exc)) from exc
    return refunded.to_dict()


# ----------------------------------------------------------------------
# Instantanés
# ----------------------------------------------------------------------

def _require_hub_admin(ctx: AdminContext, action: str) -> None:
    """
    Un instantané est hub-wide par nature : il contient le registre, les
    clés et les séquestres de TOUTES les organisations. Un `org_admin` qui
    pourrait le créer lirait ses voisins ; s'il pouvait le restaurer, il
    écraserait leur état. Ces commandes sont donc réservées à `admin`.
    """
    if ctx.scoped:
        raise AdminError(
            f"'{action}' porte sur l'ensemble du Hub, toutes organisations "
            f"confondues : le rôle 'admin' est requis, 'org_admin' ne suffit pas."
        )


def _audit_head(ctx: AdminContext) -> dict:
    chain = getattr(ctx.audit_log, "chain", None)
    if not chain:
        return {}
    return {"index": chain[-1].index, "hash": chain[-1].hash}


def _capture(ctx: AdminContext) -> dict:
    return snapshot_store.capture_state(
        identity_registry=ctx.identity_registry,
        task_registry=ctx.task_registry,
        api_keys=ctx.api_keys,
        asimov_engine=ctx.asimov_engine,
        escrow_manager=ctx.escrow_manager,
    )


def _snapshot_create(ctx: AdminContext, params: dict) -> dict:
    _require_hub_admin(ctx, "snapshot.create")
    name = params.get("name")
    if not name:
        raise AdminError("name requis.")
    try:
        manifest = snapshot_store.save(
            name,
            _capture(ctx),
            hub_org=ctx.my_org,
            audit_head=_audit_head(ctx),
            directory=ctx.snapshot_dir,
            passphrase=params.get("passphrase"),
            overwrite=bool(params.get("overwrite", True)),
        )
    except SnapshotError as exc:
        raise AdminError(str(exc)) from exc

    if not manifest["encrypted"]:
        manifest["warning"] = (
            "Instantané non chiffré. Le fichier est en 0600 mais contient les "
            "empreintes de clés d'API et l'inventaire de toutes les organisations : "
            "fournissez `passphrase` avant de le sortir de cette machine."
        )
    return manifest


def _snapshot_list(ctx: AdminContext, params: dict) -> dict:
    _require_hub_admin(ctx, "snapshot.list")
    snapshots = snapshot_store.list_snapshots(ctx.snapshot_dir)
    return {"snapshots": snapshots, "total": len(snapshots)}


def _snapshot_delete(ctx: AdminContext, params: dict) -> dict:
    _require_hub_admin(ctx, "snapshot.delete")
    name = params.get("name")
    if not name:
        raise AdminError("name requis.")
    try:
        deleted = snapshot_store.delete(name, ctx.snapshot_dir)
    except SnapshotError as exc:
        raise AdminError(str(exc)) from exc
    if not deleted:
        raise AdminError(f"Instantané inconnu : '{name}'.")
    return {"deleted": name}


def _snapshot_restore(ctx: AdminContext, params: dict) -> dict:
    """
    Réinstalle un instantané, après en avoir pris un de sécurité.

    Le filet de sécurité est pris AVANT toute écriture, avec la même
    passphrase que celle fournie pour la lecture : une restauration ratée
    reste elle-même réversible. `safety_snapshot=False` le désactive.
    """
    _require_hub_admin(ctx, "snapshot.restore")
    name = params.get("name")
    if not name:
        raise AdminError("name requis.")
    passphrase = params.get("passphrase")

    try:
        manifest, state = snapshot_store.load(
            name, directory=ctx.snapshot_dir, passphrase=passphrase,
        )
    except SnapshotError as exc:
        raise AdminError(str(exc)) from exc

    safety_name = None
    if params.get("safety_snapshot", True):
        safety_name = f"pre-restore-{int(time.time())}"
        try:
            snapshot_store.save(
                safety_name, _capture(ctx), hub_org=ctx.my_org,
                audit_head=_audit_head(ctx), directory=ctx.snapshot_dir,
                passphrase=passphrase,
            )
        except SnapshotError as exc:
            raise AdminError(
                f"Filet de sécurité impossible à écrire ({exc}) : restauration "
                f"abandonnée. Passez `safety_snapshot: false` pour forcer."
            ) from exc

    report = snapshot_store.apply_state(
        state,
        identity_registry=ctx.identity_registry,
        task_registry=ctx.task_registry,
        connected_agents=ctx.agents,
        store=ctx.store,
        api_keys=ctx.api_keys,
        asimov_engine=ctx.asimov_engine,
        escrow_manager=ctx.escrow_manager,
    )

    # La chaîne d'audit vivante n'est jamais remplacée : elle est
    # prolongée. Un instantané ne peut donc pas effacer la trace de sa
    # propre restauration.
    if ctx.audit_log is not None:
        ctx.audit_log.log("SNAPSHOT_RESTORED", "hub", None, {
            "snapshot": name,
            "snapshot_created_at": manifest.get("created_at"),
            "safety_snapshot": safety_name,
            "restored": report.get("restored"),
            "skipped": [s["what"] for s in report.get("skipped", [])],
        })

    return {
        "restored_from": name,
        "manifest": manifest,
        "safety_snapshot": safety_name,
        "audit_preserved": True,
        **report,
    }


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
    "guardrails.policy": _guardrails_policy,
    "guardrails.set_policy": _guardrails_set_policy,
    "escrow.balance": _escrow_balance,
    "escrow.grant": _escrow_grant,
    "escrow.list": _escrow_list,
    "escrow.release": _escrow_release,
    "escrow.refund": _escrow_refund,
    "snapshot.create": _snapshot_create,
    "snapshot.list": _snapshot_list,
    "snapshot.restore": _snapshot_restore,
    "snapshot.delete": _snapshot_delete,
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
