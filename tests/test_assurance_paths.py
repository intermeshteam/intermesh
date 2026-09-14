"""Les trois chemins fondamentaux, et le modèle de sécurité réel.

ALLOW, BLOCK, APPROVAL — puis la question qui décide de la crédibilité du
produit : **comment un agent contourne-t-il InterMesh ?**

Les tests de contournement ne cherchent pas à prouver que le proxy est
inviolable. Ils établissent ce qu'il couvre et ce qu'il ne couvre pas,
pour que `docs/SECURITY-MODEL.md` dise la vérité plutôt qu'une intention.
"""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from intermesh.assurance import AssuranceProxy, EvidenceStore, Policy, make_proxy_server
from intermesh.assurance.approval import HEADER as APPROVAL_HEADER
from intermesh.assurance.approval import ApprovalError, ApprovalStore
from intermesh.signing import derive_signing_key

POLICY = {
    "name": "paths-v1",
    "evidence_threshold": "R2",
    "rules": [
        {"name": "destructive", "match": {"path_contains": "/delete"},
         "risk": "R5", "decision": "block", "reason": "irréversible"},
        {"name": "transfer", "match": {"path_contains": "/transfer"},
         "risk": "R4", "decision": "approval", "reason": "validation humaine"},
        {"name": "write", "match": {"method": "POST"}, "risk": "R2",
         "decision": "allow"},
        {"name": "read", "match": {"method": "GET"}, "risk": "R0",
         "decision": "allow"},
    ],
    "default": {"decision": "block", "risk": "R3"},
}


class _API(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    touches = []

    def do_GET(self): self._ok()      # noqa: E704, N802
    def do_POST(self): self._ok()     # noqa: E704, N802

    def _ok(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        # Enregistrer ce que l'API a réellement reçu : c'est la seule façon
        # de vérifier qu'une action bloquée n'est vraiment pas partie.
        _API.touches.append(f"{self.command} {self.path}")
        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stack(tmp_path):
    _API.touches = []
    api = ThreadingHTTPServer(("127.0.0.1", 0), _API)
    api.daemon_threads = True
    threading.Thread(target=api.serve_forever, daemon=True).start()

    approvals = ApprovalStore(tmp_path / "approvals.json")
    proxy = AssuranceProxy(Policy.from_dict(POLICY),
                           derive_signing_key("cle-de-test-chemins"),
                           EvidenceStore(tmp_path / "evidence.jsonl"),
                           agent_id="bot", organization_id="acme",
                           approvals=approvals)
    guard = make_proxy_server(proxy, port=0, quiet=True)
    guard.daemon_threads = True
    threading.Thread(target=guard.serve_forever, daemon=True).start()

    ctx = {
        "api_port": api.server_address[1],
        "base": f"http://127.0.0.1:{api.server_address[1]}",
        "proxy_port": guard.server_address[1],
        "proxies": {"http": f"http://127.0.0.1:{guard.server_address[1]}"},
        "approvals": approvals, "path": tmp_path / "evidence.jsonl",
        "touches": _API.touches,
    }
    try:
        yield ctx
    finally:
        guard.shutdown(); guard.server_close()
        api.shutdown(); api.server_close()


def _preuves(ctx):
    if not ctx["path"].exists():
        return []
    return [json.loads(l) for l in
            ctx["path"].read_text(encoding="utf-8").splitlines() if l.strip()]


# ----------------------------------------------------------------------
# Les trois chemins
# ----------------------------------------------------------------------

def test_chemin_allow_execute_et_prouve(stack):
    r = requests.get(f"{stack['base']}/safe-resource", proxies=stack["proxies"],
                     timeout=10)

    assert r.status_code == 200
    assert "GET /safe-resource" in stack["touches"], "l'appel doit atteindre l'API"
    assert _preuves(stack) == [], "R0 est sous le seuil : pas de preuve"


def test_chemin_block_n_atteint_jamais_l_api(stack):
    """Le test qui compte : une action bloquée ne doit pas partir."""
    r = requests.post(f"{stack['base']}/delete-production-resource", json={},
                      proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    assert r.json()["risk"] == "R5"
    assert stack["touches"] == [], "l'API ne doit rien avoir reçu"

    preuve = _preuves(stack)[0]
    assert preuve["authorization"]["decision"] == "block"
    assert preuve["execution"]["status"] == "blocked"


def test_chemin_approval_bloque_puis_passe_apres_validation(stack):
    cible = f"{stack['base']}/transfer"

    premier = requests.post(cible, json={"amount": 5000},
                            proxies=stack["proxies"], timeout=10)
    assert premier.status_code == 403
    assert premier.json()["error"] == "approval_required"
    assert stack["touches"] == []

    action_id = premier.json()["evidence_id"]
    stack["approvals"].grant(action_id, "POST", cible, approved_by="alice")

    second = requests.post(cible, json={"amount": 5000},
                           proxies=stack["proxies"], timeout=10,
                           headers={APPROVAL_HEADER: action_id})

    assert second.status_code == 200
    assert "POST /transfer" in stack["touches"]

    executee = _preuves(stack)[-1]
    assert executee["execution"]["status"] == "executed"
    assert executee["authorization"]["approval_id"] == action_id
    assert executee["authorization"]["approved_by"] == "alice"


def test_une_approbation_ne_sert_qu_une_fois(stack):
    cible = f"{stack['base']}/transfer"
    premier = requests.post(cible, json={}, proxies=stack["proxies"], timeout=10)
    action_id = premier.json()["evidence_id"]
    stack["approvals"].grant(action_id, "POST", cible, approved_by="alice")

    entete = {APPROVAL_HEADER: action_id}
    assert requests.post(cible, json={}, proxies=stack["proxies"],
                         headers=entete, timeout=10).status_code == 200

    rejeu = requests.post(cible, json={}, proxies=stack["proxies"],
                          headers=entete, timeout=10)
    assert rejeu.status_code == 403
    assert "déjà utilisée" in rejeu.json()["detail"]


def test_une_approbation_ne_sert_pas_pour_une_autre_action(stack):
    """La tentative évidente : faire valider un virement, rejouer sur /delete."""
    cible = f"{stack['base']}/transfer"
    premier = requests.post(cible, json={}, proxies=stack["proxies"], timeout=10)
    action_id = premier.json()["evidence_id"]
    stack["approvals"].grant(action_id, "POST", cible, approved_by="alice")

    detourne = requests.post(f"{stack['base']}/delete-all", json={},
                             proxies=stack["proxies"], timeout=10,
                             headers={APPROVAL_HEADER: action_id})

    assert detourne.status_code == 403
    assert stack["touches"] == []


def test_un_jeton_d_approbation_invente_est_refuse(stack):
    r = requests.post(f"{stack['base']}/transfer", json={},
                      proxies=stack["proxies"], timeout=10,
                      headers={APPROVAL_HEADER: "je-l-ai-inventé"})

    assert r.status_code == 403
    assert r.json()["error"] == "approval_invalid"
    assert stack["touches"] == []
    assert _preuves(stack)[-1]["execution"]["status"] == "approval_rejected"


def test_une_approbation_perimee_est_refusee(tmp_path):
    store = ApprovalStore(tmp_path / "a.json")
    store.grant("abc", "POST", "http://x/transfer", "alice", ttl_ms=1)

    with pytest.raises(ApprovalError, match="périmée"):
        store.consume("abc", "POST", "http://x/transfer", now=10 ** 13)


def test_les_approbations_survivent_a_un_redemarrage(tmp_path):
    chemin = tmp_path / "a.json"
    ApprovalStore(chemin).grant("abc", "POST", "http://x/t", "alice")

    repris = ApprovalStore(chemin)
    assert repris.consume("abc", "POST", "http://x/t").approved_by == "alice"


# ----------------------------------------------------------------------
# Contournement — ce que le proxy ne peut pas empêcher
# ----------------------------------------------------------------------

def test_contournement_appel_direct_sans_proxy(stack):
    """CONTOURNABLE. Le proxy n'est pas un pare-feu : ignorer la variable
    d'environnement suffit. Seule une règle réseau sortante ferme cette
    porte, et elle est hors du produit."""
    r = requests.get(f"{stack['base']}/delete-everything", timeout=10)

    assert r.status_code == 200
    assert stack["touches"], "l'appel direct atteint l'API"
    assert _preuves(stack) == [], "et ne laisse aucune trace — c'est la limite"


def test_contournement_socket_brute(stack):
    """CONTOURNABLE. Un agent qui parle TCP directement échappe au proxy."""
    sock = socket.create_connection(("127.0.0.1", stack["api_port"]), timeout=5)
    sock.sendall(b"GET /delete-by-raw-socket HTTP/1.1\r\n"
                 b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n")
    reponse = sock.recv(4096)
    sock.close()

    assert b"200" in reponse
    assert _preuves(stack) == []


def test_couvert_le_proxy_voit_la_methode_reelle_pas_la_declaration(stack):
    """COUVERT. C'est la thèse : le proxy enregistre ce qui sort, pas ce que
    l'agent prétend. Un agent qui annonce GET mais émet DELETE est vu tel
    qu'il émet."""
    requests.request("DELETE", f"{stack['base']}/ressource",
                     proxies=stack["proxies"], timeout=10)

    preuve = _preuves(stack)[0]
    assert preuve["action"]["method"] == "DELETE"


def test_couvert_changer_d_hote_ou_de_port_ne_contourne_rien(stack):
    """COUVERT. La politique porte sur l'action, pas sur la destination :
    viser un autre hôte ou un autre port ne change pas la classification
    tant que le trafic passe par le proxy."""
    r = requests.post("http://un-autre-hote.invalid:9999/delete/tout", json={},
                      proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    assert r.json()["risk"] == "R5"
    assert r.json()["rule"] == "destructive"


def test_couvert_une_methode_hors_politique_tombe_sur_le_defaut(stack):
    """COUVERT. Ce que personne n'a prévu est refusé, pas laissé passer."""
    r = requests.request("PUT", f"{stack['base']}/inconnu",
                         proxies=stack["proxies"], timeout=10)

    assert r.status_code == 403
    assert r.json()["rule"] == "default"
    assert stack["touches"] == []


def test_couvert_un_corps_enorme_ne_fait_pas_tomber_le_proxy(stack):
    gros = {"payload": "x" * 2_000_000}
    r = requests.post(f"{stack['base']}/items", json=gros,
                      proxies=stack["proxies"], timeout=30)

    assert r.status_code == 200
    assert len(_preuves(stack)[0]["action"]["payload_hash"]) == 64


def test_couvert_le_journal_reste_chaine_sous_concurrence(stack):
    """Vingt requêtes simultanées ne doivent pas casser le chaînage."""
    from intermesh.assurance import verify_chain

    servies = []
    verrou = threading.Lock()

    def frapper(i):
        # Sous forte charge, une requête peut échouer côté client avant
        # d'atteindre le proxy. La propriété testée est le chaînage, pas le
        # taux de réussite du réseau : on compte ce qui a réellement été
        # traité plutôt que de supposer que les vingt passent.
        try:
            reponse = requests.post(f"{stack['base']}/delete/{i}", json={},
                                    proxies=stack["proxies"], timeout=30)
        except requests.RequestException:
            return
        if reponse.status_code == 403:
            with verrou:
                servies.append(i)

    fils = [threading.Thread(target=frapper, args=(i,)) for i in range(20)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()

    preuves = _preuves(stack)
    assert len(servies) >= 15, f"trop peu de requêtes abouties : {len(servies)}/20"
    assert len(preuves) == len(servies), "une preuve par action traitée"
    assert verify_chain(preuves).valid, "le chaînage doit tenir en concurrence"
    assert len({p["prev_hash"] for p in preuves}) == len(preuves), \
        "deux preuves ne doivent jamais partager le même prev_hash"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
