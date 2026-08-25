"""Tests de la persistance de l'état du Hub."""

import json
import sqlite3
import stat

import pytest

from nexus_sdk import AgentIdentity, ImmutableAuditLog, NexusStore, NexusTask, TaskStatus
from nexus_sdk.store import default_state_path


@pytest.fixture
def db(tmp_path):
    return tmp_path / "hub_state.db"


def test_identities_survive_restart(db):
    """Le registre d'identités doit être rechargé à l'identique."""
    identity = AgentIdentity(
        name="worker_1", org_id="acme",
        capabilities=["calculate", "translate"],
        roles=["worker"], permissions=["compute:execute"],
        metadata={"region": "africa"},
    )

    with NexusStore(path=db) as store:
        store.save_identity(identity)

    with NexusStore(path=db) as store:
        restored = store.load_identities()

    assert "acme/worker_1" in restored
    reloaded = restored["acme/worker_1"]
    assert reloaded.agent_id == identity.agent_id
    assert reloaded.capabilities == ["calculate", "translate"]
    assert reloaded.permissions == ["compute:execute"]
    assert reloaded.metadata == {"region": "africa"}
    assert reloaded.verify_fingerprint(), "l'empreinte doit rester valide après rechargement"
    print("✓ Identités restaurées, empreinte intacte")


def test_tasks_survive_restart_with_status(db):
    """Une tâche inachevée doit être retrouvée dans son état exact."""
    running = NexusTask(title="Analyse", orchestrator="acme/lead",
                        assignee="acme/worker", input_data={"x": 1})
    running.update_status(TaskStatus.RUNNING)

    done = NexusTask(title="Calcul", orchestrator="acme/lead",
                     assignee="acme/worker", input_data={"y": 2})
    done.update_status(TaskStatus.COMPLETED, output_data={"result": 42})

    with NexusStore(path=db) as store:
        store.save_task(running)
        store.save_task(done)

    with NexusStore(path=db) as store:
        tasks = store.load_tasks()
        counts = store.count_tasks_by_status()

    assert tasks[running.task_id].status == TaskStatus.RUNNING
    assert tasks[done.task_id].status == TaskStatus.COMPLETED
    assert tasks[done.task_id].output_data == {"result": 42}
    assert counts == {"running": 1, "completed": 1}
    print("✓ Tâches restaurées avec leur statut")


def test_task_update_overwrites_rather_than_duplicates(db):
    """Faire progresser une tâche ne doit pas en créer une seconde."""
    task = NexusTask(title="T", orchestrator="a", assignee="b", input_data={})

    with NexusStore(path=db) as store:
        store.save_task(task)
        task.update_status(TaskStatus.RUNNING)
        store.save_task(task)
        task.update_status(TaskStatus.COMPLETED, output_data={"ok": True})
        store.save_task(task)
        assert store.count_tasks_by_status() == {"completed": 1}
    print("✓ La mise à jour remplace, sans doublon")


def test_audit_chain_survives_and_continues(db):
    """
    Le journal doit reprendre la chaîne existante, pas repartir d'un
    nouveau genesis — sinon l'historique antérieur est orphelin.
    """
    with NexusStore(path=db) as store:
        log = ImmutableAuditLog(entries=store.load_audit(), on_append=store.append_audit)
        log.log("AGENT_REGISTERED", "acme/worker")
        log.log("TASK_SUBMITTED", "acme/lead", "acme/worker", {"task_id": "t1"})
        first_len = len(log.chain)
        last_hash = log.chain[-1].hash

    with NexusStore(path=db) as store:
        reloaded = ImmutableAuditLog(entries=store.load_audit(), on_append=store.append_audit)

        assert len(reloaded.chain) == first_len, "la chaîne doit être reprise entière"
        assert reloaded.chain[-1].hash == last_hash
        assert reloaded.chain[0].event_type == "GENESIS"
        assert reloaded.verify_integrity(), "la chaîne rechargée doit être valide"

        # La chaîne se prolonge correctement après rechargement
        reloaded.log("AGENT_DISCONNECTED", "acme/worker")
        assert reloaded.chain[-1].prev_hash == last_hash
        assert reloaded.verify_integrity()
    print("✓ La chaîne d'audit survit et se prolonge")


def test_tampering_with_the_database_is_detected(db):
    """
    Le point entier du chaînage Merkle : modifier le journal *sur disque*,
    hors du Hub, doit être détectable au rechargement.
    """
    with NexusStore(path=db) as store:
        log = ImmutableAuditLog(entries=store.load_audit(), on_append=store.append_audit)
        log.log("TASK_SUBMITTED", "acme/lead", "acme/worker", {"amount": 100})
        log.log("TASK_COMPLETED", "acme/worker", "acme/lead", {"amount": 100})

    # Un attaquant édite directement la base
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT payload FROM audit_log WHERE idx = 1").fetchone()
    entry = json.loads(row[0])
    entry["metadata"]["amount"] = 999_999
    conn.execute("UPDATE audit_log SET payload = ? WHERE idx = 1", (json.dumps(entry),))
    conn.commit()
    conn.close()

    with NexusStore(path=db) as store:
        reloaded = ImmutableAuditLog(entries=store.load_audit())
        assert reloaded.verify_integrity() is False, "l'altération doit être détectée"
    print("✓ Altération de la base détectée")


def test_ephemeral_store_writes_nothing(tmp_path):
    """Le mode éphémère ne doit créer aucun fichier."""
    store = NexusStore(ephemeral=True)
    store.save_identity(AgentIdentity(name="ghost"))
    assert store.load_identities()["ghost"].name == "ghost"
    store.close()

    assert not any(tmp_path.iterdir()), "aucun fichier ne doit être créé"
    print("✓ Le mode éphémère n'écrit rien")


def test_database_file_is_owner_only(db):
    """La base contient les identités et l'audit : elle ne doit pas être lisible par tous."""
    NexusStore(path=db).close()
    mode = db.stat().st_mode
    assert not mode & stat.S_IRWXG
    assert not mode & stat.S_IRWXO
    print("✓ Base créée en 0600")


def test_deleted_identity_does_not_come_back(db):
    """Une identité supprimée ne doit pas réapparaître au redémarrage."""
    with NexusStore(path=db) as store:
        store.save_identity(AgentIdentity(name="temp", org_id="acme"))
        store.delete_identity("acme/temp")

    with NexusStore(path=db) as store:
        assert store.load_identities() == {}
    print("✓ Suppression persistée")


def test_default_path_follows_nexus_home(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXUS_HOME", str(tmp_path / "custom"))
    assert default_state_path() == tmp_path / "custom" / "hub_state.db"
    print("✓ NEXUS_HOME respecté")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
