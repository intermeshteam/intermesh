"""La preuve de paiement : une reconnaissance de dette signée.

Le règlement étant différé, rien n'est bloqué au moment de l'appel. Ce que
le client remet n'est donc pas un reçu de virement mais un engagement :
« je, porteur de cette clé, dois ce montant à ce destinataire pour cette
ressource ». La propriété recherchée n'est pas l'irréversibilité des fonds,
c'est la **non-répudiation** — le débiteur ne peut pas nier ensuite.

D'où trois exigences, et pas une de plus :

* la signature couvre le montant, le destinataire, la ressource et le
  nonce. Modifier l'un d'eux invalide la preuve ;
* la sérialisation est canonique (clés triées, séparateurs fixes), sinon
  deux encodages du même objet produiraient deux signatures et la
  vérification deviendrait un pari ;
* la preuve porte son expiration. Une signature valable éternellement est
  une dette que le créancier pourrait présenter dans dix ans.

Le rejeu, lui, ne se traite pas ici : c'est au registre de refuser un
nonce déjà honoré, parce que lui seul sait ce qui a été servi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..canonical import b64 as _b64, canonical_bytes, unb64 as _unb64
from .challenge import PaymentChallenge
from .clock import now_ms

HEADER = "X-InterMesh-Payment"
VERSION = "im1"


class ProofError(ValueError):
    """Preuve absente, illisible, altérée ou périmée."""


@dataclass(frozen=True)
class PaymentProof:
    """Engagement signé du payeur, tel qu'il voyage dans l'en-tête."""

    payer: str
    amount: str
    currency: str
    pay_to: str
    resource: str
    nonce: str
    # Millisecondes entières : voir `clock.py`.
    issued_at: int
    expires_at: int

    def payload(self) -> dict:
        return {
            "v": VERSION,
            "payer": self.payer,
            "amount": self.amount,
            "currency": self.currency,
            "pay_to": self.pay_to,
            "resource": self.resource,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def is_expired(self, now: Optional[int] = None) -> bool:
        return (now if now is not None else now_ms()) > self.expires_at


def sign_proof(challenge: PaymentChallenge, payer: str,
               private_key: Ed25519PrivateKey) -> str:
    """Produit la valeur de l'en-tête `X-InterMesh-Payment`."""
    proof = PaymentProof(
        payer=payer,
        amount=challenge.amount,
        currency=challenge.currency,
        pay_to=challenge.pay_to,
        resource=challenge.resource,
        nonce=challenge.nonce,
        issued_at=now_ms(),
        expires_at=challenge.expires_at,
    )
    body = canonical_bytes(proof.payload())
    return f"{_b64(body)}.{_b64(private_key.sign(body))}"


def verify_proof(header_value: str, public_key: Ed25519PublicKey,
                 challenge: Optional[PaymentChallenge] = None,
                 now: Optional[int] = None) -> PaymentProof:
    """Vérifie une preuve et la rend exploitable, ou lève `ProofError`.

    Passer le défi correspondant est vivement recommandé : sans lui, on
    valide une signature sans vérifier qu'elle répond bien à *cette*
    demande — un attaquant rejouerait la preuve d'un appel bon marché sur
    un point d'entrée coûteux.
    """
    if not header_value or "." not in header_value:
        raise ProofError(f"en-tête {HEADER} absent ou malformé")

    encoded_body, encoded_sig = header_value.split(".", 1)
    try:
        body = _unb64(encoded_body)
        signature = _unb64(encoded_sig)
        payload = json.loads(body)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProofError("preuve illisible") from exc

    if payload.get("v") != VERSION:
        raise ProofError(f"version de preuve inconnue : {payload.get('v')!r}")

    try:
        public_key.verify(signature, body)
    except InvalidSignature as exc:
        raise ProofError("signature invalide — la preuve a été modifiée "
                         "ou ne vient pas de cette clé") from exc

    try:
        proof = PaymentProof(
            payer=str(payload["payer"]),
            amount=str(payload["amount"]),
            currency=str(payload["currency"]),
            pay_to=str(payload["pay_to"]),
            resource=str(payload["resource"]),
            nonce=str(payload["nonce"]),
            issued_at=int(payload["issued_at"]),
            expires_at=int(payload["expires_at"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProofError(f"preuve incomplète : {exc}") from exc

    if proof.is_expired(now):
        raise ProofError("preuve périmée")

    if challenge is not None:
        for field_name in ("amount", "currency", "pay_to", "resource", "nonce"):
            expected = getattr(challenge, field_name)
            if getattr(proof, field_name) != expected:
                raise ProofError(
                    f"la preuve ne répond pas à ce défi : {field_name} vaut "
                    f"{getattr(proof, field_name)!r}, attendu {expected!r}"
                )

    return proof
