"""Le portefeuille : ce qui signe, et ce qui refuse de signer.

Un intercepteur qui paie automatiquement tout ce qu'on lui réclame est un
piège à facture. `max_price` est donc **obligatoire** : il n'y a pas de
valeur par défaut permissive, parce qu'un plafond qu'on oublie de régler
est un plafond absent.

`spent` tient le cumul de la session. Un agent qui boucle sur un appel
payant s'arrête sur `BudgetExceeded` au lieu de découvrir l'addition en
fin de mois.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..payments.challenge import PaymentChallenge
from ..payments.price import Price, parse_price, quantize
from ..payments.proof import sign_proof
from ..signing import derive_signing_key, public_pem


class PaymentRefused(Exception):
    """Le portefeuille refuse de signer ce défi."""


class PriceTooHigh(PaymentRefused):
    """Le montant réclamé dépasse le plafond par requête."""


class BudgetExceeded(PaymentRefused):
    """Le cumul de la session dépasse le budget accordé."""


class Wallet:
    """Signe les défis dans les limites qu'on lui a fixées."""

    def __init__(self, agent_id: str, private_key: Ed25519PrivateKey,
                 max_price: str | Price, budget: Optional[str | Price] = None,
                 currency: str = "USD"):
        self.agent_id = agent_id
        self._key = private_key
        self.currency = currency
        self.max_price = parse_price(max_price, default_currency=currency)
        self.budget = parse_price(budget, default_currency=currency) if budget else None
        self._spent = Decimal("0")

    @classmethod
    def from_secret(cls, agent_id: str, secret: str, max_price: str | Price,
                    budget: Optional[str | Price] = None,
                    currency: str = "USD") -> "Wallet":
        """Dérive la clé du secret de l'agent — même mécanisme que le Hub."""
        return cls(agent_id, derive_signing_key(secret), max_price, budget, currency)

    @property
    def public_pem(self) -> str:
        """À déposer au registre : c'est ce qui permet de vérifier les preuves."""
        return public_pem(self._key)

    @property
    def spent(self) -> Price:
        return Price(quantize(self._spent), self.currency)

    @property
    def remaining(self) -> Optional[Price]:
        if self.budget is None:
            return None
        return Price(quantize(self.budget.amount - self._spent), self.currency)

    # ------------------------------------------------------------------

    def authorize(self, challenge: PaymentChallenge) -> str:
        """Vérifie les limites puis signe. Lève plutôt que de dépasser."""
        price = challenge.price

        if price.currency != self.currency:
            raise PaymentRefused(
                f"ce portefeuille paie en {self.currency}, le serveur "
                f"réclame des {price.currency}")

        if challenge.is_expired():
            raise PaymentRefused("le défi est déjà périmé — horloges désaccordées ?")

        if price.amount > self.max_price.amount:
            raise PriceTooHigh(
                f"{challenge.resource} réclame {price.amount} {price.currency}, "
                f"le plafond par requête est {self.max_price.amount}")

        if self.budget is not None and self._spent + price.amount > self.budget.amount:
            raise BudgetExceeded(
                f"budget de session épuisé : {self._spent} dépensés sur "
                f"{self.budget.amount}, {price.amount} de plus refusés")

        header = sign_proof(challenge, self.agent_id, self._key)
        self._spent = quantize(self._spent + price.amount)
        return header
