"""Le corps d'une réponse 402 : ce que le serveur réclame, et pour quoi.

Un défi est public et non signé — il n'a rien à protéger. Ce qui doit être
infalsifiable, c'est la *réponse* au défi, et c'est le rôle de `proof.py`.

Le nonce est ce qui empêche de rejouer une preuve : le serveur en émet un
par requête et refuse celui qu'il a déjà honoré. Le défi porte aussi la
ressource visée, sans quoi une preuve achetée pour un point d'entrée à
0,001 $ servirait à en ouvrir un à 10 $.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

from .price import Price, parse_price

# Deux minutes : assez pour un aller-retour réseau et une signature, trop
# court pour qu'un défi intercepté garde de la valeur.
DEFAULT_TTL = 120.0


@dataclass(frozen=True)
class PaymentChallenge:
    """Ce que le serveur demande pour servir une requête."""

    amount: str
    currency: str
    pay_to: str
    resource: str
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    expires_at: float = field(default_factory=lambda: time.time() + DEFAULT_TTL)
    ledger: Optional[str] = None

    @classmethod
    def create(cls, price: str | Price, pay_to: str, resource: str,
               ledger: Optional[str] = None, ttl: float = DEFAULT_TTL) -> "PaymentChallenge":
        parsed = parse_price(price)
        return cls(
            amount=str(parsed.amount),
            currency=parsed.currency,
            pay_to=pay_to,
            resource=resource,
            expires_at=time.time() + ttl,
            ledger=ledger,
        )

    @property
    def price(self) -> Price:
        return parse_price(f"{self.amount} {self.currency}")

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) > self.expires_at

    def to_dict(self) -> dict:
        body = {
            "amount": self.amount,
            "currency": self.currency,
            "pay_to": self.pay_to,
            "resource": self.resource,
            "nonce": self.nonce,
            "expires_at": self.expires_at,
        }
        if self.ledger:
            body["ledger"] = self.ledger
        return body

    @classmethod
    def from_dict(cls, data: dict) -> "PaymentChallenge":
        missing = {"amount", "currency", "pay_to", "resource", "nonce"} - set(data)
        if missing:
            raise ValueError(f"défi incomplet, champs manquants : {sorted(missing)}")
        return cls(
            amount=str(data["amount"]),
            currency=str(data["currency"]),
            pay_to=str(data["pay_to"]),
            resource=str(data["resource"]),
            nonce=str(data["nonce"]),
            expires_at=float(data.get("expires_at", time.time() + DEFAULT_TTL)),
            ledger=data.get("ledger"),
        )
