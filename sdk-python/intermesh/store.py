"""
Persistance de l'état du Hub : identités, tâches, journal d'audit.

Un Hub qui redémarre sans mémoire oublie ses agents connus, ses tâches en
cours et son historique d'audit. Ce module fournit trois modes :

  * **éphémère** — tout en mémoire, aucun fichier créé. Tests et CI.
  * **SQLite** — fichier unique en 0600. Le défaut, et le bon choix pour
    un Hub sur une seule machine.
  * **PostgreSQL** — base partagée. Nécessaire dès que l'état doit survivre
    à la machine elle-même, ou être vu par plus d'un processus.

Ce que PostgreSQL apporte, et ce qu'il n'apporte pas
----------------------------------------------------

Un fichier SQLite est lié à son système de fichiers : il ne peut pas être
lu par un Hub qui tourne ailleurs, et un disque perdu emporte l'état avec
lui. Le pointer vers PostgreSQL découple donc l'état du processus — un Hub
redémarré sur une autre machine retrouve ses identités, ses tâches et sa
chaîne d'audit.

Cela **ne suffit pas** à faire tourner deux Hubs actifs en parallèle. Les
sockets des agents connectés, elles, restent en mémoire dans chaque
processus : deux Hubs partageant la même base ne se verraient pas
mutuellement leurs agents en ligne, et une tâche routée par l'un
n'atteindrait pas un exécutant connecté à l'autre. Ce module lève le
verrou du stockage, pas celui du routage.

Ce qui devient possible : une reprise sur une autre machine sans perte
d'état, et une sauvegarde continue par l'outillage PostgreSQL habituel.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Optional

from intermesh.audit import AuditEntry
from intermesh.identity import AgentIdentity
from intermesh.task import InterMeshTask

POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def default_state_path() -> Path:
    """Emplacement par défaut de la base d'état, surchargeable via INTERMESH_HOME."""
    base = os.environ.get("INTERMESH_HOME")
    if base:
        return Path(base) / "hub_state.db"
    return Path.home() / ".intermesh" / "state.db"


def is_postgres_dsn(value: str | None) -> bool:
    return bool(value) and value.startswith(POSTGRES_SCHEMES)


# Le schéma est écrit en SQL commun aux deux moteurs. `payload` porte du
# JSON sérialisé plutôt que des colonnes typées : le Hub fait évoluer ses
# structures plus vite qu'une migration de schéma ne le permettrait, et
# rien ici n'est interrogé autrement que par clé primaire.
_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS identities (
           qualified_name TEXT PRIMARY KEY,
           payload TEXT NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS tasks (
           task_id TEXT PRIMARY KEY,
           status TEXT NOT NULL,
           payload TEXT NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS audit_log (
           idx BIGINT PRIMARY KEY,
           payload TEXT NOT NULL
       )""",
)


class InterMeshStore:
    """Stockage de l'état du Hub : mémoire, SQLite ou PostgreSQL.

    L'interface publique est la même dans les trois cas — le reste du Hub
    n'a pas à savoir où l'état atterrit.
    """

    def __init__(
        self,
        path: Optional[str | os.PathLike] = None,
        ephemeral: bool = False,
        dsn: Optional[str] = None,
    ):
        self.ephemeral = ephemeral
        self.dsn = dsn
        self.postgres = is_postgres_dsn(dsn)
        self.path: Optional[Path] = None

        if self.postgres:
            self._connect_postgres(dsn)
        elif ephemeral:
            self._conn = sqlite3.connect(":memory:")
            self.description = "éphémère (mémoire)"
        else:
            self.path = Path(path) if path else default_state_path()
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self.path.exists():
                # Créé en 0600 dès l'origine plutôt que corrigé après coup :
                # entre la création et le chmod, le fichier serait lisible.
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            else:
                os.chmod(self.path, 0o600)
            self._conn = sqlite3.connect(str(self.path))
            self.description = f"sqlite:{self.path}"

        for statement in _STATEMENTS:
            self._conn.execute(statement)
        self._conn.commit()

    def _connect_postgres(self, dsn: str) -> None:
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - dépend de l'installation
            raise RuntimeError(
                "Un DSN PostgreSQL a été fourni mais le pilote `psycopg` est absent. "
                "Installez-le avec :  pip install 'intermesh[postgres]'"
            ) from exc
        self._conn = psycopg.connect(dsn, autocommit=False)
        # Le DSN porte le mot de passe : il ne doit apparaître ni dans les
        # journaux du Hub, ni dans hub.info, qui affichent cette description.
        self.description = f"postgresql:{_redact_dsn(dsn)}"

    # ------------------------------------------------------------------
    # Dialecte
    # ------------------------------------------------------------------

    def _sql(self, statement: str) -> str:
        """Traduit les marqueurs de paramètres pour le moteur cible.

        Les requêtes sont écrites une fois, en style SQLite (`?`). psycopg
        n'accepte que `%s` — et le `%` littéral devrait alors être doublé,
        ce qu'aucune requête d'ici n'utilise.
        """
        return statement.replace("?", "%s") if self.postgres else statement

    def _upsert(self, table: str, key: str, columns: tuple[str, ...]) -> str:
        """UPSERT dans le dialecte du moteur.

        `INSERT OR REPLACE` est propre à SQLite ; PostgreSQL exige la forme
        `ON CONFLICT ... DO UPDATE`, qui a l'avantage de préserver les
        colonnes non citées au lieu de recréer la ligne.
        """
        cols = ", ".join(columns)
        marks = ", ".join("?" for _ in columns)
        if not self.postgres:
            return self._sql(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})")
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
        return self._sql(
            f"INSERT INTO {table} ({cols}) VALUES ({marks}) "
            f"ON CONFLICT ({key}) DO UPDATE SET {updates}"
        )

    def _fetch(self, statement: str, params: tuple = ()) -> list:
        cur = self._conn.execute(self._sql(statement), params)
        rows = cur.fetchall()
        if self.postgres:
            cur.close()
        return rows

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def __enter__(self) -> "InterMeshStore":
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
            self._upsert("identities", "qualified_name", ("qualified_name", "payload")),
            (self._identity_key(identity), json.dumps(identity.to_dict())),
        )
        self._conn.commit()

    def load_identities(self) -> Dict[str, AgentIdentity]:
        rows = self._fetch("SELECT qualified_name, payload FROM identities")
        return {name: AgentIdentity.from_dict(json.loads(payload)) for name, payload in rows}

    def delete_identity(self, qualified_name: str) -> None:
        self._conn.execute(
            self._sql("DELETE FROM identities WHERE qualified_name = ?"), (qualified_name,)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Tâches
    # ------------------------------------------------------------------

    def save_task(self, task: InterMeshTask) -> None:
        self._conn.execute(
            self._upsert("tasks", "task_id", ("task_id", "status", "payload")),
            (task.task_id, task.status.value, json.dumps(task.to_dict())),
        )
        self._conn.commit()

    def load_tasks(self) -> Dict[str, InterMeshTask]:
        rows = self._fetch("SELECT task_id, payload FROM tasks")
        return {task_id: InterMeshTask.from_dict(json.loads(payload)) for task_id, payload in rows}

    def count_tasks_by_status(self) -> Dict[str, int]:
        rows = self._fetch("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        return {status: count for status, count in rows}

    # ------------------------------------------------------------------
    # Remplacement en bloc (restauration d'instantané)
    # ------------------------------------------------------------------

    def _replace_all(self, table: str, statement: str, rows: list[tuple]) -> None:
        """Vide une table et la réécrit, en une seule transaction.

        Le `DELETE` et les `INSERT` doivent être atomiques : un plantage
        entre les deux laisserait un Hub sans aucune donnée persistée, pire
        que l'état qu'on cherchait à restaurer.

        `with connexion` valide ou annule dans les deux pilotes, mais ne
        les fait pas se comporter identiquement sur le reste — d'où le
        commit explicite côté PostgreSQL.
        """
        try:
            if self.postgres:
                # psycopg n'expose `executemany` que sur un curseur, pas sur
                # la connexion — contrairement à sqlite3.
                with self._conn.cursor() as cur:
                    cur.execute(self._sql(f"DELETE FROM {table}"))
                    if rows:
                        cur.executemany(self._sql(statement), rows)
            else:
                self._conn.execute(self._sql(f"DELETE FROM {table}"))
                self._conn.executemany(self._sql(statement), rows)
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()

    def replace_identities(self, identities: Dict[str, AgentIdentity]) -> None:
        self._replace_all(
            "identities",
            "INSERT INTO identities (qualified_name, payload) VALUES (?, ?)",
            [(name, json.dumps(i.to_dict())) for name, i in identities.items()],
        )

    def replace_tasks(self, tasks: Dict[str, InterMeshTask]) -> None:
        self._replace_all(
            "tasks",
            "INSERT INTO tasks (task_id, status, payload) VALUES (?, ?, ?)",
            [(t.task_id, t.status.value, json.dumps(t.to_dict())) for t in tasks.values()],
        )

    # ------------------------------------------------------------------
    # Journal d'audit
    # ------------------------------------------------------------------

    def load_audit(self) -> list[dict]:
        rows = self._fetch("SELECT payload FROM audit_log ORDER BY idx")
        return [json.loads(payload) for (payload,) in rows]

    def append_audit(self, entry: AuditEntry) -> None:
        self._conn.execute(
            self._upsert("audit_log", "idx", ("idx", "payload")),
            (entry.index, json.dumps(entry.to_dict())),
        )
        self._conn.commit()


def _redact_dsn(dsn: str) -> str:
    """Masque le mot de passe d'un DSN avant qu'il n'atteigne un journal."""
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(dsn)
        if parts.password:
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            netloc = f"{parts.username}:***@{host}" if parts.username else host
            return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return "postgresql (dsn masqué)"
