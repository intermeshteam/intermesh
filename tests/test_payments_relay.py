"""Le relais de registre, interrogé pour de vrai en HTTP.

Un vrai serveur est démarré sur un port éphémère : c'est le seul moyen de
vérifier que le routage, les codes de retour et la persistance tiennent
ensemble. Le reste du noyau se teste sans réseau ; celui-ci ne le peut pas.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from intermesh.client import Wallet
from intermesh.payments import Ledger
from intermesh.payments.keyring import Keyring
from intermesh.relay import Registry, make_server

PAYER = "client"
PAYEE = "acme"


@pytest.fixture
def wallet():
    return Wallet.from_secret(PAYER, "secret-du-client", max_price="$1")


@pytest.fixture
def relay(tmp_path):
    registry = Registry(path=tmp_path / "ledger.json")
    httpd = make_server(registry, host="127.0.0.1", port=0, quiet=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base, registry
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(f"{base}{path}", timeout=5) as response:
        return response.status, json.loads(response.read())


def _post(base, path, payload):
    request = urllib.request.Request(
        f"{base}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _erreur(base, path):
    try:
        return _get(base, path)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ----------------------------------------------------------------------

def test_le_relais_repond_present(relay):
    base, _ = relay
    assert _get(base, "/health") == (200, {"status": "ok"})


def test_un_agent_s_enregistre_avec_sa_cle(relay, wallet):
    base, _ = relay
    status, body = _post(base, "/register",
                         {"agent_id": PAYER, "public_key": wallet.public_pem,
                          "credit_limit": "$5"})

    assert status == 201
    assert body["agent_id"] == PAYER
    assert len(body["fingerprint"]) == 16
    assert body["credit_limit"] == "5.00000000"


def test_une_cle_illisible_est_refusee(relay):
    base, _ = relay
    status, body = _post(base, "/register",
                         {"agent_id": "x", "public_key": "pas une clé"})

    assert status == 400
    assert body["error"] == "rejected"


def test_un_champ_manquant_est_nomme(relay):
    base, _ = relay
    status, body = _post(base, "/register", {"agent_id": "x"})

    assert status == 400
    assert body["error"] == "missing_field"


def test_la_cle_publique_est_servie_a_qui_encaisse(relay, wallet):
    """C'est ce qui permet à un serveur tiers de vérifier une preuve."""
    base, _ = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem})

    status, body = _get(base, f"/keys/{PAYER}")

    assert status == 200
    assert body["public_key"] == wallet.public_pem


def test_un_agent_inconnu_donne_404(relay):
    base, _ = relay
    assert _erreur(base, "/keys/fantome")[0] == 404
    assert _erreur(base, "/accounts/fantome")[0] == 404


def test_le_compte_expose_ce_qu_il_reste_a_consommer(relay, wallet):
    base, _ = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem,
                              "credit_limit": "$2"})

    status, body = _get(base, f"/accounts/{PAYER}")

    assert status == 200
    assert body["balance"] == "0"
    assert body["available"] == "2.00000000"


def test_le_releve_donne_la_matiere_d_une_facture(relay, wallet):
    base, registry = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem,
                              "credit_limit": "$5"})
    _post(base, "/register", {"agent_id": PAYEE, "public_key": wallet.public_pem})

    _charger(registry, wallet, "$0.30")
    _charger(registry, wallet, "$0.12")

    status, body = _get(base, f"/accounts/{PAYER}/statement")

    assert status == 200
    assert body["count"] == 2
    assert body["total_owed"] == "0.42000000"


def test_le_releve_se_borne_dans_le_temps(relay, wallet):
    base, registry = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem,
                              "credit_limit": "$5"})
    _post(base, "/register", {"agent_id": PAYEE, "public_key": wallet.public_pem})

    _charger(registry, wallet, "$0.10", now=1000.0)
    _charger(registry, wallet, "$0.20", now=5000.0)

    assert _get(base, f"/accounts/{PAYER}/statement?since=3000")[1]["count"] == 1


def test_un_reglement_remet_le_compte_a_zero(relay, wallet):
    base, registry = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem,
                              "credit_limit": "$5"})
    _post(base, "/register", {"agent_id": PAYEE, "public_key": wallet.public_pem})
    _charger(registry, wallet, "$1.00")

    status, body = _post(base, "/settle", {"agent_id": PAYER, "amount": "$1.00"})

    assert status == 200
    assert body["balance"] == "0E-8" or float(body["balance"]) == 0


def test_le_journal_se_declare_intact(relay, wallet):
    base, _ = relay
    _post(base, "/register", {"agent_id": PAYER, "public_key": wallet.public_pem})

    status, body = _get(base, "/verify")

    assert status == 200
    assert body["intact"] is True
    assert body["entries"] >= 2  # genèse + ouverture de compte


def test_un_json_invalide_ne_fait_pas_tomber_le_relais(relay):
    base, _ = relay
    request = urllib.request.Request(f"{base}/register", data=b"{casse",
                                     method="POST")
    try:
        urllib.request.urlopen(request, timeout=5)
        pytest.fail("un corps invalide devait être rejeté")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400

    assert _get(base, "/health")[0] == 200, "le relais doit survivre"


def test_une_route_inconnue_donne_404(relay):
    base, _ = relay
    assert _erreur(base, "/n-importe-quoi")[0] == 404


# ----------------------------------------------------------------------
# Persistance
# ----------------------------------------------------------------------

def test_l_etat_survit_a_un_redemarrage(tmp_path, wallet):
    chemin = tmp_path / "ledger.json"
    registry = Registry(path=chemin)
    registry.register(PAYER, wallet.public_pem, "$3")
    registry.register(PAYEE, wallet.public_pem)
    _charger(registry, wallet, "$0.50")

    repris = Registry.load(chemin)

    assert repris.account(PAYER)["balance"] == "-0.50000000"
    assert repris.keyring.public_pem(PAYER) == wallet.public_pem
    assert repris.integrity()["intact"]


def test_le_fichier_d_etat_n_est_lisible_que_par_son_proprietaire(tmp_path, wallet):
    """Il contient des soldes : il n'a rien à faire en lecture publique."""
    chemin = tmp_path / "ledger.json"
    Registry(path=chemin).register(PAYER, wallet.public_pem)

    assert oct(chemin.stat().st_mode)[-3:] == "600"


def test_une_ecriture_passee_hors_du_relais_atteint_le_disque(tmp_path, wallet):
    """
    Régression : le portail débite le registre directement, sans passer
    par une route HTTP du relais. Le relais ne sauvegardait qu'à
    l'enregistrement et au règlement — toute requête payée disparaissait
    au redémarrage et le compte repartait à zéro.
    """
    chemin = tmp_path / "ledger.json"
    registry = Registry(path=chemin)
    registry.register(PAYER, wallet.public_pem, "$3")
    registry.register(PAYEE, wallet.public_pem)

    _charger(registry, wallet, "$0.50")  # écriture hors du relais

    sur_disque = json.loads(chemin.read_text(encoding="utf-8"))
    charges = sur_disque["ledger"]["charges"]

    assert len(charges) == 1, "l'écriture doit être sur le disque, pas seulement en mémoire"
    assert charges[0]["amount"] == "0.50000000"


def test_un_fichier_absent_donne_un_registre_vierge(tmp_path):
    registry = Registry.load(tmp_path / "jamais-cree.json")

    assert len(registry.keyring) == 0
    assert registry.integrity()["intact"]


# ----------------------------------------------------------------------

def _charger(registry, wallet, price, now=None):
    """Passe une écriture via le parcours complet défi → preuve → registre."""
    from intermesh.server import PaymentGate, PaymentRequired

    gate = PaymentGate(registry.ledger, registry.keyring, payee=PAYEE)
    try:
        gate.admit("/x", price, None)
    except PaymentRequired as exc:
        header = wallet.authorize(exc.value.challenge if hasattr(exc, "value")
                                  else exc.challenge)
        return gate.admit("/x", price, header, now=now)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
