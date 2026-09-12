"""Montants monétaires — en Decimal, jamais en float.

`0.1 + 0.2 != 0.3` en virgule flottante. Sur un compteur qui additionne
des millions de paiements à 0,001 $, l'écart n'est pas théorique : il
devient la différence entre deux factures qui ne tombent jamais juste.
Tout ce module manipule des `Decimal`, et le seul point d'entrée depuis
une chaîne est `parse_price`.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import NamedTuple

# Huit décimales : assez fin pour un paiement à 0,000001 $, assez grossier
# pour qu'une somme reste exacte et lisible dans une facture.
SCALE = Decimal("0.00000001")

_PRICE = re.compile(
    r"""^\s*
    (?:(?P<symbol>[$€£])\s*)?      # $0.001
    (?P<amount>\d+(?:\.\d+)?)
    (?:\s*(?P<code>[A-Za-z]{3}))?  # 0.001 USD
    \s*$""",
    re.VERBOSE,
)

_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}


class PriceError(ValueError):
    """Prix impossible à lire, ou négatif."""


class Price(NamedTuple):
    """Un montant et sa devise. Immuable, comparable, additionnable."""

    amount: Decimal
    currency: str

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def __add__(self, other: "Price") -> "Price":
        self._same_currency(other)
        return Price(quantize(self.amount + other.amount), self.currency)

    def __sub__(self, other: "Price") -> "Price":
        self._same_currency(other)
        return Price(quantize(self.amount - other.amount), self.currency)

    def _same_currency(self, other: "Price") -> None:
        if self.currency != other.currency:
            raise PriceError(
                f"{self.currency} et {other.currency} ne s'additionnent pas — "
                "il n'y a pas de taux de change ici."
            )


def quantize(value: Decimal) -> Decimal:
    """Ramène à l'échelle du registre, au plus proche."""
    return value.quantize(SCALE, rounding=ROUND_HALF_UP)


def parse_price(raw: str | Price, default_currency: str = "USD") -> Price:
    """Lit `"$0.001"`, `"0.001 USD"` ou `"0.001"`.

    Un `Price` passe au travers inchangé : les appelants peuvent accepter
    l'un ou l'autre sans se poser la question.
    """
    if isinstance(raw, Price):
        return raw
    if not isinstance(raw, str):
        raise PriceError(f"prix attendu sous forme de chaîne, reçu {type(raw).__name__}")

    match = _PRICE.match(raw)
    if not match:
        raise PriceError(f"prix illisible : {raw!r} (attendu « $0.001 » ou « 0.001 USD »)")

    symbol, code = match.group("symbol"), match.group("code")
    if symbol and code and _SYMBOLS.get(symbol) != code.upper():
        raise PriceError(f"{raw!r} annonce deux devises différentes")

    currency = _SYMBOLS.get(symbol) or (code.upper() if code else default_currency)

    try:
        amount = quantize(Decimal(match.group("amount")))
    except InvalidOperation as exc:  # pragma: no cover - filtré par la regex
        raise PriceError(f"montant illisible dans {raw!r}") from exc

    if amount < 0:
        raise PriceError("un prix négatif n'a pas de sens")

    return Price(amount, currency)
