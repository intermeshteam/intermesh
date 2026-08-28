"""
Persistance de l'état du Hub : identités, tâches, journal d'audit.

Un Hub qui redémarre sans mémoire oublie ses agents connus, ses tâches en
cours et son historique d'audit. Ce module fournit un magasin SQLite
(fichier unique, créé en 0600) ou un mode éphémère (tout en mémoire, aucun
fichier créé) pour les tests et le CI.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Optional

from nexus_sdk.audit import AuditEntry
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask


def default_state_path() -> Path:
    """Emplacement par défaut de la base d'état, surchargeable via NEXUS_HOME."""
    base = os.environ.get("NEXUS_HOME")
    if base:
        return Path(base) / "hub_state.db"
    return Path.home() / ".nexus" / "state.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS identities (
    qualified_name TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    idx INTEGER PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


class NexusStore:
    """Stockage persistant (SQLite) ou éphémère (mémoire) du Hub."""

    def __init__(self, path: Optional[str | os.PathLike] = None, ephemeral: bool = False):
        self.ephemeral = ephemeral
        self.path = None if ephemeral else Path(path) if path else default_state_path()
        self.description = "éphémère (mémoire)" if ephemeral else f"sqlite:{self.path}"

        if self.ephemeral:
            self._conn = sqlite3.connect(":memory:")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            is_new = not self.path.exists()
            if is_new:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            else:
                os.chmod(self.path, 0o600)
            self._conn = sqlite3.connect(str(self.path))

        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def __enter__(self) -> "NexusStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Identités
    # ------------------------------------------------------------------

    @staticmethod
    def _identity_key(identity: AgentIdentity) -> str:
        # Convention partagée avec admin.py::_org_of : un nom sans préfixe
        # appartient à l'organisation "default". AgentIdentity préfixe
        # pourtant systématiquement ("default/ghost") — on retire ce
        # préfixe ici pour rester cohérent avec le reste du Hub.
        if identity.org_id == "default":
            return identity.name
        return identity.qualified_name

    def save_identity(self, identity: AgentIdentity) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO identities (qualified_name, payload) VALUES (?, ?)",
            (self._identity_key(identity), json.dumps(identity.to_dict())),
        )
        self._conn.commit()

    def load_identities(self) -> Dict[str, AgentIdentity]:
        rows = self._conn.execute("SELECT qualified_name, payload FROM identities").fetchall()
        return {name: AgentIdentity.from_dict(json.loads(payload)) for name, payload in rows}

    def delete_identity(self, qualified_name: str) -> None:
        self._conn.execute("DELETE FROM identities WHERE qualified_name = ?", (qualified_name,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------

    def save_task(self, task: NexusTask) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, status, payload) VALUES (?, ?, ?)",
            (task.task_id, task.status.value, json.dumps(task.to_dict())),
        )
        self._conn.commit()

    def load_tasks(self) -> Dict[str, NexusTask]:
        rows = self._conn.execute("SELECT task_id, payload FROM tasks").fetchall()
        return {task_id: NexusTask.from_dict(json.loads(payload)) for task_id, payload in rows}

    def count_tasks_by_status(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM tasks GROUP BY status"
        ).fetchall()
        return {status: count for status, count in rows}

    # ------------------------------------------------------------------
    # Journal d'audit
    # ------------------------------------------------------------------

    def load_audit(self) -> list[dict]:
        rows = self._conn.execute("SELECT payload FROM audit_log ORDER BY idx").fetchall()
        return [json.loads(payload) for (payload,) in rows]

    def append_audit(self, entry: AuditEntry) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO audit_log (idx, payload) VALUES (?, ?)",
            (entry.index, json.dumps(entry.to_dict())),
        )
        self._conn.commit()
