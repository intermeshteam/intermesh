"""
Instantanés de l'état du Hub — le « Ctrl+Z » de l'infrastructure.

Une mise à jour rate, une policy trop stricte coupe la production, une
migration d'identités tourne mal : sans instantané, il faut reconstruire
le registre à la main. `snapshot.create` fige l'état reconstructible du
Hub dans un fichier ; `snapshot.restore` le réinstalle.

CE QUI EST DANS UN INSTANTANÉ
-----------------------------
Les identités connues, les tâches, les empreintes de clés d'API, les
policies de garde-fous, les séquestres et les soldes simulés. C'est
exactement l'état que le Hub sait reconstruire seul.

CE QUI N'Y EST PAS, ET POURQUOI
-------------------------------
1. **Les connexions WebSocket vivantes.** Un agent connecté a un état en
   mémoire dans SON processus, hors de portée du Hub. Restaurer ne le
   remet pas dans l'état d'hier — au mieux ça le rend inconnu du
   registre. Les agents concernés sont signalés (`orphaned_online`).

2. **Les effets de bord déjà émis.** Un mail parti est parti. Ceci
   restaure une CONFIGURATION et un REGISTRE, pas le monde extérieur.
   Ce n'est pas une machine à remonter le temps, et le vendre ainsi
   serait mentir à l'exploitant qui s'y fiera à 3h du matin.

3. **Le journal d'audit.** Il est présent dans le fichier à titre de
   référence forensique, mais `restore` ne le réinstalle JAMAIS : le
   remplacer par une version plus courte serait une troncature de
   journal — précisément l'opération qu'un attaquant cherche, et la fin
   de la garantie d'immuabilité. La chaîne vivante est conservée et
   prolongée d'un évènement `SNAPSHOT_RESTORED`. Un instantané ne peut
   donc pas effacer la trace de son propre usage.

4. **Les compteurs volatils** (fenêtres de débit, disjoncteur, cascade) :
   des fenêtres de quelques secondes, dont la restauration ressusciterait
   des blocages déjà expirés.

CONFIDENTIALITÉ DU FICHIER
--------------------------
Le fichier contient les empreintes des clés d'API et l'inventaire complet
de toutes les organisations d'un Hub. Il est écrit en 0600 dans un dossier
0700, et peut être chiffré au repos par passphrase (PBKDF2 + AES-256-GCM).
Le manifeste reste en clair même chiffré, pour que `snapshot.list` reste
utilisable sans détenir la passphrase de chaque instantané.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from nexus_sdk.crypto import decrypt_blob, encrypt_blob
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask

FORMAT = "nexus-snapshot/1"
SUFFIX = ".nxsnap"

# Un nom d'instantané devient un nom de fichier : tout ce qui pourrait
# s'échapper du dossier ('/', '..') ou surprendre un shell est refusé.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class SnapshotError(Exception):
    """Instantané introuvable, illisible, ou nom invalide."""


def default_snapshot_dir() -> Path:
    """Dossier des instantanés, aligné sur NEXUS_HOME comme le reste du SDK."""
    base = os.environ.get("NEXUS_HOME")
    return (Path(base) if base else Path.home() / ".nexus") / "snapshots"


def _validate_name(name: str) -> str:
    if not name or not _NAME_RE.match(name):
        raise SnapshotError(
            f"Nom d'instantané invalide : '{name}'. Lettres, chiffres, "
            f"'.', '_' et '-' uniquement, 64 caractères au plus."
        )
    return name


def _resolve_dir(directory: Optional[str | os.PathLike]) -> Path:
    return Path(directory) if directory else default_snapshot_dir()


def path_for(name: str, directory: Optional[str | os.PathLike] = None) -> Path:
    return _resolve_dir(directory) / f"{_validate_name(name)}{SUFFIX}"


# ----------------------------------------------------------------------
# Capture et application de l'état
# ----------------------------------------------------------------------

def capture_state(
    *,
    identity_registry: dict,
    task_registry: dict,
    api_keys=None,
    asimov_engine=None,
    escrow_manager=None,
) -> dict:
    """Sérialise l'état reconstructible du Hub. Ne touche à rien."""
    state: dict[str, Any] = {
        "identities": {name: i.to_dict() for name, i in identity_registry.items()},
        "tasks": {tid: t.to_dict() for tid, t in task_registry.items()},
    }
    if api_keys is not None:
        state["api_keys"] = api_keys.export_hashed()
    if asimov_engine is not None:
        state["guardrails"] = asimov_engine.export_policies()
    if escrow_manager is not None:
        state["escrow"] = escrow_manager.export_state()
    return state


def apply_state(
    state: dict,
    *,
    identity_registry: dict,
    task_registry: dict,
    connected_agents: Optional[dict] = None,
    store=None,
    api_keys=None,
    asimov_engine=None,
    escrow_manager=None,
) -> dict:
    """
    Réinstalle un état capturé, en mémoire et dans le magasin persistant.

    Les registres sont mutés en place (`clear`/`update`) plutôt que
    remplacés : le Hub et la console partagent ces mêmes objets, une
    réaffectation ne serait vue par aucun des deux.

    Returns:
        Un rapport de ce qui a réellement été restauré, y compris ce qui
        a été refusé — un `restore` partiel doit se voir, pas se deviner.
    """
    report: dict[str, Any] = {"restored": [], "skipped": []}

    identities = {
        name: AgentIdentity.from_dict(raw)
        for name, raw in (state.get("identities") or {}).items()
    }
    tasks = {
        tid: NexusTask.from_dict(raw)
        for tid, raw in (state.get("tasks") or {}).items()
    }

    identity_registry.clear()
    identity_registry.update(identities)
    task_registry.clear()
    task_registry.update(tasks)
    report["restored"].append("identities")
    report["restored"].append("tasks")
    report["identities"] = len(identities)
    report["tasks"] = len(tasks)

    if store is not None and not getattr(store, "ephemeral", False):
        store.replace_identities(identities)
        store.replace_tasks(tasks)
        report["restored"].append("store")

    if api_keys is not None and "api_keys" in state:
        try:
            api_keys.import_hashed(state["api_keys"])
            report["restored"].append("api_keys")
            report["api_keys"] = len(state["api_keys"])
        except PermissionError as exc:
            report["skipped"].append({"what": "api_keys", "reason": str(exc)})

    if asimov_engine is not None and "guardrails" in state:
        asimov_engine.import_policies(state["guardrails"])
        report["restored"].append("guardrails")

    if escrow_manager is not None and "escrow" in state:
        escrow_manager.import_state(state["escrow"])
        report["restored"].append("escrow")

    # Un agent connecté absent de l'instantané reste connecté : sa socket
    # est vivante, on ne peut pas la « dé-ouvrir ». Il est simplement
    # inconnu du registre restauré. L'exploitant doit le savoir pour
    # décider — le déconnecter, ou le laisser se réenregistrer.
    if connected_agents:
        orphans = sorted(set(connected_agents) - set(identity_registry))
        if orphans:
            report["orphaned_online"] = orphans

    return report


# ----------------------------------------------------------------------
# Fichiers
# ----------------------------------------------------------------------

def save(
    name: str,
    state: dict,
    *,
    hub_org: str = "default",
    audit_head: Optional[dict] = None,
    directory: Optional[str | os.PathLike] = None,
    passphrase: Optional[str] = None,
    overwrite: bool = True,
) -> dict:
    """
    Écrit un instantané sur disque et retourne son manifeste.

    Args:
        audit_head: `{"index", "hash"}` de la tête de chaîne d'audit au
            moment de la capture. Sert de repère forensique : il indique
            où en était le journal, sans jamais permettre de l'y ramener.
        passphrase: Si fournie, seule la section `state` est chiffrée ;
            le manifeste reste lisible pour l'inventaire.
        overwrite: `False` refuse d'écraser un instantané existant.

    L'écriture passe par un fichier temporaire remplacé atomiquement :
    une interruption en cours d'écriture ne peut pas laisser derrière
    elle un instantané tronqué qui paraîtrait valide.
    """
    target = path_for(name, directory)
    if target.exists() and not overwrite:
        raise SnapshotError(f"L'instantané '{name}' existe déjà.")

    manifest = {
        "name": name,
        "format": FORMAT,
        "created_at": time.time(),
        "hub_org": hub_org,
        "encrypted": bool(passphrase),
        "counts": {
            "identities": len(state.get("identities") or {}),
            "tasks": len(state.get("tasks") or {}),
            "api_keys": len(state.get("api_keys") or {}),
            "escrow_holds": len((state.get("escrow") or {}).get("holds") or []),
        },
        # Repère seulement : `restore` ne remet jamais la chaîne d'audit
        # à cet index (voir le docstring du module).
        "audit_head": audit_head or {},
    }

    document: dict[str, Any] = {"format": FORMAT, "manifest": manifest}
    if passphrase:
        document["encrypted_state"] = encrypt_blob(json.dumps(state), passphrase)
    else:
        document["state"] = state

    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(document, indent=2).encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp, target)

    return manifest


def _read_document(target: Path) -> dict:
    if not target.is_file():
        raise SnapshotError(f"Instantané introuvable : {target.name.removesuffix(SUFFIX)}")
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"{target} n'est pas un instantané lisible : {exc}") from exc
    if document.get("format") != FORMAT:
        raise SnapshotError(
            f"Format d'instantané non supporté : {document.get('format')!r} "
            f"(attendu {FORMAT!r})."
        )
    return document


def load(
    name: str,
    *,
    directory: Optional[str | os.PathLike] = None,
    passphrase: Optional[str] = None,
) -> tuple[dict, dict]:
    """
    Retourne `(manifeste, état)`.

    Raises:
        SnapshotError: instantané absent, illisible, ou passphrase
            manquante/incorrecte.
    """
    document = _read_document(path_for(name, directory))
    manifest = document.get("manifest") or {}

    if "encrypted_state" in document:
        if not passphrase:
            raise SnapshotError(
                f"L'instantané '{name}' est chiffré : une passphrase est requise."
            )
        try:
            state = json.loads(decrypt_blob(document["encrypted_state"], passphrase))
        except Exception as exc:
            # AES-GCM ne distingue pas passphrase fausse et fichier altéré.
            raise SnapshotError(
                f"Déchiffrement impossible pour '{name}' : passphrase incorrecte "
                f"ou fichier altéré."
            ) from exc
    else:
        state = document.get("state") or {}

    return manifest, state


def list_snapshots(directory: Optional[str | os.PathLike] = None) -> list[dict]:
    """Manifestes de tous les instantanés lisibles, du plus récent au plus ancien."""
    base = _resolve_dir(directory)
    if not base.is_dir():
        return []

    manifests = []
    for entry in sorted(base.glob(f"*{SUFFIX}")):
        try:
            document = _read_document(entry)
        except SnapshotError:
            # Un fichier corrompu ne doit pas rendre l'inventaire inutilisable.
            continue
        manifest = document.get("manifest") or {}
        manifest.setdefault("name", entry.name.removesuffix(SUFFIX))
        manifests.append(manifest)

    manifests.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return manifests


def delete(name: str, directory: Optional[str | os.PathLike] = None) -> bool:
    """Supprime un instantané. `False` s'il n'existait pas."""
    target = path_for(name, directory)
    if not target.is_file():
        return False
    target.unlink()
    return True
