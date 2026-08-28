"""
Instantanés du Hub : capture, chiffrement au repos, restauration.

L'invariant le plus important testé ici n'est pas « la restauration
remet bien l'état » — c'est que la restauration ne peut PAS tronquer le
journal d'audit. Un instantané qui pourrait remplacer la chaîne serait
un outil d'effacement de traces déguisé en outil d'exploitation.
"""

import asyncio
import json
import os
import stat

import pytest

from intermesh import snapshot
from intermesh.admin import AdminContext, AdminError
from intermesh.admin import execute as admin_execute
from intermesh.apikeys import ApiKeyStore
from intermesh.audit import ImmutableAuditLog
from intermesh.escrow import EscrowManager
from intermesh.guardrails import AsimovGuardrailEngine, GuardrailPolicy
from intermesh.identity import AgentIdentity
from intermesh.snapshot import SnapshotError
from intermesh.store import InterMeshStore
from intermesh.task import InterMeshTask, TaskStatus


# ----------------------------------------------------------------------
# Fixtures : un Hub miniature, sans serveur
# ----------------------------------------------------------------------

def _identity(name: str, org: str = "acme", caps=None) -> AgentIdentity:
    return AgentIdentity(name=name, org_id=org, capabilities=caps or ["translate"],
                         roles=["standard"])


def _task(title: str, assignee: str) -> InterMeshTask:
    return InterMeshTask(title=title, orchestrator="acme/boss", assignee=assignee,
                     input_data={"text": "bonjour"})


class _Hub:
    """L'état qu'un Hub réel détient, sans les WebSockets."""

    def __init__(self, tmp_path, *, keys_mutable=True):
        self.identity_registry = {}
        self.task_registry = {}
        self.agents = {}
        self.store = InterMeshStore(path=str(tmp_path / "state.db"))
        self.audit_log = ImmutableAuditLog(entries=self.store.load_audit(),
                                           on_append=self.store.append_audit)
        self.asimov_engine = AsimovGuardrailEngine()
        self.escrow_manager = EscrowManager()
        self.snapshot_dir = str(tmp_path / "snapshots")

        if keys_mutable:
            self.api_keys = ApiKeyStore({}, source="test", path=tmp_path / "api_keys.json")
        else:
            # Clés injectées par l'environnement : lecture seule.
            self.api_keys = ApiKeyStore({"nx_env_key": {"org_id": "acme", "roles": ["admin"]}},
                                        source="variable INTERMESH_API_KEYS")

    def ctx(self, *, scoped=False, caller_org="acme") -> AdminContext:
        return AdminContext(
            agents=self.agents, identity_registry=self.identity_registry,
            task_registry=self.task_registry, audit_log=self.audit_log,
            api_keys=self.api_keys, peered_hubs={}, store=self.store, my_org="acme",
            remember_task=lambda t: None, send_to_agent=lambda t: None,
            caller_org=caller_org, scoped=scoped, asimov_engine=self.asimov_engine,
            escrow_manager=self.escrow_manager, snapshot_dir=self.snapshot_dir,
        )

    def admin(self, command, **params):
        return asyncio.run(admin_execute(command, params, self.ctx()))


@pytest.fixture
def hub(tmp_path):
    h = _Hub(tmp_path)
    h.identity_registry["acme/alpha"] = _identity("alpha")
    h.identity_registry["acme/beta"] = _identity("beta", caps=["summarize"])
    t = _task("Traduire", "acme/alpha")
    h.task_registry[t.task_id] = t
    h.audit_log.log("AGENT_REGISTERED", "acme/alpha", "hub", {})
    yield h
    h.store.close()


# ----------------------------------------------------------------------
# Aller-retour
# ----------------------------------------------------------------------

def test_capture_then_restore_roundtrip(hub):
    hub.escrow_manager.ledger.grant("acme", 500.0)
    hub.asimov_engine.set_org_policy("acme", GuardrailPolicy(name="strict", max_cost_per_task=7.5))
    hub.admin("snapshot.create", name="baseline")

    # Dérive : un agent part, un autre arrive, la policy change.
    del hub.identity_registry["acme/beta"]
    hub.identity_registry["acme/gamma"] = _identity("gamma")
    hub.task_registry.clear()
    hub.asimov_engine.set_org_policy("acme", GuardrailPolicy(name="laxe", max_cost_per_task=999.0))
    hub.escrow_manager.ledger.grant("acme", 1000.0)

    result = hub.admin("snapshot.restore", name="baseline")

    assert set(hub.identity_registry) == {"acme/alpha", "acme/beta"}
    assert "acme/gamma" not in hub.identity_registry
    assert len(hub.task_registry) == 1
    assert hub.asimov_engine.get_policy("acme").max_cost_per_task == 7.5
    assert hub.escrow_manager.ledger.balance("acme") == 500.0
    assert result["restored_from"] == "baseline"
    print("✓ Identités, tâches, policies et soldes restaurés")


def test_restore_rewrites_the_persistent_store(hub, tmp_path):
    """Sans réécriture du magasin, un redémarrage annulerait la restauration."""
    hub.store.save_identity(hub.identity_registry["acme/alpha"])
    hub.admin("snapshot.create", name="avant")

    hub.identity_registry["acme/intrus"] = _identity("intrus")
    hub.store.save_identity(hub.identity_registry["acme/intrus"])
    assert "acme/intrus" in hub.store.load_identities()

    hub.admin("snapshot.restore", name="avant")
    assert "acme/intrus" not in hub.store.load_identities()
    print("✓ Le magasin persistant suit la restauration")


def test_task_status_survives_the_roundtrip(hub):
    task = next(iter(hub.task_registry.values()))
    task.update_status(TaskStatus.COMPLETED, output_data={"translated": "hello"})
    hub.admin("snapshot.create", name="terminee")

    hub.task_registry.clear()
    hub.admin("snapshot.restore", name="terminee")

    restored = next(iter(hub.task_registry.values()))
    assert restored.status == TaskStatus.COMPLETED
    assert restored.output_data == {"translated": "hello"}
    print("✓ Statut et sortie de tâche préservés")


# ----------------------------------------------------------------------
# L'invariant central : le journal d'audit n'est jamais tronqué
# ----------------------------------------------------------------------

def test_restore_never_truncates_the_audit_chain(hub):
    hub.admin("snapshot.create", name="tot")
    length_at_snapshot = len(hub.audit_log.chain)

    # Des évènements postérieurs à l'instantané : exactement ce qu'une
    # restauration malveillante chercherait à faire disparaître.
    hub.audit_log.log("ASIMOV_GUARDRAIL_VIOLATION", "acme/alpha", None, {"rule": "RM_RF"})
    hub.audit_log.log("ADMIN_ACTION", "acme/console", None, {"command": "apikey.create"})
    assert len(hub.audit_log.chain) > length_at_snapshot

    hub.admin("snapshot.restore", name="tot")

    assert len(hub.audit_log.chain) > length_at_snapshot, "la chaîne a été tronquée"
    assert hub.audit_log.verify_integrity()
    events = [e.event_type for e in hub.audit_log.chain]
    assert "ASIMOV_GUARDRAIL_VIOLATION" in events
    assert events[-1] == "SNAPSHOT_RESTORED"
    print("✓ Le journal d'audit survit à la restauration, et l'enregistre")


def test_snapshot_records_the_audit_head_for_reference(hub):
    manifest = hub.admin("snapshot.create", name="repere")
    head = manifest["audit_head"]
    assert head["index"] == hub.audit_log.chain[-1].index
    assert head["hash"] == hub.audit_log.chain[-1].hash
    print("✓ La tête de chaîne est notée comme repère forensique")


# ----------------------------------------------------------------------
# Filet de sécurité
# ----------------------------------------------------------------------

def test_restore_takes_a_safety_snapshot_first(hub):
    hub.admin("snapshot.create", name="cible")
    hub.identity_registry["acme/precieux"] = _identity("precieux")

    result = hub.admin("snapshot.restore", name="cible")
    safety = result["safety_snapshot"]
    assert safety and safety.startswith("pre-restore-")
    assert "acme/precieux" not in hub.identity_registry

    # Une mauvaise restauration reste réversible.
    hub.admin("snapshot.restore", name=safety, safety_snapshot=False)
    assert "acme/precieux" in hub.identity_registry
    print("✓ Le filet de sécurité rend la restauration elle-même réversible")


def test_safety_snapshot_can_be_disabled(hub):
    hub.admin("snapshot.create", name="c")
    result = hub.admin("snapshot.restore", name="c", safety_snapshot=False)
    assert result["safety_snapshot"] is None
    print("✓ Filet de sécurité désactivable explicitement")


# ----------------------------------------------------------------------
# Chiffrement au repos
# ----------------------------------------------------------------------

def test_encrypted_snapshot_hides_state_but_keeps_manifest_readable(hub):
    hub.admin("snapshot.create", name="chiffre", passphrase="correct horse battery")

    raw = json.loads((snapshot.path_for("chiffre", hub.snapshot_dir)).read_text())
    assert "state" not in raw
    assert "encrypted_state" in raw
    assert "alpha" not in json.dumps(raw["encrypted_state"])

    # L'inventaire reste possible sans détenir la passphrase.
    listing = hub.admin("snapshot.list")
    entry = next(s for s in listing["snapshots"] if s["name"] == "chiffre")
    assert entry["encrypted"] is True
    assert entry["counts"]["identities"] == 2
    print("✓ État chiffré, manifeste toujours inventoriable")


def test_wrong_passphrase_is_refused(hub):
    hub.admin("snapshot.create", name="secret", passphrase="bonne")
    with pytest.raises(AdminError, match="passphrase incorrecte|altéré"):
        hub.admin("snapshot.restore", name="secret", passphrase="mauvaise")
    print("✓ Passphrase incorrecte refusée")


def test_encrypted_snapshot_requires_a_passphrase(hub):
    hub.admin("snapshot.create", name="secret", passphrase="bonne")
    with pytest.raises(AdminError, match="chiffré"):
        hub.admin("snapshot.restore", name="secret")
    print("✓ Restauration sans passphrase refusée")


def test_tampered_ciphertext_is_detected(hub, tmp_path):
    """AES-GCM est authentifié : un octet modifié doit faire échouer, pas produire du faux."""
    hub.admin("snapshot.create", name="scelle", passphrase="pass")
    target = snapshot.path_for("scelle", hub.snapshot_dir)
    doc = json.loads(target.read_text())
    ct = doc["encrypted_state"]["ciphertext"]
    doc["encrypted_state"]["ciphertext"] = ("B" if ct[0] == "A" else "A") + ct[1:]
    target.write_text(json.dumps(doc))

    with pytest.raises(AdminError, match="passphrase incorrecte|altéré"):
        hub.admin("snapshot.restore", name="scelle", passphrase="pass")
    print("✓ Altération du chiffré détectée")


def test_plaintext_snapshot_carries_a_warning(hub):
    manifest = hub.admin("snapshot.create", name="clair")
    assert "warning" in manifest
    assert "empreintes de clés d'API" in manifest["warning"]
    assert "warning" not in hub.admin("snapshot.create", name="couvert", passphrase="p")
    print("✓ L'instantané non chiffré s'annonce comme tel")


# ----------------------------------------------------------------------
# Confidentialité sur disque
# ----------------------------------------------------------------------

def test_snapshot_file_and_directory_are_private(hub):
    hub.admin("snapshot.create", name="prive")
    target = snapshot.path_for("prive", hub.snapshot_dir)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not stat.S_IMODE(target.parent.stat().st_mode) & (stat.S_IRWXG | stat.S_IRWXO)
    print("✓ Fichier 0600 dans un dossier interdit aux autres utilisateurs")


def test_no_temporary_file_is_left_behind(hub):
    hub.admin("snapshot.create", name="atomique")
    leftovers = list((snapshot.path_for("atomique", hub.snapshot_dir)).parent.glob("*.tmp"))
    assert leftovers == []
    print("✓ Écriture atomique, aucun .tmp résiduel")


# ----------------------------------------------------------------------
# Validation des noms
# ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "../../etc/passwd", "a/b", "", "avec espace", "x" * 65, ".cache", "nom;rm -rf",
])
def test_dangerous_snapshot_names_are_refused(hub, bad):
    with pytest.raises((AdminError, SnapshotError)):
        hub.admin("snapshot.create", name=bad)
    print(f"✓ Nom refusé : {bad!r}")


def test_unknown_snapshot_is_a_clear_error(hub):
    with pytest.raises(AdminError, match="introuvable"):
        hub.admin("snapshot.restore", name="jamais-cree")
    print("✓ Instantané inconnu signalé clairement")


# ----------------------------------------------------------------------
# Cloisonnement : un instantané est hub-wide
# ----------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "snapshot.create", "snapshot.list", "snapshot.restore", "snapshot.delete",
])
def test_org_admin_cannot_touch_snapshots(hub, command):
    """
    Un instantané contient le registre et les clés de TOUTES les
    organisations : le créer serait une exfiltration, le restaurer une
    écrasement des voisins.
    """
    ctx = hub.ctx(scoped=True, caller_org="acme")
    with pytest.raises(AdminError, match="admin"):
        asyncio.run(admin_execute(command, {"name": "x"}, ctx))
    print(f"✓ '{command}' refusé à un org_admin")


# ----------------------------------------------------------------------
# Restauration partielle : ce qui est ignoré doit se voir
# ----------------------------------------------------------------------

def test_readonly_api_keys_are_skipped_not_crashed(tmp_path):
    hub = _Hub(tmp_path, keys_mutable=False)
    hub.identity_registry["acme/alpha"] = _identity("alpha")
    try:
        hub.admin("snapshot.create", name="ro")
        result = hub.admin("snapshot.restore", name="ro")

        assert "api_keys" not in result["restored"]
        skipped = [s["what"] for s in result["skipped"]]
        assert "api_keys" in skipped
        # Le reste a bien été restauré : l'échec est partiel, pas total.
        assert "identities" in result["restored"]
        print("✓ Clés en lecture seule ignorées, restauration poursuivie et signalée")
    finally:
        hub.store.close()


def test_online_agents_absent_from_the_snapshot_are_reported(hub):
    hub.admin("snapshot.create", name="avant-arrivee")

    # Un agent rejoint le réseau APRÈS l'instantané, puis on restaure :
    # sa socket reste vivante alors que le registre l'a oublié.
    hub.identity_registry["acme/tardif"] = _identity("tardif")
    hub.agents["acme/tardif"] = object()

    result = hub.admin("snapshot.restore", name="avant-arrivee")
    assert result["orphaned_online"] == ["acme/tardif"]
    print("✓ Agents connectés orphelins signalés à l'exploitant")


# ----------------------------------------------------------------------
# Inventaire et suppression
# ----------------------------------------------------------------------

def test_list_is_sorted_most_recent_first(hub):
    for name in ("un", "deux", "trois"):
        hub.admin("snapshot.create", name=name)
    names = [s["name"] for s in hub.admin("snapshot.list")["snapshots"]]
    assert names[0] == "trois"
    assert set(names) == {"un", "deux", "trois"}
    print("✓ Inventaire trié du plus récent au plus ancien")


def test_list_survives_a_corrupted_file(hub):
    hub.admin("snapshot.create", name="sain")
    corrupted = snapshot.path_for("corrompu", hub.snapshot_dir)
    corrupted.write_text("{ pas du json")

    names = [s["name"] for s in hub.admin("snapshot.list")["snapshots"]]
    assert names == ["sain"]
    print("✓ Un fichier corrompu ne casse pas l'inventaire")


def test_delete_removes_the_file(hub):
    hub.admin("snapshot.create", name="jetable")
    hub.admin("snapshot.delete", name="jetable")
    assert not snapshot.path_for("jetable", hub.snapshot_dir).exists()
    with pytest.raises(AdminError, match="inconnu"):
        hub.admin("snapshot.delete", name="jetable")
    print("✓ Suppression effective, seconde suppression signalée")


def test_overwrite_can_be_refused(hub):
    hub.admin("snapshot.create", name="unique")
    with pytest.raises(AdminError, match="existe déjà"):
        hub.admin("snapshot.create", name="unique", overwrite=False)
    print("✓ Écrasement refusable")


# ----------------------------------------------------------------------
# Composants : aller-retour unitaire
# ----------------------------------------------------------------------

def test_escrow_holds_survive_the_roundtrip():
    manager = EscrowManager()
    manager.ledger.grant("acme", 100.0)
    manager.create_hold("t-1", "acme", "globex", 40.0)

    restored = EscrowManager()
    restored.import_state(manager.export_state())

    hold = restored.get("t-1")
    assert hold.amount == 40.0 and hold.payee_org == "globex"
    assert restored.ledger.balance("acme") == 60.0
    # Le séquestre reste résoluble après restauration.
    restored.release("t-1")
    assert restored.ledger.balance("globex") == 40.0
    print("✓ Séquestres et soldes reconstruits, et toujours résolubles")


def test_guardrail_patterns_recompile_after_import():
    """Le cache de motifs est indexé par id() : un import doit l'invalider."""
    engine = AsimovGuardrailEngine()
    engine.inspect_payload("a", "SELECT 1")          # amorce le cache

    engine.import_policies({
        "default": {**GuardrailPolicy().__dict__, "blocked_patterns": [r"INTERDIT"]},
        "orgs": {},
    })
    engine.inspect_payload("a", "rm -rf /")           # l'ancien motif ne s'applique plus
    with pytest.raises(Exception, match="INTERDIT"):
        engine.inspect_payload("b", "commande INTERDITE")
    print("✓ Les motifs sont recompilés après import de policy")


def test_volatile_counters_are_not_exported():
    engine = AsimovGuardrailEngine()
    exported = engine.export_policies()
    assert set(exported) == {"default", "orgs"}
    print("✓ Compteurs volatils exclus de l'instantané")
