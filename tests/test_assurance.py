"""InterMesh Assurance : interception, classification, décision, preuve.

Ce que ces tests cherchent à établir est précis : une action autonome
critique peut être interceptée, contrôlée, et transformée en preuve qu'un
tiers vérifie sans faire confiance à l'émetteur.

Les tests de falsification sont les plus importants du fichier. Une preuve
qui survit à une modification n'est pas une preuve, c'est un journal.
"""

import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from intermesh.assurance import (
    ActionEvidence,
    AssuranceProxy,
    EvidenceStore,
    Policy,
    PolicyError,
    RiskLevel,
    make_proxy_server,
    verify_chain,
    verify_evidence,
)
from intermesh.signing import derive_signing_key

KEY = derive_signing_key("cle-de-test-assurance")
AUTRE = derive_signing_key("une-cle-qui-n-est-pas-la-bonne")
NODE = shutil.which("node")

POLICY = {
    "name": "test-v1",
    "evidence_threshold": "R2",
    "rules": [
        {"name": "destructive", "match": {"path_contains": "/delete"},
         "risk": "R5", "decision": "block", "reason": "irréversible"},
        {"name": "transfer", "match": {"path_contains": "/transfer"},
         "risk": "R4", "decision": "approval", "reason": "validation humaine"},
        {"name": "write", "match": {"method": "POST"},
         "risk": "R2", "decision": "allow"},
        {"name": "read", "match": {"method": "GET"},
         "risk": "R0", "decision": "allow"},
    ],
    "default": {"decision": "block", "risk": "R3"},
}


class _API(BaseHTTPRequestHandler):
    def do_GET(self): self._ok()      # noqa: E704, N802
    def do_POST(self): self._ok()     # noqa: E704, N802

    def _ok(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stack(tmp_path):
    """API cible + proxy d'assurance, sur des ports éphémères."""
    api = ThreadingHTTPServer(("127.0.0.1", 0), _API)
    threading.Thread(target=api.serve_forever, daemon=True).start()

    store = EvidenceStore(tmp_path / "evidence.jsonl")
    proxy = AssuranceProxy(Policy.from_dict(POLICY), KEY, store,
                           agent_id="bot", organization_id="acme")
    guard = make_proxy_server(proxy, port=0, quiet=True)
    threading.Thread(target=guard.serve_forever, daemon=True).start()

    ctx = {
        "base": f"http://127.0.0.1:{api.server_address[1]}",
        "proxies": {"http": f"http://127.0.0.1:{guard.server_address[1]}"},
        "store": store, "path": tmp_path / "evidence.jsonl",
    }
    try:
        yield ctx
    finally:
        guard.shutdown(); guard.server_close()
        api.shutdown(); api.server_close()


def _preuves(ctx):
    return [json.loads(l) for l in
            ctx["path"].read_text(encoding="utf-8").splitlines() if l.strip()]


# ----------------------------------------------------------------------
# 1-3 : classification et décision
# ----------------------------------------------------------------------

def test_une_lecture_anodine_passe_sans_preuve(stack):
    """R0 sous le seuil : exécutée, et volontairement non tracée."""
    r = requests.get(f"{stack['base']}/api/items", proxies=stack["proxies"], timeout=10)

    assert r.status_code == 200
    assert r.headers["X-InterMesh-Risk"] == "R0"
    assert not stack["path"].exists(), "R0 ne doit pas produire de preuve"


def test_une_action_r5_est_bloquee_et_prouvee(stack):
    r = requests.post(f"{stack['base']}/api/delete/db", json={"x": 1},
                      proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "blocked"
    assert body["risk"] == "R5"
    assert body["rule"] == "destructive"
    assert body["evidence_id"]

    preuve = _preuves(stack)[0]
    assert preuve["authorization"]["decision"] == "block"
    assert preuve["execution"]["status"] == "blocked"


def test_une_action_r4_demande_une_approbation(stack):
    r = requests.post(f"{stack['base']}/api/transfer", json={"amount": 5000},
                      proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    assert r.json()["error"] == "approval_required"
    assert _preuves(stack)[0]["execution"]["status"] == "pending_approval"


def test_une_action_autorisee_atteint_vraiment_l_api(stack):
    """La preuve ne doit pas remplacer l'exécution : l'appel doit aboutir."""
    r = requests.post(f"{stack['base']}/api/items", json={"name": "w"},
                      proxies=stack["proxies"], timeout=10)

    assert r.status_code == 200
    assert r.json()["ok"] is True
    preuve = _preuves(stack)[0]
    assert preuve["execution"]["status"] == "executed"
    assert preuve["execution"]["response_status"] == 200


def test_une_action_hors_politique_est_refusee(stack):
    """Le défaut protège ce que personne n'a prévu."""
    r = requests.request("PUT", f"{stack['base']}/api/inconnu",
                         proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    assert r.json()["rule"] == "default"


# ----------------------------------------------------------------------
# 4-6, 10-11 : la preuve elle-même
# ----------------------------------------------------------------------

def _evidence(decision="block", risk=RiskLevel.R5):
    return ActionEvidence.build(
        agent_id="bot", organization_id="acme", method="POST",
        target="http://x/api/delete", risk=risk, decision=decision,
        policy="test-v1@abc", rule="destructive", status="blocked").sign(KEY)


def test_une_preuve_intacte_est_valide():
    rapport = verify_evidence(_evidence())

    assert rapport.valid
    assert rapport.schema_ok and rapport.integrity_ok and rapport.signature_ok
    assert rapport.decision == "block"


@pytest.mark.parametrize("chemin,valeur", [
    (("authorization", "decision"), "allow"),
    (("risk", "level"), "R0"),
    (("action", "target"), "http://ailleurs/"),
    (("agent_id",), "quelqu-un-d-autre"),
])
def test_toute_modification_apres_coup_est_detectee(chemin, valeur):
    """Le test essentiel. Sans lui, ce produit n'est qu'un journal."""
    preuve = _evidence()
    cible = preuve
    for cle in chemin[:-1]:
        cible = cible[cle]
    cible[chemin[-1]] = valeur

    rapport = verify_evidence(preuve)

    assert not rapport.valid
    assert not rapport.integrity_ok
    assert any("modifiée" in e for e in rapport.errors)


def test_une_signature_etrangere_est_refusee():
    """Non-répudiation : la preuve désigne une clé, et une seule."""
    preuve = _evidence()

    assert not verify_evidence(preuve, trusted_key=AUTRE.public_key()).signature_ok
    assert verify_evidence(preuve, trusted_key=KEY.public_key()).valid


def test_une_signature_remplacee_ne_sauve_pas_une_preuve_modifiee():
    """L'attaque évidente : modifier, puis resigner avec sa propre clé."""
    preuve = _evidence()
    preuve["authorization"]["decision"] = "allow"
    resigne = ActionEvidence(
        agent_id=preuve["agent_id"], organization_id=preuve["organization_id"],
        action=preuve["action"], risk=preuve["risk"],
        authorization=preuve["authorization"], execution=preuve["execution"],
        action_id=preuve["action_id"], timestamp=preuve["timestamp"],
        prev_hash=preuve["prev_hash"]).sign(AUTRE)

    # Cohérent avec sa propre clé — mais pas avec celle de l'émetteur annoncé.
    assert verify_evidence(resigne).valid
    assert not verify_evidence(resigne, trusted_key=KEY.public_key()).valid


def test_le_corps_de_la_requete_n_est_jamais_stocke(stack):
    """Une preuve qui contiendrait le virement serait la fuite qu'elle documente."""
    requests.post(f"{stack['base']}/api/transfer",
                  json={"iban": "FR7630006000011234567890189", "amount": 5000},
                  proxies=stack["proxies"], timeout=10)

    brut = stack["path"].read_text(encoding="utf-8")
    assert "FR7630006000011234567890189" not in brut
    assert len(json.loads(brut)["action"]["payload_hash"]) == 64


def test_le_chainage_resiste_a_des_ecritures_simultanees(tmp_path):
    """
    Régression : `prev_hash` était lu hors du verrou, puis la preuve
    signée, puis écrite. Deux requêtes simultanées lisaient la même
    empreinte précédente et produisaient deux preuves de même `prev_hash`.
    Le chaînage cassait dès qu'un agent émettait en parallèle — c'est-à-
    dire dans le cas normal, pas dans un cas limite.
    """
    from intermesh.assurance import AssuranceProxy, EvidenceStore
    from intermesh.assurance.policy import Verdict

    store = EvidenceStore(tmp_path / "e.jsonl")
    proxy = AssuranceProxy(Policy.from_dict(POLICY), KEY, store)
    verdict = Verdict("block", RiskLevel.R5, "destructive")

    def ecrire(i):
        proxy.record(method="POST", url=f"http://h/delete/{i}",
                     verdict=verdict, status="blocked")

    fils = [threading.Thread(target=ecrire, args=(i,)) for i in range(30)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()

    preuves = [json.loads(l) for l in
               (tmp_path / "e.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(preuves) == 30
    assert verify_chain(preuves).valid


def test_la_chaine_detecte_une_preuve_retiree(stack):
    for chemin in ("/api/delete/a", "/api/transfer", "/api/delete/b"):
        requests.post(f"{stack['base']}{chemin}", json={},
                      proxies=stack["proxies"], timeout=10)

    preuves = _preuves(stack)
    assert verify_chain(preuves).valid

    ampute = [preuves[0], preuves[2]]
    rapport = verify_chain(ampute)
    assert not rapport.valid
    assert any("chaînage rompu" in e for e in rapport.errors)


# ----------------------------------------------------------------------
# 7 : politique invalide
# ----------------------------------------------------------------------

@pytest.mark.parametrize("raw,motif", [
    ({"rules": []}, "au moins une règle"),
    ({"rules": [{"name": "x", "match": {}, "risk": "R1"}]}, "aucun critère"),
    ({"rules": [{"name": "x", "match": {"method": "GET"}, "decision": "peut-etre"}]},
     "inconnue"),
    ({"rules": [{"name": "x", "match": {"method": "GET"}, "risk": "R9"}]},
     "illisible"),
    ({"rules": [{"name": "x", "match": {"path_regex": "[("}, "risk": "R1"}]},
     "régulière invalide"),
    ({"rules": [{"name": "d", "match": {"method": "GET"}, "risk": "R1"},
                {"name": "d", "match": {"method": "POST"}, "risk": "R1"}]},
     "portent le nom"),
])
def test_une_politique_invalide_est_refusee_au_chargement(raw, motif):
    with pytest.raises(PolicyError, match=motif):
        Policy.from_dict(raw)


def test_la_politique_est_identifiee_par_son_contenu():
    """« policy: finance-v1 » ne prouve rien si le fichier a changé depuis."""
    a = Policy.from_dict(POLICY)
    modifiee = json.loads(json.dumps(POLICY))
    modifiee["rules"][0]["decision"] = "allow"
    b = Policy.from_dict(modifiee)

    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == Policy.from_dict(POLICY).fingerprint()


def test_la_premiere_regle_qui_correspond_gagne():
    policy = Policy.from_dict(POLICY)
    verdict = policy.evaluate("POST", "http://h/api/delete/x")

    assert verdict.rule == "destructive", "l'ordre du fichier fait loi"


# ----------------------------------------------------------------------
# 8-9, 12-13 : le proxy en conditions réelles
# ----------------------------------------------------------------------

def test_une_requete_directe_explique_au_lieu_de_deviner(stack):
    port = stack["proxies"]["http"].rsplit(":", 1)[1]
    r = requests.get(f"http://127.0.0.1:{port}/pas-un-proxy", timeout=10)

    assert r.status_code == 400
    assert r.json()["error"] == "not_a_proxy_request"


def test_le_connect_https_note_qu_il_ne_voit_pas_le_chemin(stack):
    """Honnêteté du dispositif : en TLS, la preuve ne porte que sur l'hôte."""
    store = stack["store"]
    proxy = AssuranceProxy(Policy.from_dict(POLICY), KEY, store)
    verdict = proxy.assess("CONNECT", "https://api.exemple.com")
    record = proxy.record(method="CONNECT", url="https://api.exemple.com",
                          verdict=verdict, status="tunnelled", tls_opaque=True)

    assert record["execution"]["tls_opaque"] is True


@pytest.mark.skipif(NODE is None, reason="Node.js absent de la machine")
def test_un_client_node_sans_sdk_est_intercepte(stack, tmp_path):
    """
    La promesse multi-langages : zéro ligne d'InterMesh côté client.
    Node n'a ici aucune dépendance — juste `http.request` vers le proxy.
    """
    port = stack["proxies"]["http"].rsplit(":", 1)[1]
    script = tmp_path / "agent.js"
    script.write_text(f"""
const http = require('http');
const req = http.request({{
  host: '127.0.0.1', port: {port}, method: 'POST',
  path: '{stack["base"]}/api/delete/tout',
  headers: {{'Content-Type': 'application/json'}},
}}, res => {{
  let data = '';
  res.on('data', c => data += c);
  res.on('end', () => console.log(JSON.stringify({{status: res.statusCode, body: JSON.parse(data)}})));
}});
req.end(JSON.stringify({{}}));
""", encoding="utf-8")

    sortie = subprocess.run([NODE, str(script)], capture_output=True,
                            text=True, timeout=30)
    assert sortie.returncode == 0, sortie.stderr

    resultat = json.loads(sortie.stdout)
    assert resultat["status"] == 403
    assert resultat["body"]["risk"] == "R5"
    assert _preuves(stack)[0]["action"]["method"] == "POST"


def test_verify_en_ligne_de_commande_tranche_dans_les_deux_sens(tmp_path):
    """`intermesh verify` doit rendre un code de sortie exploitable."""
    bonne = tmp_path / "ok.json"
    bonne.write_text(json.dumps(_evidence()), encoding="utf-8")

    fausse = tmp_path / "ko.json"
    altere = _evidence()
    altere["risk"]["level"] = "R0"
    fausse.write_text(json.dumps(altere), encoding="utf-8")

    def verifier(chemin):
        return subprocess.run([sys.executable, "-m", "intermesh.cli", "verify",
                               str(chemin)], capture_output=True, text=True,
                              timeout=60)

    assert verifier(bonne).returncode == 0
    echec = verifier(fausse)
    assert echec.returncode == 1
    assert "INVALID" in echec.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
