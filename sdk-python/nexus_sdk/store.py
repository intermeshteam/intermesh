"""
Persistance de l'état du Hub.

Sans elle, l'arrêt du Hub efface le registre d'identités, les tâches en
cours et le journal d'audit — ce dernier prétendant pourtant offrir une
garantie d'immuabilité. Un journal qui disparaît à chaque `Ctrl+C` ne
prouve rien à un auditeur.

Le stockage repose sur SQLite : présent dans la bibliothèque standard,
transactionnel, et adapté à la charge d'un Hub unique. Il devra céder la
place à PostgreSQL le jour où plusieurs Hubs partageront un même état.

Ce qui n'est *pas* persisté : les connexions WebSocket actives. Un agent
« en ligne » est une propriété du processus courant, pas un fait durable.
Après un redémarrage, les identités connues sont rechargées mais tous les
agents sont considérés hors ligne jusqu'à leur reconnexion.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from nexus_sdk.audit import AuditEntry
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identities (
    qualified_name TEXT PRIMARY KEY,
    payload        TEXT NOT NULL,
    updated_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id    TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    status     TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS audit_log (
    idx     INTEGER PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


def default_state_path() -> Path:
    """Emplacement par défaut de la base, surchargeable via NEXUS_HOME."""
    base = os.environ.get("NEXUS_HOME")
    return (Path(base) if base else Path.home() / ".nexus") / "hub_state.db"


class NexusStore:
    """État durable du Hub : identités, tâches et journal d'audit."""

    def __init__(self, path: str | os.PathLike | None = None, ephemeral: bool = False):
        """
        Args:
            path:      Chemin de la base. Par défaut ~/.nexus/hub_state.db.
            ephemeral: Base en mémoire, effacée à la fermeture (tests, CI).
        """
        self.ephemeral = ephemeral

        if ephemeral:
            self.path = ":memory:"
            self.description = "en mémoire (perdu au redémarrage)"
        else:
            resolved = Path(path) if path else default_state_path()
            resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            existed = resolved.exists()
            self.path = str(resolved)
            self.description = f"{resolved}" + ("" if existed else " (créée)")

        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if not ephemeral:
            # WAL : une écriture interrompue ne corrompt pas la base.
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

        if not ephemeral:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Identités
    # ------------------------------------------------------------------

    def save_identity(self, identity: AgentIdentity) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO identities (qualified_name, payload, updated_at) "
            "VALUES (?, ?, ?)",
            (identity.qualified_name, json.dumps(identity.to_dict()), time.time()),
        )
        self._conn.commit()

    def load_identities(self) -> dict[str, AgentIdentity]:
        rows = self._conn.execute(
            "SELECT qualified_name, payload FROM identities"
        ).fetchall()
        return {
            r["qualified_name"]: AgentIdentity.from_dict(json.loads(r["payload"]))
            for r in rows
        }

    def delete_identity(self, qualified_name: str) -> None:
        self._conn.execute(
            "DELETE FROM identities WHERE qualified_name = ?", (qualified_name,)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------

    def save_task(self, task: NexusTask) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, payload, status, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (task.task_id, json.dumps(task.to_dict()), task.status.value, task.updated_at),
        )
        self._conn.commit()

    def load_tasks(self) -> dict[str, NexusTask]:
        rows = self._conn.execute("SELECT payload FROM tasks").fetchall()
        return {
            t.task_id: t
            for t in (NexusTask.from_dict(json.loads(r["payload"])) for r in rows)
        }

    def count_tasks_by_status(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # ------------------------------------------------------------------
    # Journal d'audit
    # ------------------------------------------------------------------

    def append_audit(self, entry: AuditEntry) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO audit_log (idx, payload) VALUES (?, ?)",
            (entry.index, json.dumps(entry.to_dict())),
        )
        self._conn.commit()

    def load_audit(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT payload FROM audit_log ORDER BY idx ASC"
        ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "NexusStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
