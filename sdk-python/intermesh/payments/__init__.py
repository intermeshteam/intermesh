"""Le noyau de paiement d'InterMesh — HTTP 402, règlement différé.

Quatre briques, sans dépendance au transport :

* `price`     — des montants en Decimal, lus depuis « $0.001 »
* `challenge` — ce que le serveur réclame dans une réponse 402
* `proof`     — l'engagement signé du payeur, porté par un en-tête
* `ledger`    — qui doit combien à qui, scellé dans une chaîne Merkle

Rien ici n'ouvre de socket ni ne connaît HTTP : les intégrations serveur
et client se posent par-dessus, et se testent sans réseau.
"""

from .challenge import PaymentChallenge
from .ledger import (
    Account,
    Charge,
    CreditLimitExceeded,
    DuplicateNonce,
    Ledger,
    LedgerError,
    UnknownAccount,
)
from .price import Price, PriceError, parse_price
from .proof import HEADER, PaymentProof, ProofError, sign_proof, verify_proof

__all__ = [
    "PaymentChallenge",
    "Price", "PriceError", "parse_price",
    "PaymentProof", "ProofError", "sign_proof", "verify_proof", "HEADER",
    "Ledger", "Account", "Charge",
    "LedgerError", "UnknownAccount", "CreditLimitExceeded", "DuplicateNonce",
]
