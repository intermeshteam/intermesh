"""La logique du 402, sans HTTP.

Tout ce qui décide — émettre un défi, vérifier une preuve, passer
l'écriture — vit ici, et ne connaît ni FastAPI, ni Express, ni socket. Les
adaptateurs se contentent de traduire une requête entrante en deux
chaînes et d'écrire le résultat. C'est ce qui permet de tester la partie
délicate en quelques millisecondes, sans serveur.

Le protocole tient en trois temps :

1. requête sans preuve → un défi est émis, retenu, et renvoyé en 402 ;
2. le client signe ce défi précis et rejoue sa requête ;
3. la preuve est vérifiée contre le défi retenu, l'écriture est passée,
   le nonce est consommé.

Retenir le défi est ce qui rend le rejeu impossible : une preuve ne vaut
que pour un nonce que ce serveur a lui-même émis, une seule fois.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..payments.challenge import DEFAULT_TTL, PaymentChallenge
from ..payments.clock import now_ms
from ..payments.keyring import Keyring, UnknownPayer
from ..payments.ledger import Ledger, LedgerError
from ..payments.price import Price
from ..payments.proof import HEADER, PaymentProof, ProofError, verify_proof

# Au-delà, un défi non honoré n'est plus qu'une fuite mémoire.
# En millisecondes, comme tout horodatage du protocole.
PENDING_GRACE = 60_000


class PaymentRequired(Exception):
    """La requête doit être payée — porte le défi à renvoyer en 402."""

    def __init__(self, challenge: PaymentChallenge, reason: str = "payment_required"):
        super().__init__(reason)
        self.challenge = challenge
        self.reason = reason

    def body(self) -> dict:
        return {"error": self.reason, **self.challenge.to_dict()}

    def headers(self) -> Dict[str, str]:
        # Le client sait ainsi quoi renvoyer sans lire la documentation.
        return {"WWW-Authenticate": f'InterMesh realm="{self.challenge.pay_to}"'}


class PaymentRejected(Exception):
    """La preuve existe mais n'est pas recevable — 402 également, sans rejeu."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Settled:
    """Ce que le point d'entrée reçoit quand le paiement est passé."""

    proof: PaymentProof
    amount: Price


class PaymentGate:
    """Émet les défis, vérifie les preuves, tient les nonces en attente."""

    def __init__(self, ledger: Ledger, keyring: Keyring, payee: str,
                 ledger_url: Optional[str] = None, ttl: float = DEFAULT_TTL):
        self.ledger = ledger
        self.keyring = keyring
        self.payee = payee
        self.ledger_url = ledger_url
        self.ttl = ttl
        self._pending: Dict[str, PaymentChallenge] = {}

    # ------------------------------------------------------------------

    def challenge_for(self, resource: str, price) -> PaymentChallenge:
        """Émet un défi et le retient jusqu'à son expiration."""
        self._evict()
        challenge = PaymentChallenge.create(
            price, pay_to=self.payee, resource=resource,
            ledger=self.ledger_url, ttl=self.ttl)
        self._pending[challenge.nonce] = challenge
        return challenge

    def admit(self, resource: str, price, header_value: Optional[str],
              now: Optional[int] = None) -> Settled:
        """Laisse passer la requête, ou lève de quoi répondre 402.

        `PaymentRequired` veut dire « voici ce qu'il faut payer » et
        s'accompagne d'un défi neuf. `PaymentRejected` veut dire « ce que
        vous avez envoyé ne convient pas » et n'en fournit aucun : émettre
        un nouveau défi à chaque preuve invalide offrirait à un attaquant
        une réserve de nonces gratuite.
        """
        if not header_value:
            raise PaymentRequired(self.challenge_for(resource, price))

        try:
            payload_payer = _peek_payer(header_value)
            public_key = self.keyring.public_key(payload_payer)
        except UnknownPayer as exc:
            raise PaymentRejected(str(exc)) from exc
        except ProofError as exc:
            raise PaymentRejected(str(exc)) from exc

        challenge = self._pending.get(_peek_nonce(header_value))
        if challenge is None:
            # Nonce inconnu, déjà consommé, ou émis par un autre processus.
            raise PaymentRejected(
                "nonce inconnu ou déjà utilisé — redemandez un défi")

        try:
            proof = verify_proof(header_value, public_key, challenge, now=now)
        except ProofError as exc:
            raise PaymentRejected(str(exc)) from exc

        if proof.pay_to != self.payee:
            raise PaymentRejected(
                f"preuve émise pour '{proof.pay_to}', ce serveur encaisse "
                f"pour '{self.payee}'")

        try:
            charge = self.ledger.charge(proof, now=now)
        except LedgerError as exc:
            # Le défi reste consommé : une écriture refusée ne doit pas
            # rendre le nonce réutilisable.
            self._pending.pop(challenge.nonce, None)
            raise PaymentRejected(str(exc)) from exc

        self._pending.pop(challenge.nonce, None)
        return Settled(proof=proof, amount=Price(charge.amount, charge.currency))

    # ------------------------------------------------------------------

    def _evict(self, now: Optional[int] = None) -> None:
        moment = now if now is not None else now_ms()
        expired = [n for n, c in self._pending.items()
                   if c.expires_at + PENDING_GRACE < moment]
        for nonce in expired:
            del self._pending[nonce]

    @property
    def pending_count(self) -> int:
        return len(self._pending)


def _peek_payer(header_value: str) -> str:
    """Lit le payeur annoncé, *avant* toute vérification de signature."""
    return _peek(header_value, "payer")


def _peek_nonce(header_value: str) -> str:
    return _peek(header_value, "nonce")


def _peek(header_value: str, field: str) -> str:
    import base64
    import json

    if not header_value or "." not in header_value:
        raise ProofError(f"en-tête {HEADER} absent ou malformé")
    encoded = header_value.split(".", 1)[0]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        value = json.loads(raw)[field]
    except Exception as exc:
        raise ProofError("preuve illisible") from exc
    return str(value)
