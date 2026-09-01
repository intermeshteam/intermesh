"""
Stockage de l'état du Hub : SQLite et PostgreSQL derrière la même interface.

Un fichier SQLite est lié à sa machine. Le pointer vers PostgreSQL découple
l'état du processus : un Hub redémarré ailleurs retrouve ses identités, ses
tâches et sa chaîne d'audit.

Les tests PostgreSQL ne s'exécutent que si `INTERMESH_TEST_PG_DSN` désigne
une base joignable — ils sont ignorés sinon, plutôt que d'échouer sur une
machine qui n'en a pas. Pour les lancer :

    docker run -d --name im-pg -e POSTGRES_PASSWORD=pw \\
        -e POSTGRES_DB=intermesh -p 55433:5432 postgres:16-alpine
    export INTERMESH_TEST_PG_DSN=postgresql://postgres:pw@localhost:55433/intermesh
    pytest tests/test_store_backends.py
"""

import os
import tempfile

import pytest

from intermesh.audit import ImmutableAuditLog
from intermesh.identity import AgentIdentity
from intermesh.store import InterMeshStore, _redact_dsn, is_postgres_dsn
from intermesh.task import InterMeshTask

PG_DSN = os.environ.get("INTERMESH_TEST_PG_DSN")
needs_pg = pytest.mark.skipif(not PG_DSN, reason="INTERMESH_TEST_PG_DSN non défini")


def _identity(name="worker", org="acme"):
    return AgentIdentity.from_dict(
        {"name": name, "org_id": org, "capabilities": ["pricing"], "roles": ["worker"]}
    )


def _task(title="Devis"):
    return InterMeshTask(title=title, assignee="acme/worker",
                         orchestrator="acme/lead", input_data={"q": 10})


# ----------------------------------------------------------------------
# Reconnaissance du DSN (aucune base requise)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("postgresql://u:p@h/db", True),
    ("postgres://u:p@h/db", True),
    ("/var/lib/intermesh/state.db", False),
    ("", False),
    (None, False),
])
def test_dsn_detection(value, expected):
    assert is_postgres_dsn(value) is expected


def test_password_never_reaches_the_description():
    """`description` est affichée au démarrage et renvoyée par hub.info.
    Un mot de passe qui y transite finit dans les journaux."""
    red = _redact_dsn("postgresql://user:supersecret@db.example.com:5432/intermesh")

    assert "supersecret" not in red
    assert "user" in red and "db.example.com" in red


def test_redaction_leaves_a_passwordless_dsn_readable():
    red = _redact_dsn("postgresql://db.example.com/intermesh")
    assert "db.example.com" in red


# ----------------------------------------------------------------------
# Le contrat, vérifié à l'identique sur chaque moteur
# ----------------------------------------------------------------------

def _clear(store: InterMeshStore) -> None:
    """Vide les trois tables avant un test.

    `replace_identities` et `replace_tasks` couvrent deux d'entre elles,
    mais le journal d'audit n'a volontairement pas d'API d'effacement — il
    est censé être inaltérable. On passe donc par la connexion, ce qui est
    acceptable ici et nulle part ailleurs.
    """
    for table in ("identities", "tasks", "audit_log"):
        store._conn.execute(f"DELETE FROM {table}")
    store._conn.commit()


def _round_trip(store: InterMeshStore):
    _clear(store)
    ident = _identity()
    store.save_identity(ident)
    # Deux fois : l'UPSERT ne doit pas violer la clé primaire.
    store.save_identity(ident)
    assert "acme/worker" in store.load_identities()

    task = _task()
    store.save_task(task)
    store.save_task(task)
    assert task.task_id in store.load_tasks()
    assert store.count_tasks_by_status()["pending"] >= 1

    log = ImmutableAuditLog()
    entry = log.log("TEST_EVENT", "a", "b", {"k": 1})
    store.append_audit(entry)
    store.append_audit(entry)
    assert len(store.load_audit()) == 1

    # Restauration d'instantané : vidage et réécriture atomiques.
    store.replace_identities({})
    assert store.load_identities() == {}
    store.replace_identities({"acme/worker": ident})
    assert len(store.load_identities()) == 1

    store.replace_tasks({})
    assert store.load_tasks() == {}
    store.replace_tasks({task.task_id: task})
    assert len(store.load_tasks()) == 1

    store.delete_identity("acme/worker")
    assert store.load_identities() == {}


def test_sqlite_round_trip():
    work = tempfile.mkdtemp()
    store = InterMeshStore(path=os.path.join(work, "state.db"))
    assert store.postgres is False
    _round_trip(store)
    store.close()


def test_ephemeral_round_trip():
    store = InterMeshStore(ephemeral=True)
    assert store.postgres is False
    _round_trip(store)
    store.close()


def test_sqlite_file_is_created_private():
    """L'état contient des identités et un journal d'audit : il ne doit pas
    être lisible par les autres comptes de la machine."""
    work = tempfile.mkdtemp()
    path = os.path.join(work, "state.db")
    store = InterMeshStore(path=path)
    store.close()

    assert oct(os.stat(path).st_mode)[-3:] == "600"


@needs_pg
def test_postgres_round_trip():
    store = InterMeshStore(dsn=PG_DSN)
    assert store.postgres is True
    _round_trip(store)
    store.close()


@needs_pg
def test_postgres_description_hides_the_password():
    store = InterMeshStore(dsn=PG_DSN)
    try:
        assert "***" in store.description or "@" not in store.description
        if ":" in PG_DSN.split("@")[0].split("//")[-1]:
            secret = PG_DSN.split("@")[0].split(":")[-1]
            assert secret not in store.description
    finally:
        store.close()


@needs_pg
def test_postgres_state_survives_reconnection():
    """Le point qui justifie tout le reste : l'état n'appartient plus au
    processus, donc un Hub redémarré ailleurs le retrouve."""
    first = InterMeshStore(dsn=PG_DSN)
    first.replace_identities({})
    first.replace_tasks({})
    first.save_identity(_identity(name="survivor"))
    first.save_task(_task(title="Tâche persistante"))
    first.close()

    second = InterMeshStore(dsn=PG_DSN)
    try:
        assert "acme/survivor" in second.load_identities()
        titles = [t.title for t in second.load_tasks().values()]
        assert "Tâche persistante" in titles
    finally:
        second.close()
