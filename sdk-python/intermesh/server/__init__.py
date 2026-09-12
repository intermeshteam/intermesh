"""Côté serveur : réclamer un paiement avant de servir.

`gate` porte la décision et ne dépend d'aucun framework. `fastapi` n'est
importé que si on le demande, pour que le paquet reste installable sans.
"""

from .gate import (
    PaymentGate,
    PaymentRejected,
    PaymentRequired,
    Settled,
)

__all__ = ["PaymentGate", "PaymentRequired", "PaymentRejected", "Settled"]
