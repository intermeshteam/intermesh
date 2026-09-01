"""
InterMesh Hub — routage central, fédération inter-organisations, télémétrie,
console d'administration, persistance.

Point d'entrée unique : ce module remplace l'ancien couple
`hub.py` / `hub_telemetry.py`, qui avait divergé (la fédération n'était
implémentée que dans le second, que personne ne démarrait).
"""
import argparse
import asyncio
import json
import os
import time
import uuid

import jwt
import websockets

from intermesh.admin import MUTATING, AdminContext, AdminError, authorize, caller_scope
from intermesh.admin import execute as admin_execute
from intermesh.apikeys import ApiKeyStore
from intermesh.approval import ApprovalPolicy, requires_approval
from intermesh.audit import ImmutableAuditLog
from intermesh.egress import EgressBlocked, EgressPolicy, apply_egress
from intermesh.escrow import EscrowError, EscrowManager
from intermesh.guardrails import AsimovGuardrailEngine, PolicyViolationError
from intermesh.health import HealthCheckHandler
from intermesh.identity import AgentIdentity
from intermesh.message import MessageType, InterMeshMessage
from intermesh.peering import (
    assert_peer_link_is_secure, build_peer_ssl_context, build_server_ssl_context,
    parse_peer_spec,
)
from intermesh.ratelimit import RateLimiter
from intermesh.secret import resolve_hub_secret
from intermesh.signing import (
    ALGORITHM, derive_signing_key, key_fingerprint, load_public_pem, public_pem,
)
from intermesh.store import InterMeshStore
from intermesh.task import InterMeshTask, TaskStatus

TOKEN_EXPIRY_SECONDS = 3600

# Plafond d'agents connectés simultanément. 0 = illimité, et c'est le
# défaut : InterMesh est auto-hébergé, la seule limite qui a du sens est la
# machine de celui qui l'exécute.
#
# Une valeur codée en dur ici était pire qu'inutile. Elle refusait le 16e
# agent avant même de regarder la clé d'API — donc une clé entreprise n'y
# changeait rien — et n'importe qui pouvait de toute façon éditer la
# constante, puisque le dépôt est public. Elle ne protégeait aucun modèle
# économique, elle empêchait seulement de s'en servir.
MAX_AGENTS = 0

# Auto-déclaration : à l'enregistrement, un agent sans clé d'API choisit
# lui-même son organisation, ses rôles et ses permissions. Le Hub les
# acceptait tels quels, quelle que soit la provenance de la connexion.
#
# Sur localhost c'est un confort de développement. Depuis une adresse
# distante, cela signifie que quiconque connaît l'adresse se déclare admin
# de n'importe quelle organisation. Le Hub écoutant toujours sur 0.0.0.0,
# « exposé » ne se déduit pas d'un réglage : la décision se prend par
# connexion, selon son origine.
#
#   ALLOW_SELF_DECLARED : autorise l'auto-déclaration même à distance.
#   REQUIRE_API_KEY     : l'exige partout, y compris depuis localhost.
ALLOW_SELF_DECLARED = False
REQUIRE_API_KEY = False

# État partagé du Hub, peuplé par main() au démarrage.
agents: dict[str, "websockets.ServerConnection"] = {}       # qualified_name -> websocket
identity_registry: dict[str, AgentIdentity] = {}             # qualified_name -> AgentIdentity
task_registry: dict[str, InterMeshTask] = {}                     # task_id -> InterMeshTask
peered_hubs: dict[str, object] = {}                           # org distante -> websocket du Hub pair

# Grappe : plusieurs Hubs d'une *même* organisation, partageant la base
# d'état et la clé de signature. Distinct du pairage inter-organisations,
# qui franchit une frontière et filtre ce qui sort ; ici rien ne sort.
#
# Chaque Hub a une identité propre et une adresse à laquelle ses frères le
# joignent. La table `presence` du store dit qui détient quel agent ; ce
# dictionnaire garde les liens ouverts vers les frères déjà contactés.
HUB_ID: str = ""
CLUSTER_URL: str = ""            # adresse annoncée aux frères, vide = hors grappe
CLUSTER_LINKS: dict[str, object] = {}   # hub_id frère -> websocket
PRESENCE_TTL = 45.0              # au-delà, une présence n'est plus crue
PRESENCE_HEARTBEAT = 15.0        # période de rafraîchissement
observers: set = set()                                        # websockets dashboard / topologie / sécurité
agent_meta: dict[str, dict] = {}                              # qualified_name -> métriques de connexion

# Un agent est traité comme observateur (télémétrie seule, hors quota) s'il
# déclare le rôle "observer" ou si son nom porte un de ces préfixes.
OBSERVER_PREFIXES = ("topology_", "nexus_dashboard", "dashboard_", "agents_dir", "security_")

store: InterMeshStore | None = None
api_keys: ApiKeyStore | None = None
audit_log: ImmutableAuditLog | None = None
rate_limiter = RateLimiter(default_rate=20.0, default_burst=30.0)
asimov_engine = AsimovGuardrailEngine()
escrow_manager = EscrowManager()

HUB_SECRET: str = ""
HUB_ORG: str = "default"

# Signature asymétrique : la privée ne sort jamais d'ici, la publique est
# transmise aux pairs au moment du pairage.
HUB_PRIVATE_KEY = None          # Ed25519PrivateKey
HUB_PUBLIC_PEM: str = ""
HUB_KEY_ID: str = ""
peer_public_keys: dict[str, str] = {}      # org distante -> clé publique PEM

# Politique de sortie de cette organisation. Vide par défaut : rien n'est
# filtré tant que rien n'est déclaré.
egress_policy: EgressPolicy = EgressPolicy()

# Validation humaine. Vide par défaut : aucune tâche n'est suspendue tant
# qu'aucune règle n'est déclarée.
approval_policy: ApprovalPolicy = ApprovalPolicy()

# Tâches retenues en attente d'un arbitrage humain, par task_id.
#
# Le séquestre n'est volontairement pas encore constitué à ce stade : rien
# ne doit être immobilisé tant qu'une personne n'a pas dit oui, et une
# tâche refusée n'a donc aucun blocage à défaire. Le revers assumé est
# qu'une approbation peut être suivie d'un échec de séquestre faute de
# fonds — un échec visible, préférable à des fonds gelés en silence sur une
# tâche que personne ne validera.
pending_approvals: dict[str, dict] = {}

SNAPSHOT_DIR: str | None = None   # None => ~/.intermesh/snapshots (ou $INTERMESH_HOME)


# ----------------------------------------------------------------------
# Jetons
# ----------------------------------------------------------------------

def generate_token(agent_name: str, agent_id: str, roles: list, org_id: str, auth_method: str) -> str:
    payload = {
        "agent_name": agent_name, "agent_id": agent_id, "roles": roles,
        "org_id": org_id, "auth_method": auth_method,
        "issued_at": time.time(), "expires_at": time.time() + TOKEN_EXPIRY_SECONDS,
        "issuer": "intermesh-hub", "iss_org": HUB_ORG,
    }
    return jwt.encode(payload, HUB_PRIVATE_KEY, algorithm=ALGORITHM,
                      headers={"kid": HUB_KEY_ID})


def decode_token(token: str, issuing_org: str | None = None) -> dict | None:
    """Décode un jeton en vérifiant sa signature.

    `issuing_org` désigne l'organisation censée l'avoir émis : par défaut
    ce Hub. Pour un jeton reçu d'un pair, la vérification se fait contre la
    clé publique que ce pair a publiée lors du pairage — un Hub ne peut donc
    pas signer au nom d'un autre.
    """
    if not token:
        return None

    if issuing_org is None or issuing_org == HUB_ORG:
        key = HUB_PUBLIC_PEM
    else:
        key = peer_public_keys.get(issuing_org)
        if key is None:
            return None

    try:
        return jwt.decode(token, key, algorithms=[ALGORITHM])
    except Exception:
        return None


def verify_token(token: str, expected_agent: str, issuing_org: str | None = None) -> bool:
    payload = decode_token(token, issuing_org) if token else None
    if payload is None:
        return False
    if payload.get("agent_name") != expected_agent:
        return False
    if payload.get("expires_at", 0) < time.time():
        return False
    # Un jeton émis par une organisation ne vaut que pour elle : sans ce
    # contrôle, un pair pairé pourrait rejouer un jeton en se réclamant
    # d'une organisation tierce.
    expected_issuer = HUB_ORG if issuing_org is None else issuing_org
    return payload.get("iss_org", expected_issuer) == expected_issuer


def verify_federated_token(token: str, origin_org: str, claimed_sender: str | None) -> bool:
    """Vérifie un jeton porté par un message relayé depuis le Hub `origin_org`.

    Un message relayé peut être émis par le Hub lui-même (TASK_ASSIGN, par
    exemple) tout en transportant le jeton de l'agent commanditaire : la
    liaison nom↔jeton ne s'applique donc qu'aux messages émis par un agent.
    Ce qui est vérifié dans tous les cas — et qui est le fond du sujet — est
    que le jeton porte bien la signature de l'organisation d'origine.
    """
    payload = decode_token(token, origin_org) if token else None
    if payload is None:
        return False
    if payload.get("expires_at", 0) < time.time():
        return False
    if payload.get("iss_org") != origin_org:
        return False
    if claimed_sender and claimed_sender != "hub":
        return payload.get("agent_name") == claimed_sender
    return True


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


def _local_name(name: str | None) -> str | None:
    """Nom sous lequel un agent est réellement enregistré localement, ou None.

    Le SDK peut adresser un agent de l'organisation "default" aussi bien par
    `x` que par `default/x` ; `_qualified_name` ne retient que la forme courte.
    On accepte donc les deux à la lecture.
    """
    if not name:
        return None
    if name in agents:
        return name
    if name.startswith("default/"):
        short = name[len("default/"):]
        if short in agents:
            return short
    return None


def _agent_org(qualified_name: str) -> str:
    ident = identity_registry.get(qualified_name)
    if ident is None and qualified_name and qualified_name.startswith("default/"):
        ident = identity_registry.get(qualified_name[len("default/"):])
    if ident is not None:
        return ident.org_id
    if qualified_name and "/" in qualified_name:
        return qualified_name.split("/")[0]
    return HUB_ORG


def remember_task(task: InterMeshTask) -> None:
    task_registry[task.task_id] = task
    if store is not None:
        store.save_task(task)


async def finalize_task_submission(raw_task: dict, submitter: str, token: str | None,
                                   reply_to: str | None = None) -> str | None:
    """Constitue le séquestre puis livre la tâche à son exécutant.

    Extrait du gestionnaire TASK_SUBMIT parce qu'une tâche soumise à
    validation humaine emprunte le même chemin, mais plus tard — au moment
    où quelqu'un l'approuve. Dupliquer cette séquence, c'est se garantir que
    les deux divergeront.

    Retourne un message d'erreur si le séquestre est refusé, sinon None.
    """
    escrow_req = raw_task.get("escrow")
    if escrow_req:
        try:
            hold = escrow_manager.create_hold(
                task_id=raw_task.get("task_id"),
                payer_org=_agent_org(submitter),
                payee_org=_agent_org(raw_task.get("assignee")),
                amount=float(escrow_req.get("amount", 0) or 0),
                currency=escrow_req.get("currency", "USD"),
                auto_release=bool(escrow_req.get("auto_release", True)),
            )
        except EscrowError as ee:
            audit_log.log("ESCROW_REJECTED", submitter, raw_task.get("assignee"), {
                "reason": str(ee), "task_id": raw_task.get("task_id"),
            })
            return str(ee)
        audit_log.log("ESCROW_HELD", submitter, raw_task.get("assignee"), {
            "task_id": hold.task_id, "amount": hold.amount, "currency": hold.currency,
        })

    task = InterMeshTask.from_dict(raw_task)
    remember_task(task)
    entry = audit_log.log("TASK_SUBMITTED", submitter, task.assignee,
                          {"task_id": task.task_id, "title": task.title})
    await broadcast("task_submitted", {
        "task_id": task.task_id, "title": task.title,
        "orchestrator": submitter, "assignee": task.assignee,
    })
    await broadcast("audit_entry", {"entry": entry.to_dict()})
    # Non livrée (exécutant hors ligne) : la tâche reste PENDING et sera
    # réassignée à sa reconnexion.
    await deliver_or_relay(InterMeshMessage(
        type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee,
        reply_to=reply_to, content=task.to_dict(), token=token,
    ))
    return None


# ----------------------------------------------------------------------
# Télémétrie (dashboard, topologie, console sécurité)
# ----------------------------------------------------------------------

async def broadcast(event: str, data: dict) -> None:
    """Diffuse un évènement de télémétrie aux observateurs connectés."""
    if not observers:
        return
    payload = json.dumps({"type": MessageType.TELEMETRY, "content": {"event": event, **data}})
    dead = []
    for ws in list(observers):
        try:
            await ws.send(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        observers.discard(ws)


def snapshot_agents() -> list[dict]:
    now = time.time()
    out = []
    for name, meta in agent_meta.items():
        ident = identity_registry.get(name)
        out.append({
            "name": name,
            "agent_id": ident.agent_id if ident else None,
            "roles": ident.roles if ident else [],
            "capabilities": ident.capabilities if ident else [],
            "status": meta.get("status", "healthy"),
            "connected_at": meta.get("connected_at"),
            "last_seen": meta.get("last_seen", now),
            "msg_count": meta.get("msg_count", 0),
            "online": name in agents,
        })
    return out


# ----------------------------------------------------------------------
# Fédération inter-organisations
# ----------------------------------------------------------------------

def is_peered(org: str) -> bool:
    """Vrai si `org` est une organisation avec laquelle un pairage est actif.

    C'est le seul assouplissement de l'isolement multi-tenant : sans pairage
    explicite (--peer côté sortant, PEER_CONNECT côté entrant), toute adresse
    hors organisation reste refusée.
    """
    return org in peered_hubs


async def _cluster_link(hub_id: str, hub_url: str):
    """Lien vers un Hub frère, ouvert à la demande et réutilisé.

    L'authentification s'appuie sur la clé de signature du Hub, que les
    frères partagent nécessairement — sans elle, un jeton émis par l'un ne
    serait pas accepté par l'autre. Un tiers qui ne la détient pas ne peut
    pas se faire passer pour un frère.
    """
    existing = CLUSTER_LINKS.get(hub_id)
    if existing is not None:
        return existing

    try:
        ws = await websockets.connect(hub_url, open_timeout=5)
        await ws.send(InterMeshMessage(
            type=MessageType.CLUSTER_JOIN, sender=HUB_ID,
            content={"hub_id": HUB_ID, "org": HUB_ORG,
                     "token": generate_token("hub", HUB_ID, ["hub"], HUB_ORG, "cluster")},
        ).to_json())
        reply = InterMeshMessage.from_json(await asyncio.wait_for(ws.recv(), timeout=5))
        if reply.type != MessageType.CLUSTER_JOINED:
            await ws.close()
            print(f"[grappe] frère '{hub_id}' a refusé le lien : {reply.content}")
            return None
        CLUSTER_LINKS[hub_id] = ws
        print(f"[grappe] lien établi vers le Hub frère '{hub_id}' ({hub_url})")
        return ws
    except Exception as exc:
        print(f"[grappe] lien vers '{hub_id}' ({hub_url}) impossible : {exc}")
        return None


async def _forward_to_sibling(msg: InterMeshMessage, presence: dict) -> bool:
    """Transporte `msg` vers le Hub frère qui détient l'agent visé.

    Le message est encapsulé dans un CLUSTER_RELAY que le frère déballe
    puis livre localement, **sans le retransmettre**. Un seul saut : cela
    interdit les boucles sans avoir à compter les sauts, au prix d'exiger
    que la présence soit juste — c'est précisément ce que la base partagée
    garantit.
    """
    ws = await _cluster_link(presence["hub_id"], presence["hub_url"])
    if ws is None:
        return False
    try:
        await ws.send(InterMeshMessage(
            type=MessageType.CLUSTER_RELAY, sender=HUB_ID,
            to=presence["hub_id"], content=msg.to_dict(),
        ).to_json())
        return True
    except Exception as exc:
        # Le frère a disparu : on oublie le lien pour que la prochaine
        # tentative le rétablisse au lieu de réutiliser une socket morte.
        CLUSTER_LINKS.pop(presence["hub_id"], None)
        print(f"[grappe] transfert vers '{presence['hub_id']}' échoué : {exc}")
        return False


async def deliver_or_relay(msg: InterMeshMessage) -> bool:
    """Livre `msg` à l'agent local visé, sinon le relaie au Hub pair de son org.

    Retourne True si le message a été livré ou relayé.
    """
    target = msg.to
    if not target:
        return False

    local = _local_name(target)
    if local is not None:
        try:
            await agents[local].send(msg.to_json())
        except Exception:
            return False
        return True

    # Absent d'ici : peut-être connecté à un Hub frère de la même
    # organisation. Vérifié avant le relais de fédération, qui lui franchit
    # une frontière d'organisation et applique le filtrage de sortie —
    # inapproprié pour du trafic qui reste dans le même tenant.
    if CLUSTER_URL and store is not None:
        try:
            presence = store.find_presence(target, max_age=PRESENCE_TTL)
        except Exception:
            presence = None
        if presence and presence["hub_id"] != HUB_ID and presence["org_id"] == HUB_ORG:
            if await _forward_to_sibling(msg, presence):
                return True

    target_org = _agent_org(target)
    peer_ws = peered_hubs.get(target_org)
    if peer_ws is None:
        return False

    # Le contenu quitte l'organisation : filtrage de sortie. Le Hub ne voit
    # que ce qui n'est pas chiffré de bout en bout ; c'est un garde-fou en
    # complément du filtre appliqué par l'agent, pas à sa place.
    try:
        msg.content, triggered = apply_egress(msg.content, target_org, egress_policy)
    except EgressBlocked as blocked:
        audit_log.log("EGRESS_BLOCKED", msg.sender, target_org, {
            "rule": blocked.rule_name, "message_type": str(msg.type),
        })
        await broadcast("egress_blocked", {
            "sender": msg.sender, "target_org": target_org, "rule": blocked.rule_name,
        })
        print(f"[egress] envoi vers '{target_org}' bloqué par la règle '{blocked.rule_name}'")
        return False
    if triggered:
        audit_log.log("EGRESS_REDACTED", msg.sender, target_org, {
            "rules": triggered, "message_type": str(msg.type),
        })

    relay = InterMeshMessage(
        type=MessageType.FEDERATION_RELAY, sender=HUB_ORG,
        to=target_org, content=msg.to_dict(),
    )
    try:
        await peer_ws.send(relay.to_json())
    except Exception:
        return False
    return True


async def send_task_to_agent(task: InterMeshTask) -> bool:
    return await deliver_or_relay(InterMeshMessage(
        type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, content=task.to_dict(),
    ))


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


async def process_relayed(ws, msg: InterMeshMessage, origin_org: str) -> None:
    """Traite un message déballé d'un FEDERATION_RELAY émis par un Hub pair.

    Le jeton porté par `msg` a été signé par le Hub d'origine avec SA clé
    privée ; il est vérifié ici contre la clé publique que ce Hub a publiée
    au moment du pairage. Un pair ne peut donc ni forger un jeton au nom
    d'une organisation tierce, ni se réclamer d'une autre que la sienne.

    Les réponses repartent sur la même connexion, ce qui les ramène
    naturellement au Hub demandeur.
    """
    if not verify_federated_token(msg.token, origin_org, msg.sender):
        audit_log.log("FEDERATION_TOKEN_REJECTED", msg.sender, HUB_ORG, {
            "origin_org": origin_org, "message_type": str(msg.type),
        })
        await ws.send(InterMeshMessage(
            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
            content=("FEDERATION_DENIED: jeton invalide ou non signé par "
                     f"l'organisation '{origin_org}'."),
        ).to_json())
        return

    if msg.type == MessageType.WHO_IS:
        ident = identity_registry.get(msg.content)
        if ident is not None and ident.org_id == HUB_ORG:
            await ws.send(InterMeshMessage(
                type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id,
                content=ident.to_dict(), token=msg.token,
            ).to_json())

    elif msg.type == MessageType.DISCOVER:
        query = msg.content or {}
        # Un pair ne découvre que les agents de CE Hub, jamais ceux d'un tiers.
        matched = discover_agents(query, HUB_ORG)
        await ws.send(InterMeshMessage(
            type=MessageType.DISCOVER_RESULT, sender="hub", to=msg.sender, reply_to=msg.id,
            content={"query": query, "count": len(matched), "agents": matched}, token=msg.token,
        ).to_json())

    elif msg.type == MessageType.TASK_SUBMIT:
        raw_task = msg.content or {}
        try:
            asimov_engine.validate_task_submission(
                agent_name=msg.sender,
                task_id=raw_task.get("task_id"),
                parent_task_id=raw_task.get("parent_task_id"),
                estimated_cost=float(raw_task.get("estimated_cost") or 0.0),
                payload_text=str(raw_task.get("input_data", raw_task.get("title", ""))),
                org_id=_agent_org(msg.sender),
            )
        except PolicyViolationError as pve:
            entry = audit_log.log("ASIMOV_GUARDRAIL_VIOLATION", msg.sender, raw_task.get("assignee"), {
                "rule": pve.rule_name, "reason": str(pve), "task_id": raw_task.get("task_id"),
                "federated": True,
            })
            await broadcast("audit_entry", {"entry": entry.to_dict()})
            await ws.send(InterMeshMessage(
                type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                content=str(pve), token=msg.token,
            ).to_json())
            return

        task = InterMeshTask.from_dict(raw_task)
        remember_task(task)
        entry = audit_log.log("TASK_SUBMITTED", msg.sender, task.assignee, {
            "task_id": task.task_id, "title": task.title, "federated": True,
        })
        await broadcast("audit_entry", {"entry": entry.to_dict()})
        await deliver_or_relay(InterMeshMessage(
            type=MessageType.TASK_ASSIGN, sender="hub", to=task.assignee, reply_to=msg.id,
            content=raw_task, token=msg.token,
        ))

    elif msg.type == MessageType.TASK_UPDATE:
        td = msg.content or {}
        tid = td.get("task_id")
        if tid in task_registry:
            remember_task(InterMeshTask.from_dict(td))
        if td.get("status") == TaskStatus.COMPLETED.value:
            entry = audit_log.log("TASK_COMPLETED", msg.sender, td.get("orchestrator"), {
                "task_id": tid, "federated": True, "summary": td.get("summary"),
            })
            await broadcast("audit_entry", {"entry": entry.to_dict()})
        await deliver_or_relay(InterMeshMessage(
            type=MessageType.TASK_UPDATE, sender=msg.sender, to=td.get("orchestrator"),
            content=td, token=msg.token,
        ))

    elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE,
                      MessageType.TASK_ASSIGN):
        await deliver_or_relay(msg)


async def connect_peer(remote_org: str, url: str, ca_file: str | None = None) -> None:
    """Maintient une connexion sortante vers un Hub pair, avec reconnexion."""
    ssl_context = build_peer_ssl_context(url, ca_file)
    while True:
        try:
            async with websockets.connect(url, ssl=ssl_context) as ws:
                await ws.send(InterMeshMessage(
                    type=MessageType.PEER_CONNECT, sender=HUB_ORG,
                    content={"org": HUB_ORG, "public_key": HUB_PUBLIC_PEM, "kid": HUB_KEY_ID},
                ).to_json())
                reply = InterMeshMessage.from_json(await ws.recv())
                if reply.type != MessageType.PEER_CONNECTED:
                    raise ConnectionError(f"pairage refusé par '{remote_org}' : {reply.content}")

                remote_key = (reply.content or {}).get("public_key")
                if not remote_key:
                    raise ConnectionError(
                        f"'{remote_org}' n'a pas publié de clé publique — pairage abandonné")
                load_public_pem(remote_key)     # rejette une clé illisible
                peer_public_keys[remote_org] = remote_key
                peered_hubs[remote_org] = ws
                print(f"[peering] connecté au pair '{remote_org}' ({url}) "
                      f"kid={key_fingerprint(remote_key)}")
                try:
                    await handle_agent(ws, HUB_ORG)
                finally:
                    peered_hubs.pop(remote_org, None)
                    peer_public_keys.pop(remote_org, None)
        except Exception as exc:
            print(f"[peering] lien vers '{remote_org}' ({url}) perdu : {exc} — nouvel essai")
        await asyncio.sleep(3)


# ----------------------------------------------------------------------
# Probes HTTP (/healthz, /readyz, /metrics) sur le même port que le WS
# ----------------------------------------------------------------------

_health_handler = HealthCheckHandler(
    readiness_evaluator=lambda: True,
    state_metrics_provider=lambda: {
        "intermesh_connected_agents": len(agents),
        "intermesh_registered_identities": len(identity_registry),
        "intermesh_peered_hubs": len(peered_hubs),
        "intermesh_observers": len(observers),
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
            pending_approvals=pending_approvals, finalize_task=finalize_task_submission,
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


def _is_local_connection(websocket) -> bool:
    """Vrai si la connexion vient de la machine elle-même.

    ⚠️ Derrière un reverse proxy (nginx, Caddy), *toutes* les connexions
    paraissent locales — le proxy est le pair TCP. Le contrôle d'origine ne
    protège donc rien dans cette configuration, et c'est pour cela que
    `--require-api-key` existe : c'est le seul réglage qui tienne quand le
    Hub est derrière un proxy.

    L'en-tête X-Forwarded-For n'est délibérément pas consulté : il est
    fourni par le client tant qu'aucun proxy de confiance ne le réécrit,
    donc s'y fier transformerait ce contrôle en simple formalité.
    """
    try:
        peer = websocket.remote_address
    except Exception:
        return False
    if not peer:
        return False
    host = peer[0]
    return host in ("127.0.0.1", "::1", "localhost") or host.startswith("127.")


async def handle_agent(websocket, my_org: str):
    agent_name = None
    is_observer = False
    try:
        async for raw_data in websocket:
            try:
                msg = InterMeshMessage.from_json(raw_data)
            except Exception as e:
                await websocket.send(InterMeshMessage(type=MessageType.ERROR, sender="hub", content=str(e)).to_json())
                continue

            # -- Kill-switch distant (plan de contrôle) --------------------
            if msg.type == "disconnect_agent" or (
                isinstance(msg.content, dict) and msg.content.get("action") == "kill_agent"
            ):
                target_name = msg.to or (
                    msg.content.get("target_agent") if isinstance(msg.content, dict) else None
                )
                local = _local_name(target_name)
                if local is not None:
                    target_ws = agents[local]
                    entry = audit_log.log("REMOTE_KILL_SWITCH", msg.sender, local,
                                          {"reason": "Control Plane Revocation"})
                    await broadcast("audit_entry", {"entry": entry.to_dict()})
                    try:
                        await target_ws.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=local,
                            content="DISCONNECTED_BY_ADMIN: connexion close depuis le plan de contrôle.",
                        ).to_json())
                        await target_ws.close(1000, "Disconnected by Admin")
                    except Exception:
                        pass
                continue

            # -- Grappe : lien entrant d'un Hub frère ----------------------
            if msg.type == MessageType.CLUSTER_JOIN:
                content = msg.content or {}
                sibling_id = content.get("hub_id") or msg.sender
                refusal = None
                if content.get("org") != my_org:
                    # Un « frère » d'une autre organisation n'en est pas un.
                    # Le trafic entre organisations passe par le pairage, qui
                    # vérifie une signature et filtre ce qui sort.
                    refusal = "organisation différente : utilisez le pairage fédéré."
                else:
                    # Le jeton est signé avec la clé du Hub, que les frères
                    # partagent nécessairement — sans elle, un jeton émis par
                    # l'un serait rejeté par l'autre. Qui ne la détient pas ne
                    # peut pas se faire passer pour un frère.
                    payload = decode_token(content.get("token") or "")
                    if payload is None:
                        refusal = "jeton absent ou signature invalide."
                    elif payload.get("auth_method") != "cluster":
                        refusal = "jeton non émis pour la grappe."
                    elif payload.get("expires_at", 0) < time.time():
                        refusal = "jeton expiré."

                if refusal:
                    await websocket.send(InterMeshMessage(
                        type=MessageType.ERROR, sender=HUB_ID, to=sibling_id,
                        content=f"CLUSTER_REJECTED: {refusal}",
                    ).to_json())
                    audit_log.log("CLUSTER_REJECTED", sibling_id, HUB_ID, {"reason": refusal})
                    continue

                await websocket.send(InterMeshMessage(
                    type=MessageType.CLUSTER_JOINED, sender=HUB_ID, to=sibling_id,
                    content={"hub_id": HUB_ID},
                ).to_json())
                print(f"[grappe] Hub frère '{sibling_id}' accepté")
                audit_log.log("CLUSTER_JOINED", sibling_id, HUB_ID, {})
                continue

            # -- Grappe : message transporté par un frère ------------------
            if msg.type == MessageType.CLUSTER_RELAY:
                inner = InterMeshMessage.from_dict(msg.content or {})
                local = _local_name(inner.to)
                if local is None:
                    # L'agent a quitté ce Hub entre l'écriture de la présence
                    # et l'arrivée du message. Ne pas retransmettre : un seul
                    # saut est ce qui interdit les boucles.
                    audit_log.log("CLUSTER_RELAY_UNDELIVERED", msg.sender, inner.to, {
                        "message_type": str(inner.type),
                    })
                    continue
                try:
                    await agents[local].send(inner.to_json())
                except Exception as exc:
                    print(f"[grappe] livraison locale de '{inner.to}' échouée : {exc}")
                continue

            # -- Pairage Hub à Hub (connexion entrante) --------------------
            if msg.type == MessageType.PEER_CONNECT:
                content = msg.content or {}
                remote_org = content.get("org") or msg.sender
                remote_key = content.get("public_key")
                if not remote_key:
                    # Sans clé publique, les jetons du pair seraient
                    # invérifiables : le lien serait de la confiance aveugle.
                    await websocket.send(InterMeshMessage(
                        type=MessageType.ERROR, sender=my_org, to=remote_org,
                        content="PEER_REJECTED: clé publique absente de la demande de pairage.",
                    ).to_json())
                    audit_log.log("PEER_REJECTED", remote_org, my_org, {"reason": "no_public_key"})
                    continue
                try:
                    load_public_pem(remote_key)
                except Exception as exc:
                    await websocket.send(InterMeshMessage(
                        type=MessageType.ERROR, sender=my_org, to=remote_org,
                        content=f"PEER_REJECTED: clé publique illisible ({exc}).",
                    ).to_json())
                    audit_log.log("PEER_REJECTED", remote_org, my_org, {"reason": "bad_public_key"})
                    continue

                peer_public_keys[remote_org] = remote_key
                peered_hubs[remote_org] = websocket
                await websocket.send(InterMeshMessage(
                    type=MessageType.PEER_CONNECTED, sender=my_org,
                    content={"org": my_org, "public_key": HUB_PUBLIC_PEM, "kid": HUB_KEY_ID},
                ).to_json())
                audit_log.log("PEER_CONNECTED", remote_org, my_org, {
                    "direction": "inbound", "peer_kid": key_fingerprint(remote_key),
                })
                print(f"[peering] pair accepté : {remote_org} (kid={key_fingerprint(remote_key)})")
                continue

            if msg.type == MessageType.FEDERATION_RELAY:
                try:
                    inner = InterMeshMessage.from_dict(msg.content)
                except Exception:
                    continue
                await process_relayed(websocket, inner, msg.sender)
                continue

            # Réponse d'un pair à une requête relayée : à rendre telle quelle
            # à l'agent local qui l'avait demandée (identifié par `to`).
            if msg.type in (MessageType.IDENTITY, MessageType.DISCOVER_RESULT):
                local = _local_name(msg.to)
                if local is not None:
                    try:
                        await agents[local].send(msg.to_json())
                    except Exception:
                        pass
                continue

            if msg.type == MessageType.REGISTER:
                d = msg.content or {}
                raw_name = msg.sender

                # -- Observateurs : télémétrie seule, hors quota ------------
                roles_declared = d.get("roles", ["standard"])
                if "observer" in roles_declared or str(raw_name).startswith(OBSERVER_PREFIXES):
                    is_observer = True
                    observers.add(websocket)
                    await websocket.send(json.dumps({
                        "type": MessageType.TELEMETRY,
                        "content": {
                            "event": "snapshot",
                            "agents": snapshot_agents(),
                            "audit_chain": [e.to_dict() for e in audit_log.chain],
                            "server_time": time.time(),
                        },
                    }))
                    await websocket.send(InterMeshMessage(
                        type=MessageType.REGISTERED, sender="hub", to=raw_name,
                        content={"status": "ready", "token": "observer"},
                    ).to_json())
                    print(f"[observer] {raw_name} connecté")
                    continue

                current_active = len(agents)
                if MAX_AGENTS and current_active >= MAX_AGENTS:
                    err_msg = (f"AGENT_LIMIT_REACHED: ce Hub est configuré pour "
                               f"{MAX_AGENTS} agents simultanés ({current_active} connectés). "
                               f"Relevez --max-agents.")
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
                    # Refus de l'auto-déclaration quand elle n'est pas sûre.
                    # Le contrôle est ici, après la recherche de clé : un
                    # agent qui en présente une valide n'est jamais concerné.
                    local = _is_local_connection(websocket)
                    if REQUIRE_API_KEY or (not local and not ALLOW_SELF_DECLARED):
                        origin = "cette connexion" if local else "une connexion distante"
                        await websocket.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=raw_name,
                            content=(
                                f"SELF_DECLARED_REFUSED: ce Hub n'accepte pas d'identité "
                                f"auto-déclarée depuis {origin}. Un agent doit présenter "
                                f"une clé d'API (`intermesh apikey --org <org>`). "
                                f"Pour un réseau privé, démarrez le Hub avec "
                                f"--allow-self-declared."
                            ),
                        ).to_json())
                        audit_log.log("SELF_DECLARED_REFUSED", raw_name, None, {
                            "local": local, "require_api_key": REQUIRE_API_KEY,
                        })
                        continue

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
                agent_meta[agent_name] = {
                    "connected_at": time.time(), "last_seen": time.time(),
                    "msg_count": 0, "status": "healthy",
                }
                if store is not None:
                    store.save_identity(identity)
                    if CLUSTER_URL:
                        # Déclare où joindre cet agent. Un frère qui doit lui
                        # transmettre un message lira cette ligne : sans elle,
                        # il le tiendrait pour hors ligne.
                        try:
                            store.record_presence(agent_name, HUB_ID, CLUSTER_URL,
                                                  identity.org_id, time.time())
                        except Exception as exc:
                            print(f"[grappe] présence de '{agent_name}' non enregistrée : {exc}")
                token = generate_token(agent_name, identity.agent_id, identity.roles, identity.org_id, auth_method)

                entry = audit_log.log("AGENT_REGISTERED", agent_name, "hub", {"roles": identity.roles, "org_id": identity.org_id})
                await broadcast("agent_connected", {
                    "agent": {**identity.to_dict(), "status": "healthy", "online": True},
                })
                await broadcast("audit_entry", {"entry": entry.to_dict()})

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

                if agent_name and agent_name in agent_meta:
                    agent_meta[agent_name]["last_seen"] = time.time()
                    agent_meta[agent_name]["msg_count"] = agent_meta[agent_name].get("msg_count", 0) + 1

                if msg.type == MessageType.WHO_IS:
                    target_name = msg.content
                    ident = identity_registry.get(target_name)
                    sender_org = _agent_org(msg.sender)
                    if ident is not None and ident.org_id == sender_org:
                        await websocket.send(InterMeshMessage(type=MessageType.IDENTITY, sender="hub", to=msg.sender, reply_to=msg.id, content=ident.to_dict(), token=msg.token).to_json())
                    elif ident is None:
                        # Inconnu localement : interroger le pair si l'org visée
                        # fait l'objet d'un pairage explicite.
                        target_org = _agent_org(target_name)
                        peer_ws = peered_hubs.get(target_org) if target_org != sender_org else None
                        if peer_ws is not None:
                            await peer_ws.send(InterMeshMessage(
                                type=MessageType.FEDERATION_RELAY, sender=HUB_ORG, to=target_org,
                                content=msg.to_dict(),
                            ).to_json())

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

                    # Validation humaine, avant toute constitution de séquestre :
                    # rien ne doit être immobilisé tant qu'une personne n'a pas
                    # tranché, et une tâche refusée n'a donc rien à défaire.
                    assignee_name = raw_task.get("assignee") or ""
                    assignee_identity = identity_registry.get(assignee_name)
                    rule = requires_approval(
                        raw_task,
                        approval_policy,
                        capabilities=(getattr(assignee_identity, "capabilities", None) or []),
                        is_cross_org=(_agent_org(assignee_name) != task_org),
                    )
                    if rule is not None:
                        pending_approvals[raw_task.get("task_id")] = {
                            "task": raw_task,
                            "submitter": msg.sender,
                            "org_id": task_org,
                            "rule": rule.name,
                            "reason": rule.reason,
                            "token": msg.token,
                            "reply_to": msg.id,
                            "submitted_at": time.time(),
                        }
                        entry = audit_log.log("APPROVAL_REQUIRED", msg.sender, assignee_name, {
                            "task_id": raw_task.get("task_id"),
                            "title": raw_task.get("title"),
                            "rule": rule.name,
                            "reason": rule.reason,
                        })
                        await broadcast("approval_required", {
                            "task_id": raw_task.get("task_id"),
                            "title": raw_task.get("title"),
                            "orchestrator": msg.sender,
                            "assignee": assignee_name,
                            "rule": rule.name,
                            "reason": rule.reason,
                        })
                        await broadcast("audit_entry", {"entry": entry.to_dict()})
                        # Aucun TASK_UPDATE n'est renvoyé à l'orchestrateur. Le
                        # gestionnaire TASK_UPDATE du SDK parse le contenu comme
                        # une tâche complète : un message partiel lève une
                        # TaskValidationError dans sa boucle d'écoute et coupe sa
                        # connexion. Un statut « awaiting_approval » exigerait
                        # d'étendre TaskStatus, ce que les agents déjà publiés en
                        # 0.3.0 ne sauraient pas lire.
                        #
                        # L'orchestrateur attend donc, comme devant un exécutant
                        # lent — son propre timeout s'applique. La visibilité de
                        # l'attente passe par approvals.list et l'événement de
                        # télémétrie approval_required, qui est ce que regarde la
                        # personne appelée à trancher.
                        continue

                    err = await finalize_task_submission(raw_task, msg.sender, msg.token, reply_to=msg.id)
                    if err:
                        await websocket.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                            content=err, token=msg.token,
                        ).to_json())
                        continue

                elif msg.type == MessageType.TASK_UPDATE:
                    td = msg.content or {}
                    tid = td.get("task_id")
                    orch = td.get("orchestrator")
                    if tid in task_registry:
                        task = InterMeshTask.from_dict(td)
                        remember_task(task)
                        if task.status == TaskStatus.COMPLETED:
                            entry = audit_log.log("TASK_COMPLETED", msg.sender, orch, {"task_id": tid, "summary": task.summary})
                            await broadcast("task_completed", {"task_id": tid, "summary": task.summary})
                            await broadcast("audit_entry", {"entry": entry.to_dict()})
                            hold = escrow_manager.get(tid)
                            if hold and hold.status.value == "held" and hold.auto_release:
                                escrow_manager.release(tid)
                                audit_log.log("ESCROW_RELEASED", "hub", hold.payee_org, {
                                    "task_id": tid, "amount": hold.amount, "currency": hold.currency,
                                })
                        elif task.status == TaskStatus.FAILED:
                            audit_log.log("TASK_FAILED", msg.sender, orch, {"task_id": tid, "error": task.error_message})
                            await broadcast("task_failed", {
                                "task_id": tid, "summary": task.summary, "error_message": task.error_message,
                            })
                            hold = escrow_manager.get(tid)
                            if hold and hold.status.value == "held":
                                escrow_manager.refund(tid)
                                audit_log.log("ESCROW_REFUNDED", "hub", hold.payer_org, {
                                    "task_id": tid, "amount": hold.amount, "currency": hold.currency,
                                })
                    await deliver_or_relay(InterMeshMessage(
                        type=MessageType.TASK_UPDATE, sender="hub", to=orch,
                        content=td, token=msg.token,
                    ))

                elif msg.type in (MessageType.MESSAGE, MessageType.REQUEST, MessageType.RESPONSE):
                    target = msg.to
                    sender_org = _agent_org(msg.sender)
                    target_org = _agent_org(target) if target else sender_org
                    if target and target_org != sender_org and not is_peered(target_org):
                        await websocket.send(InterMeshMessage(
                            type=MessageType.ERROR, sender="hub", to=msg.sender, reply_to=msg.id,
                            content=f"Isolement Multi-Tenant : '{target}' appartient à une autre organisation.",
                        ).to_json())
                        continue
                    await deliver_or_relay(msg)

                elif msg.type == MessageType.ADMIN_REQUEST:
                    await _handle_admin_request(websocket, msg)

    except websockets.ConnectionClosed:
        pass
    finally:
        if is_observer:
            observers.discard(websocket)
        for org, peer_ws in list(peered_hubs.items()):
            if peer_ws is websocket:
                peered_hubs.pop(org, None)
                peer_public_keys.pop(org, None)
                print(f"[peering] pair '{org}' déconnecté")
        if agent_name and agent_name in agents:
            del agents[agent_name]
            if store is not None and CLUSTER_URL:
                # Conditionné à HUB_ID côté store : si l'agent s'est déjà
                # reconnecté ailleurs, sa nouvelle présence ne doit pas être
                # effacée par le Hub qu'il vient de quitter.
                try:
                    store.clear_presence(agent_name, HUB_ID)
                except Exception:
                    pass
            if agent_name in agent_meta:
                agent_meta[agent_name]["status"] = "unhealthy"
            entry = audit_log.log("AGENT_DISCONNECTED", agent_name, "hub", {"status": "unhealthy"})
            await broadcast("agent_disconnected", {"agent_name": agent_name, "status": "unhealthy"})
            await broadcast("audit_entry", {"entry": entry.to_dict()})


async def main(argv: list[str] | None = None):
    """Démarre le Hub. `argv` permet de l'appeler depuis le CLI sans
    dépendre de sys.argv, qui porte déjà le nom de la sous-commande."""
    global store, api_keys, audit_log, HUB_SECRET, HUB_ORG, SNAPSHOT_DIR
    global HUB_PRIVATE_KEY, HUB_PUBLIC_PEM, HUB_KEY_ID, egress_policy, approval_policy
    global MAX_AGENTS, ALLOW_SELF_DECLARED, REQUIRE_API_KEY
    global HUB_ID, CLUSTER_URL

    parser = argparse.ArgumentParser(description="InterMesh Hub")
    parser.add_argument("--port", type=int, default=8765, help="Port")
    parser.add_argument("--org", type=str, default="default", help="Org")
    parser.add_argument("--ephemeral-state", action="store_true", help="État en mémoire, rien sur disque")
    parser.add_argument("--state-file", type=str, default=None, help="Chemin de la base d'état")
    parser.add_argument("--cluster-url", type=str, default=None,
                        help="Adresse à laquelle les Hubs frères joignent celui-ci "
                             "(ex. ws://hub-2.internal:8765). Active la grappe : "
                             "plusieurs Hubs d'une même organisation partageant "
                             "--state-dsn et --secret-file. Aussi via $INTERMESH_CLUSTER_URL.")
    parser.add_argument("--hub-id", type=str, default=None,
                        help="Identifiant de ce Hub dans la grappe. Généré si absent.")
    parser.add_argument("--allow-self-declared", action="store_true",
                        help="Accepte des identités auto-déclarées depuis des connexions "
                             "distantes. Réseau privé ou test uniquement : sans clé d'API, "
                             "un agent choisit lui-même son organisation et ses rôles.")
    parser.add_argument("--require-api-key", action="store_true",
                        help="Exige une clé d'API pour tout enregistrement, y compris "
                             "depuis localhost. Le seul réglage qui tienne derrière un "
                             "reverse proxy, où toute connexion paraît locale.")
    parser.add_argument("--max-agents", type=int, default=None,
                        help="Plafond d'agents connectés simultanément (0 = illimité, "
                             "défaut). Aussi lisible via $INTERMESH_MAX_AGENTS.")
    parser.add_argument("--state-dsn", type=str, default=None,
                        help="Base d'état PostgreSQL (postgresql://...). Découple l'état "
                             "de la machine : un Hub redémarré ailleurs le retrouve. "
                             "Défaut : $INTERMESH_STATE_DSN")
    parser.add_argument("--ephemeral-secret", action="store_true", help="Clé JWT jetable")
    parser.add_argument("--secret-file", type=str, default=None, help="Chemin du fichier de clé JWT")
    parser.add_argument("--snapshot-dir", type=str, default=None, help="Dossier des instantanés d'état")
    parser.add_argument("--dev-api-keys", action="store_true", help="Active les clés de démonstration")
    parser.add_argument("--peer", action="append", default=[], help="Pair fédéré ORG=wss://host:port")
    parser.add_argument("--tls-cert", type=str, default=None, help="Certificat TLS (sert en wss://)")
    parser.add_argument("--tls-key", type=str, default=None, help="Clé privée du certificat TLS")
    parser.add_argument("--peer-ca", type=str, default=None,
                        help="Autorité de certification des pairs (PKI privée)")
    parser.add_argument("--allow-insecure-peering", action="store_true",
                        help="Autorise un pairage en clair vers un hôte distant (déconseillé)")
    parser.add_argument("--approval-policy", type=str, default=None,
                        help="Politique de validation humaine (JSON) : quelles tâches "
                             "sont retenues jusqu'à arbitrage")
    parser.add_argument("--egress-policy", type=str, default=None,
                        help="Politique de filtrage des contenus sortants (fichier JSON)")

    # Tolérance : tout argument inconnu (utilisé par un autre point d'entrée) est ignoré.
    args, _ = parser.parse_known_args(argv)

    HUB_ORG = args.org
    SNAPSHOT_DIR = args.snapshot_dir

    # Le DSN peut venir de l'environnement : en conteneur, il arrive par une
    # variable d'environnement injectée, pas par la ligne de commande — et un
    # mot de passe passé en argument est visible dans la table des processus.
    HUB_ID = args.hub_id or f"hub-{uuid.uuid4().hex[:12]}"
    CLUSTER_URL = args.cluster_url or os.environ.get("INTERMESH_CLUSTER_URL") or ""

    ALLOW_SELF_DECLARED = args.allow_self_declared
    REQUIRE_API_KEY = args.require_api_key

    if args.max_agents is not None:
        MAX_AGENTS = args.max_agents
    elif os.environ.get("INTERMESH_MAX_AGENTS"):
        MAX_AGENTS = int(os.environ["INTERMESH_MAX_AGENTS"])

    state_dsn = args.state_dsn or os.environ.get("INTERMESH_STATE_DSN")

    if args.ephemeral_state:
        store = InterMeshStore(ephemeral=True)
    elif state_dsn:
        store = InterMeshStore(dsn=state_dsn)
    elif args.state_file:
        store = InterMeshStore(path=args.state_file)
    else:
        store = InterMeshStore()

    identity_registry.update(store.load_identities())
    task_registry.update(store.load_tasks())

    secret, secret_desc = resolve_hub_secret(secret_file=args.secret_file, ephemeral=args.ephemeral_secret)
    HUB_SECRET = secret
    HUB_PRIVATE_KEY = derive_signing_key(secret)
    HUB_PUBLIC_PEM = public_pem(HUB_PRIVATE_KEY)
    HUB_KEY_ID = key_fingerprint(HUB_PUBLIC_PEM)

    api_keys = ApiKeyStore.load(dev_keys=args.dev_api_keys)

    audit_log = ImmutableAuditLog(entries=store.load_audit(), on_append=store.append_audit)

    print(f"InterMesh Hub — org={HUB_ORG} port={args.port}")
    print(f"  secret : {secret_desc}")
    print(f"  clé    : Ed25519 kid={HUB_KEY_ID} (privée non exportée)")
    print(f"  état   : {store.description}")
    print(f"  clés   : {api_keys.source}")
    print(f"  agents : {'illimités' if not MAX_AGENTS else f'{MAX_AGENTS} max'}")
    if REQUIRE_API_KEY:
        identite = "clé d'API exigée partout"
    elif ALLOW_SELF_DECLARED:
        identite = "AUTO-DÉCLARATION AUTORISÉE À DISTANCE (réseau privé uniquement)"
    else:
        identite = "auto-déclaration limitée à localhost"
    print(f"  identité : {identite}")
    if CLUSTER_URL:
        print(f"  grappe : {HUB_ID} joignable sur {CLUSTER_URL}")
        if not (args.state_dsn or os.environ.get("INTERMESH_STATE_DSN")):
            # Sans base partagée, la table de présence est locale : chaque
            # Hub n'y verrait que ses propres agents, donc aucun transfert
            # n'aurait lieu. La grappe serait inerte, silencieusement.
            print("  ⚠️  grappe active sans --state-dsn : les Hubs frères ne "
                  "partageront aucune présence et ne se routeront rien.")
    if not REQUIRE_API_KEY and api_keys.source.startswith("aucune"):
        # Un Hub derrière un reverse proxy voit toutes les connexions comme
        # locales : le contrôle d'origine ne le protège pas, et sans clé
        # configurée il n'a plus aucune barrière.
        print("  ⚠️  aucune clé d'API configurée. Derrière un reverse proxy, "
              "toute connexion paraît locale : utilisez --require-api-key.")

    if args.egress_policy:
        egress_policy = EgressPolicy.load(args.egress_policy)
        print(f"  egress : {egress_policy.name} ({len(egress_policy.rules)} règle(s))")

    if args.approval_policy:
        approval_policy = ApprovalPolicy.load(args.approval_policy)
        print(f"  appro. : {approval_policy.name} ({len(approval_policy.rules)} règle(s))")
    else:
        print("  egress : aucun filtre déclaré")

    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("--tls-cert et --tls-key vont de pair")
    server_ssl = build_server_ssl_context(args.tls_cert, args.tls_key) if args.tls_cert else None
    print(f"  écoute : {'wss:// (TLS)' if server_ssl else 'ws:// (en clair)'}")

    for spec in args.peer:
        try:
            remote_org, url = parse_peer_spec(spec)
            assert_peer_link_is_secure(remote_org, url, args.allow_insecure_peering)
        except ValueError as exc:
            print(f"[peering] --peer ignoré : {exc}")
            continue
        asyncio.create_task(connect_peer(remote_org, url, args.peer_ca))
        print(f"  pair   : {remote_org} -> {url}")

    if CLUSTER_URL and store is not None:
        # Un Hub tué net n'efface pas ses présences. Sans rafraîchissement,
        # rien ne distinguerait ses lignes de celles d'un Hub vivant, et les
        # frères lui transmettraient des messages dans le vide. L'horodatage
        # entretenu rend ces entrées périmables (PRESENCE_TTL).
        async def _presence_heartbeat():
            while True:
                await asyncio.sleep(PRESENCE_HEARTBEAT)
                try:
                    store.touch_presence(HUB_ID, time.time())
                except Exception as exc:
                    print(f"[grappe] battement de présence échoué : {exc}")

        asyncio.create_task(_presence_heartbeat())

    async with websockets.serve(
        lambda ws: handle_agent(ws, args.org),
        "0.0.0.0",
        args.port,
        process_request=process_request,
        ssl=server_ssl,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
