"""L'intercepteur : un 402 absorbé, la requête rejouée une fois.

Le principe tient en trois lignes de logique, et tout le soin est dans
les garde-fous :

* **un seul rejeu.** Un serveur qui renvoie 402 sur une requête déjà
  payée est en faute ; boucler dessus transformerait cette faute en
  dépense illimitée ;
* **le plafond est vérifié avant de signer**, pas après. C'est le
  portefeuille qui refuse, et il refuse fort — par une exception, pas par
  un avertissement qu'on ne lit jamais ;
* **le corps de la requête est réutilisé tel quel.** Une requête rejouée
  avec un corps différent paierait pour autre chose que ce qu'elle
  obtient.

`httpx` n'est pas une dépendance du paquet. Le cœur de la boucle vit dans
`pay_and_retry`, qui ne connaît que des fonctions — un utilisateur de
`requests` ou d'`aiohttp` le réemploie sans rien réécrire.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ..payments.challenge import PaymentChallenge
from ..payments.proof import HEADER
from .wallet import PaymentRefused, Wallet

PAYMENT_REQUIRED = 402


class PaymentFailed(Exception):
    """Le paiement a été tenté et le serveur a refusé de servir."""


def challenge_from_response(body: Any) -> PaymentChallenge:
    """Lit le défi dans un corps de réponse 402."""
    if isinstance(body, (bytes, bytearray, str)):
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PaymentFailed("réponse 402 sans défi lisible") from exc
    if not isinstance(body, dict):
        raise PaymentFailed("réponse 402 sans défi lisible")
    try:
        return PaymentChallenge.from_dict(body)
    except ValueError as exc:
        raise PaymentFailed(f"défi invalide : {exc}") from exc


def pay_and_retry(send: Callable[[dict], Any], wallet: Wallet,
                  status_of: Callable[[Any], int],
                  body_of: Callable[[Any], Any]) -> Any:
    """Envoie, et si c'est un 402, signe puis renvoie — une seule fois."""
    response = send({})
    if status_of(response) != PAYMENT_REQUIRED:
        return response

    challenge = challenge_from_response(body_of(response))
    header = wallet.authorize(challenge)  # lève si le plafond est dépassé

    retried = send({HEADER: header})
    if status_of(retried) == PAYMENT_REQUIRED:
        reason = _reason(body_of(retried))
        raise PaymentFailed(
            f"paiement présenté et refusé pour {challenge.resource} : {reason}")
    return retried


def _reason(body: Any) -> str:
    if isinstance(body, (bytes, bytearray, str)):
        try:
            body = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return "raison illisible"
    if isinstance(body, dict):
        return str(body.get("reason") or body.get("error") or "sans raison")
    return "sans raison"


class PaymentClient:
    """Un client httpx qui règle les 402 tout seul, dans les limites fixées.

        wallet = Wallet.from_secret("mon-agent", secret, max_price="$0.01")
        with PaymentClient(wallet) as client:
            r = client.get("https://api.example.com/summarize")
    """

    def __init__(self, wallet: Wallet, client: Optional[Any] = None, **kwargs: Any):
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dépend de l'environnement
            raise ImportError(
                "PaymentClient demande httpx : pip install 'intermesh[http]'"
            ) from exc

        self.wallet = wallet
        self._client = client or httpx.Client(**kwargs)
        self._owned = client is None

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        def send(extra_headers: dict) -> Any:
            headers = dict(kwargs.pop("headers", None) or {})
            headers.update(extra_headers)
            return self._client.request(method, url, headers=headers, **kwargs)

        return pay_and_retry(send, self.wallet,
                             status_of=lambda r: r.status_code,
                             body_of=lambda r: r.content)

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def __enter__(self) -> "PaymentClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


__all__ = ["PaymentClient", "PaymentFailed", "PaymentRefused",
           "pay_and_retry", "challenge_from_response"]
