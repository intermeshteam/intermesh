"""Le noyau de paiement : prix, défi, preuve, registre.

Aucun réseau, aucun socket — si un de ces tests devient lent ou instable,
c'est que la couche de paiement s'est mise à dépendre du transport.
"""

from decimal import Decimal

import pytest

from intermesh.payments import (
    CreditLimitExceeded,
    DuplicateNonce,
    Ledger,
    LedgerError,
    PaymentChallenge,
    Price,
    PriceError,
    ProofError,
    UnknownAccount,
    parse_price,
    sign_proof,
    verify_proof,
)
from intermesh.payments.clock import now_ms
from intermesh.signing import derive_signing_key

KEY = derive_signing_key("secret-de-test-payeur")
PUB = KEY.public_key()
AUTRE = derive_signing_key("une-tout-autre-cle")


def _defi(price="$0.001", pay_to="acme", resource="/summarize", ttl=120.0,
          ledger=None):
    return PaymentChallenge.create(price, pay_to=pay_to, resource=resource,
                                   ttl=ttl, ledger=ledger)


# ----------------------------------------------------------------------
# Prix
# ----------------------------------------------------------------------

@pytest.mark.parametrize("raw,amount,currency", [
    ("$0.001", "0.00100000", "USD"),
    ("0.001 USD", "0.00100000", "USD"),
    ("0.001", "0.00100000", "USD"),
    ("€1.50", "1.50000000", "EUR"),
    ("  $2  ", "2.00000000", "USD"),
])
def test_les_formats_de_prix_acceptes(raw, amount, currency):
    price = parse_price(raw)
    assert price.amount == Decimal(amount)
    assert price.currency == currency


@pytest.mark.parametrize("raw", ["", "gratuit", "$", "$-1", "12,50", "$1 EUR"])
def test_un_prix_illisible_est_refuse(raw):
    with pytest.raises(PriceError):
        parse_price(raw)


def test_les_montants_ne_sont_jamais_des_flottants():
    """0.1 + 0.2 doit faire exactement 0.3, pas 0.30000000000000004."""
    total = parse_price("$0.1") + parse_price("$0.2")

    assert total.amount == Decimal("0.30000000000000000").quantize(Decimal("0.00000001"))
    assert str(total) == "0.30000000 USD"


def test_deux_devises_ne_s_additionnent_pas():
    with pytest.raises(PriceError):
        parse_price("$1") + parse_price("€1")


def test_mille_micro_paiements_font_un_compte_rond():
    """Le cas qui fait dériver un float : beaucoup de très petits montants."""
    total = Price(Decimal("0"), "USD")
    for _ in range(1000):
        total = total + parse_price("$0.001")

    assert total.amount == Decimal("1.00000000")


# ----------------------------------------------------------------------
# Défi
# ----------------------------------------------------------------------

def test_chaque_defi_porte_un_nonce_different():
    assert _defi().nonce != _defi().nonce


def test_un_defi_perime_se_declare_tel():
    assert _defi(ttl=-1).is_expired()
    assert not _defi(ttl=60).is_expired()


def test_le_defi_fait_l_aller_retour_json():
    original = _defi(ledger="https://ledger.example.com")
    copie = PaymentChallenge.from_dict(original.to_dict())

    assert copie == original


def test_un_defi_incomplet_est_rejete():
    with pytest.raises(ValueError, match="champs manquants"):
        PaymentChallenge.from_dict({"amount": "0.001", "currency": "USD"})


# ----------------------------------------------------------------------
# Preuve
# ----------------------------------------------------------------------

def test_une_preuve_signee_se_verifie():
    defi = _defi()
    preuve = verify_proof(sign_proof(defi, "client", KEY), PUB, defi)

    assert preuve.payer == "client"
    assert preuve.amount == defi.amount
    assert preuve.nonce == defi.nonce


def test_une_preuve_signee_par_une_autre_cle_est_refusee():
    defi = _defi()
    with pytest.raises(ProofError, match="signature invalide"):
        verify_proof(sign_proof(defi, "client", AUTRE), PUB, defi)


def test_une_preuve_alteree_est_refusee():
    defi = _defi()
    entete = sign_proof(defi, "client", KEY)
    corps, signature = entete.split(".", 1)

    # Un octet modifié dans le corps suffit à casser la signature.
    altere = corps[:-2] + ("AA" if corps[-2:] != "AA" else "AB")
    with pytest.raises(ProofError):
        verify_proof(f"{altere}.{signature}", PUB, defi)


def test_une_preuve_ne_sert_pas_pour_une_autre_ressource():
    """La faille évidente : payer 0,001 $ et ouvrir le point d'entrée à 10 $."""
    pas_cher = _defi(price="$0.001", resource="/cheap")
    entete = sign_proof(pas_cher, "client", KEY)
    cher = PaymentChallenge.create("$10", pay_to="acme", resource="/expensive")

    with pytest.raises(ProofError, match="ne répond pas à ce défi"):
        verify_proof(entete, PUB, cher)


def test_une_preuve_perimee_est_refusee():
    defi = _defi(ttl=1)
    entete = sign_proof(defi, "client", KEY)

    with pytest.raises(ProofError, match="périmée"):
        verify_proof(entete, PUB, defi, now=now_ms() + 10_000)


def test_les_horodatages_signes_sont_des_entiers():
    """
    Régression inter-langages. Python sérialise `1788459123.0` en
    « 1788459123.0 », JavaScript en « 1788459123 » : octets différents,
    donc signature différente. Le cas ne se produit que lorsque l'horloge
    tombe pile sur une seconde ronde — assez rare pour passer tous les
    tests, assez fréquent pour casser en production.

    Un entier se sérialise identiquement dans les deux langages.
    """
    import json

    defi = _defi()
    preuve = verify_proof(sign_proof(defi, "client", KEY), PUB, defi)

    assert isinstance(defi.expires_at, int)
    assert isinstance(preuve.issued_at, int)
    assert isinstance(preuve.expires_at, int)

    encode = json.dumps(preuve.payload(), sort_keys=True, separators=(",", ":"))
    for champ in ("issued_at", "expires_at"):
        rendu = encode.split(f'"{champ}":', 1)[1].split(",", 1)[0]
        assert "." not in rendu, (
            f"{champ} est sérialisé en flottant ({rendu}) — JavaScript "
            "écrirait autre chose et la signature ne correspondrait plus")


@pytest.mark.parametrize("entete", ["", "pas-de-point", "aaa.bbb", "."])
def test_un_entete_malforme_ne_fait_pas_planter(entete):
    with pytest.raises(ProofError):
        verify_proof(entete, PUB)


# ----------------------------------------------------------------------
# Registre
# ----------------------------------------------------------------------

def _registre():
    ledger = Ledger()
    ledger.open_account("client", credit_limit="$1")
    ledger.open_account("acme", credit_limit="$0")
    return ledger


def _preuve(defi, payer="client"):
    return verify_proof(sign_proof(defi, payer, KEY), PUB, defi)


def test_une_ecriture_deplace_le_montant():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.25")))

    assert ledger.balance("client").amount == Decimal("-0.25000000")
    assert ledger.balance("acme").amount == Decimal("0.25000000")


def test_un_compte_demarre_a_zero_et_descend():
    """Pas de provision préalable : c'est tout l'intérêt du différé."""
    ledger = _registre()

    assert ledger.balance("client").amount == Decimal("0")
    ledger.charge(_preuve(_defi("$0.10")))
    assert ledger.balance("client").amount < 0


def test_le_plafond_de_credit_arrete_la_consommation():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.99")))

    with pytest.raises(CreditLimitExceeded, match="il reste"):
        ledger.charge(_preuve(_defi("$0.50")))


def test_la_meme_preuve_ne_passe_pas_deux_fois():
    ledger = _registre()
    preuve = _preuve(_defi("$0.01"))
    ledger.charge(preuve)

    with pytest.raises(DuplicateNonce, match="rejouée"):
        ledger.charge(preuve)


def test_on_ne_debite_pas_un_compte_inconnu():
    ledger = Ledger()
    ledger.open_account("acme")

    with pytest.raises(UnknownAccount):
        ledger.charge(_preuve(_defi("$0.01")))


def test_un_reglement_recu_remonte_le_solde():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.75")))
    ledger.settle("client", "$0.75")

    assert ledger.balance("client").amount == Decimal("0")


def test_un_reglement_negatif_est_refuse():
    ledger = _registre()
    with pytest.raises(LedgerError):
        ledger.settle("client", "$0")


def test_le_releve_ne_montre_que_ses_propres_ecritures():
    ledger = _registre()
    ledger.open_account("tiers")
    ledger.charge(_preuve(_defi("$0.01")))

    assert len(ledger.statement("client")) == 1
    assert ledger.statement("tiers") == []


def test_le_total_du_est_la_matiere_d_une_facture():
    ledger = _registre()
    for _ in range(3):
        ledger.charge(_preuve(_defi("$0.10")))

    assert ledger.total_owed("client").amount == Decimal("0.30000000")


def test_le_releve_se_borne_dans_le_temps():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.01")), now=1000.0)
    ledger.charge(_preuve(_defi("$0.02")), now=2000.0)

    assert len(ledger.statement("client", since=1500.0)) == 1
    assert len(ledger.statement("client", until=1500.0)) == 1


def test_une_devise_etrangere_est_refusee():
    ledger = _registre()
    with pytest.raises(LedgerError, match="refusée"):
        ledger.charge(_preuve(_defi("€1")))


# ----------------------------------------------------------------------
# Journal scellé
# ----------------------------------------------------------------------

def test_le_journal_est_intact_apres_des_ecritures():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.01")))
    ledger.settle("client", "$0.01")

    assert ledger.verify_integrity()


def test_une_ecriture_reecrite_apres_coup_se_voit():
    """Sans cette propriété, le relevé ne vaut rien en cas de litige."""
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.01")))

    ledger.audit.chain[-1].metadata["amount"] = "999.00"

    assert not ledger.verify_integrity()


def test_le_registre_survit_a_un_aller_retour_serialise():
    ledger = _registre()
    ledger.charge(_preuve(_defi("$0.40")))

    repris = Ledger.import_state(ledger.export_state())

    assert repris.balance("client").amount == Decimal("-0.40000000")
    assert repris.verify_integrity()


def test_un_nonce_reste_refuse_apres_rechargement():
    """Un relais qui redémarre ne doit pas rouvrir la porte au rejeu."""
    ledger = _registre()
    preuve = _preuve(_defi("$0.01"))
    ledger.charge(preuve)

    repris = Ledger.import_state(ledger.export_state())

    with pytest.raises(DuplicateNonce):
        repris.charge(preuve)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
