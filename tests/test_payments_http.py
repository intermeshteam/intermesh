"""Le 402 de bout en bout : portail, portefeuille, intercepteur.

Les tests du portail ne touchent pas à HTTP — c'est la preuve que la
logique est bien restée hors du framework. Les derniers montent une vraie
application FastAPI et font passer un paiement réel à travers.
"""

import pytest

from intermesh.client import BudgetExceeded, PriceTooHigh, Wallet
from intermesh.client.http import PaymentFailed, pay_and_retry
from intermesh.payments import HEADER, Ledger, PaymentChallenge
from intermesh.payments.keyring import Keyring, UnknownPayer
from intermesh.server import PaymentGate, PaymentRejected, PaymentRequired

PAYER = "client"
PAYEE = "acme"


@pytest.fixture
def wallet():
    return Wallet.from_secret(PAYER, "secret-du-client", max_price="$1")


@pytest.fixture
def gate(wallet):
    ledger = Ledger()
    ledger.open_account(PAYER, credit_limit="$5")
    ledger.open_account(PAYEE, credit_limit="$0")

    keyring = Keyring()
    keyring.add(PAYER, wallet.public_pem)

    return PaymentGate(ledger, keyring, payee=PAYEE)


def _payer(gate, wallet, resource="/summarize", price="$0.001"):
    """Le parcours complet : 402, signature, rejeu."""
    with pytest.raises(PaymentRequired) as premier:
        gate.admit(resource, price, None)

    header = wallet.authorize(premier.value.challenge)
    return gate.admit(resource, price, header)


# ----------------------------------------------------------------------
# Le portail
# ----------------------------------------------------------------------

def test_sans_preuve_le_portail_reclame_un_paiement(gate):
    with pytest.raises(PaymentRequired) as exc:
        gate.admit("/summarize", "$0.001", None)

    challenge = exc.value.challenge
    assert challenge.pay_to == PAYEE
    assert challenge.resource == "/summarize"
    assert exc.value.body()["amount"] == "0.00100000"
    assert "InterMesh" in exc.value.headers()["WWW-Authenticate"]


def test_une_preuve_valide_ouvre_la_porte(gate, wallet):
    settled = _payer(gate, wallet)

    assert settled.proof.payer == PAYER
    assert gate.ledger.balance(PAYER).amount < 0
    assert gate.ledger.balance(PAYEE).amount > 0


def test_un_nonce_inconnu_est_refuse(gate, wallet):
    """Un défi que ce serveur n'a jamais émis ne vaut rien."""
    etranger = PaymentChallenge.create("$0.001", pay_to=PAYEE, resource="/summarize")
    header = wallet.authorize(etranger)

    with pytest.raises(PaymentRejected, match="nonce inconnu"):
        gate.admit("/summarize", "$0.001", header)


def test_le_meme_entete_ne_passe_pas_deux_fois(gate, wallet):
    with pytest.raises(PaymentRequired) as exc:
        gate.admit("/summarize", "$0.001", None)
    header = wallet.authorize(exc.value.challenge)

    gate.admit("/summarize", "$0.001", header)

    with pytest.raises(PaymentRejected, match="déjà utilisé"):
        gate.admit("/summarize", "$0.001", header)


def test_un_payeur_inconnu_du_trousseau_est_refuse(gate):
    inconnu = Wallet.from_secret("fantome", "sa-cle", max_price="$1")
    with pytest.raises(PaymentRequired) as exc:
        gate.admit("/summarize", "$0.001", None)
    header = inconnu.authorize(exc.value.challenge)

    with pytest.raises(PaymentRejected, match="aucune clé publique"):
        gate.admit("/summarize", "$0.001", header)


def test_un_entete_illisible_ne_fait_pas_planter(gate):
    with pytest.raises(PaymentRejected):
        gate.admit("/summarize", "$0.001", "n-importe-quoi")


def test_une_preuve_refusee_ne_fournit_pas_de_nouveau_defi(gate):
    """Sinon chaque tentative invalide offrirait un nonce gratuit."""
    with pytest.raises(PaymentRejected) as exc:
        gate.admit("/summarize", "$0.001", "corrompu.aussi")

    assert not hasattr(exc.value, "challenge")


def test_le_plafond_de_credit_refuse_le_passage(gate, wallet):
    gate.ledger.open_account("pauvre", credit_limit="$0.0001")
    pauvre = Wallet.from_secret("pauvre", "secret-pauvre", max_price="$1")
    gate.keyring.add("pauvre", pauvre.public_pem)

    with pytest.raises(PaymentRequired) as exc:
        gate.admit("/summarize", "$0.50", None)
    header = pauvre.authorize(exc.value.challenge)

    with pytest.raises(PaymentRejected, match="plafond"):
        gate.admit("/summarize", "$0.50", header)


def test_les_defis_non_honores_finissent_par_etre_oublies(gate):
    """Sans éviction, un client qui ne paie jamais fait fuir la mémoire."""
    for i in range(5):
        with pytest.raises(PaymentRequired):
            gate.admit(f"/r{i}", "$0.001", None)
    assert gate.pending_count == 5

    gate._evict(now=gate._pending[next(iter(gate._pending))].expires_at + 3600)
    assert gate.pending_count == 0


# ----------------------------------------------------------------------
# Le portefeuille
# ----------------------------------------------------------------------

def test_le_portefeuille_refuse_au_dela_du_plafond():
    petit = Wallet.from_secret(PAYER, "s", max_price="$0.01")
    cher = PaymentChallenge.create("$5", pay_to=PAYEE, resource="/expensive")

    with pytest.raises(PriceTooHigh, match="plafond par requête"):
        petit.authorize(cher)


def test_le_budget_de_session_finit_par_bloquer():
    wallet = Wallet.from_secret(PAYER, "s", max_price="$1", budget="$0.05")
    for _ in range(5):
        wallet.authorize(PaymentChallenge.create("$0.01", pay_to=PAYEE, resource="/x"))

    with pytest.raises(BudgetExceeded, match="budget de session"):
        wallet.authorize(PaymentChallenge.create("$0.01", pay_to=PAYEE, resource="/x"))


def test_un_refus_ne_consomme_pas_de_budget():
    wallet = Wallet.from_secret(PAYER, "s", max_price="$0.01", budget="$1")
    with pytest.raises(PriceTooHigh):
        wallet.authorize(PaymentChallenge.create("$5", pay_to=PAYEE, resource="/x"))

    assert wallet.spent.amount == 0


def test_le_portefeuille_suit_ce_qu_il_a_depense():
    wallet = Wallet.from_secret(PAYER, "s", max_price="$1", budget="$1")
    wallet.authorize(PaymentChallenge.create("$0.30", pay_to=PAYEE, resource="/x"))

    assert str(wallet.spent) == "0.30000000 USD"
    assert wallet.remaining.amount == wallet.budget.amount - wallet.spent.amount


def test_un_defi_perime_n_est_pas_signe():
    wallet = Wallet.from_secret(PAYER, "s", max_price="$1")
    perime = PaymentChallenge.create("$0.01", pay_to=PAYEE, resource="/x", ttl=-1)

    with pytest.raises(Exception, match="périmé"):
        wallet.authorize(perime)


# ----------------------------------------------------------------------
# L'intercepteur, sans réseau
# ----------------------------------------------------------------------

class _Reponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body


def test_l_intercepteur_paie_et_rejoue(gate, wallet):
    appels = []

    def send(headers):
        appels.append(headers)
        try:
            gate.admit("/summarize", "$0.001", headers.get(HEADER))
        except PaymentRequired as exc:
            return _Reponse(402, exc.body())
        return _Reponse(200, {"ok": True})

    reponse = pay_and_retry(send, wallet, lambda r: r.status_code, lambda r: r.body)

    assert reponse.status_code == 200
    assert len(appels) == 2, "exactement un rejeu, pas une boucle"
    assert HEADER in appels[1]


def test_l_intercepteur_ne_boucle_pas_sur_un_serveur_fautif(wallet):
    """Un serveur qui renvoie 402 même payé ne doit pas vider le budget."""
    appels = []
    defi = PaymentChallenge.create("$0.001", pay_to=PAYEE, resource="/x").to_dict()

    def send(headers):
        appels.append(headers)
        return _Reponse(402, dict(defi, error="payment_rejected", reason="non"))

    with pytest.raises(PaymentFailed, match="présenté et refusé"):
        pay_and_retry(send, wallet, lambda r: r.status_code, lambda r: r.body)

    assert len(appels) == 2


def test_une_reponse_sans_defi_est_signalee(wallet):
    def send(headers):
        return _Reponse(402, "pas du json")

    with pytest.raises(PaymentFailed, match="sans défi lisible"):
        pay_and_retry(send, wallet, lambda r: r.status_code, lambda r: r.body)


def test_une_reponse_normale_passe_sans_paiement(wallet):
    def send(headers):
        return _Reponse(200, {"ok": True})

    assert pay_and_retry(send, wallet, lambda r: r.status_code,
                         lambda r: r.body).status_code == 200
    assert wallet.spent.amount == 0


# ----------------------------------------------------------------------
# Bout en bout, vraie application FastAPI
# ----------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi", reason="FastAPI absent de la machine")


@pytest.fixture
def app_et_client(wallet):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from intermesh.server.fastapi import PaymentGuard

    ledger = Ledger()
    ledger.open_account(PAYER, credit_limit="$5")
    ledger.open_account(PAYEE, credit_limit="$0")
    keyring = Keyring({PAYER: wallet.public_pem})

    app = FastAPI()
    guard = PaymentGuard(ledger, keyring, payee=PAYEE)

    @app.get("/summarize")
    @guard.require_payment(price="$0.001")
    async def summarize(request: Request):
        return {"summary": "ok", "paid_by": request.state.payment.proof.payer}

    @app.get("/free")
    async def free():
        return {"summary": "gratuit"}

    return TestClient(app), ledger, guard


def test_fastapi_renvoie_402_puis_sert_apres_paiement(app_et_client, wallet):
    client, ledger, _ = app_et_client

    premier = client.get("/summarize")
    assert premier.status_code == 402
    assert premier.json()["pay_to"] == PAYEE

    header = wallet.authorize(PaymentChallenge.from_dict(premier.json()))
    second = client.get("/summarize", headers={HEADER: header})

    assert second.status_code == 200
    assert second.json()["paid_by"] == PAYER
    assert ledger.balance(PAYEE).amount > 0


def test_fastapi_laisse_passer_un_point_d_entree_gratuit(app_et_client):
    client, _, _ = app_et_client
    assert client.get("/free").status_code == 200


def test_fastapi_refuse_un_entete_bidon(app_et_client):
    client, _, _ = app_et_client
    reponse = client.get("/summarize", headers={HEADER: "bidon.bidon"})

    assert reponse.status_code == 402
    assert reponse.json()["error"] == "payment_rejected"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
