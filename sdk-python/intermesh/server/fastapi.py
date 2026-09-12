"""Adaptateur FastAPI — la traduction, rien de plus.

Toute la logique vit dans `gate.py`. Ce fichier lit un en-tête, appelle le
portail, et transforme deux exceptions en réponses HTTP. S'il grossit,
c'est qu'une décision a fui hors du noyau.

    app = FastAPI()
    intermesh = PaymentGuard(ledger, keyring, payee="acme")

    @app.get("/summarize")
    @intermesh.require_payment(price="$0.001")
    async def summarize(request: Request):
        return {"summary": "..."}

FastAPI n'est pas une dépendance du paquet : l'import échoue avec un
message utile plutôt qu'une pile d'appels, si le module est absent.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Optional

from ..payments.keyring import Keyring
from ..payments.ledger import Ledger
from ..payments.proof import HEADER
from .gate import PaymentGate, PaymentRejected, PaymentRequired, Settled

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError as exc:  # pragma: no cover - dépend de l'environnement
    raise ImportError(
        "l'adaptateur FastAPI demande fastapi : pip install 'intermesh[fastapi]'"
    ) from exc


class PaymentGuard:
    """Fabrique de décorateurs, adossée à un portail unique."""

    def __init__(self, ledger: Ledger, keyring: Keyring, payee: str,
                 ledger_url: Optional[str] = None):
        self.gate = PaymentGate(ledger, keyring, payee, ledger_url=ledger_url)

    def require_payment(self, price: str, resource: Optional[str] = None):
        """Exige un paiement avant d'exécuter le point d'entrée.

        `resource` vaut par défaut le chemin de la requête. La preciser
        n'a d'intérêt que si plusieurs chemins doivent partager un même
        tarif — sinon le chemin est déjà l'identifiant naturel.
        """
        def decorator(func: Callable) -> Callable:
            is_async = inspect.iscoroutinefunction(func)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any):
                request = _find_request(args, kwargs)
                if request is None:
                    raise RuntimeError(
                        f"{func.__name__} doit recevoir un paramètre "
                        "`request: Request` pour lire l'en-tête de paiement")

                target = resource or request.url.path
                try:
                    settled = self.gate.admit(
                        target, price, request.headers.get(HEADER))
                except PaymentRequired as required:
                    return JSONResponse(status_code=402, content=required.body(),
                                        headers=required.headers())
                except PaymentRejected as rejected:
                    return JSONResponse(status_code=402,
                                        content={"error": "payment_rejected",
                                                 "reason": rejected.reason})

                # Le point d'entrée peut vouloir savoir qui a payé.
                request.state.payment = settled
                result = func(*args, **kwargs)
                return await result if is_async else result

            return wrapper
        return decorator


def _find_request(args, kwargs) -> Optional["Request"]:
    for value in list(kwargs.values()) + list(args):
        if isinstance(value, Request):
            return value
    return None


__all__ = ["PaymentGuard", "Settled"]
