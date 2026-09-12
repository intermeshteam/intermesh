"""Le registre : qui doit combien à qui, et sur quelle preuve.

Le règlement étant différé, il n'y a pas de solde à provisionner avant le
premier appel. Un compte démarre à zéro et **descend** au fil de ce qu'il
consomme ; la limite de crédit dit jusqu'où il peut descendre. C'est ce qui
remplace le séquestre : personne ne bloque de fonds, mais personne ne
consomme non plus sans borne.

Chaque écriture est scellée dans la chaîne Merkle de `intermesh.audit`.
C'est ce qui tranche un litige de facturation : un relevé exporté d'ici est
vérifiable ligne à ligne par les deux parties, sans avoir à se croire.

Ce module ne persiste rien de lui-même — `export_state`/`import_state` le
rendent sérialisable, et c'est le serveur relais qui choisit son stockage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from ..audit import ImmutableAuditLog
from .price import Price, parse_price, quantize
from .proof import PaymentProof

DEFAULT_CREDIT_LIMIT = "10.00"


class LedgerError(Exception):
    """Écriture refusée par le registre."""


class UnknownAccount(LedgerError):
    """Compte jamais ouvert — on ne débite pas un inconnu."""


class CreditLimitExceeded(LedgerError):
    """La dette dépasserait le plafond accordé."""


class DuplicateNonce(LedgerError):
    """Preuve déjà honorée : c'est un rejeu."""


@dataclass(frozen=True)
class Account:
    agent_id: str
    currency: str
    credit_limit: Decimal
    balance: Decimal  # négatif = doit de l'argent

    @property
    def available(self) -> Decimal:
        """Ce qu'il reste à consommer avant de heurter le plafond."""
        return quantize(self.balance + self.credit_limit)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "currency": self.currency,
            "credit_limit": str(self.credit_limit),
            "balance": str(self.balance),
        }


@dataclass(frozen=True)
class Charge:
    """Une écriture passée : le payeur doit, le bénéficiaire est dû."""

    payer: str
    payee: str
    amount: Decimal
    currency: str
    resource: str
    nonce: str
    at: float

    def to_dict(self) -> dict:
        return {
            "payer": self.payer, "payee": self.payee,
            "amount": str(self.amount), "currency": self.currency,
            "resource": self.resource, "nonce": self.nonce, "at": self.at,
        }


class Ledger:
    """Comptes, écritures et journal scellé. Sans effet de bord externe."""

    def __init__(self, currency: str = "USD", entries: Optional[List[dict]] = None,
                 on_change: Optional[Callable[["Ledger"], None]] = None):
        """`on_change` est appelé après chaque mutation.

        C'est ce qui permet au relais de persister une écriture passée par
        un serveur tiers. Sans ce crochet, seules les opérations traversant
        le relais étaient sauvegardées : une requête payée disparaissait au
        redémarrage, et le compte repartait à zéro.
        """
        self.currency = currency
        self._accounts: Dict[str, Account] = {}
        self._charges: List[Charge] = []
        self._seen_nonces: set[str] = set()
        self.audit = ImmutableAuditLog(entries=entries)
        self.on_change = on_change

    # ------------------------------------------------------------------
    # Comptes
    # ------------------------------------------------------------------

    def open_account(self, agent_id: str,
                     credit_limit: str | Price = DEFAULT_CREDIT_LIMIT) -> Account:
        """Ouvre un compte, ou renvoie celui qui existe déjà.

        Idempotent volontairement : un relais qui redémarre ne doit pas
        échouer parce qu'un compte est déjà là.
        """
        if agent_id in self._accounts:
            return self._accounts[agent_id]

        limit = parse_price(credit_limit, default_currency=self.currency)
        self._require_currency(limit.currency)

        account = Account(agent_id=agent_id, currency=self.currency,
                          credit_limit=limit.amount, balance=Decimal("0"))
        self._accounts[agent_id] = account
        self.audit.log("ACCOUNT_OPENED", sender=agent_id,
                       metadata={"credit_limit": str(limit.amount),
                                 "currency": self.currency})
        self._changed()
        return account

    def account(self, agent_id: str) -> Account:
        try:
            return self._accounts[agent_id]
        except KeyError:
            raise UnknownAccount(f"aucun compte ouvert pour '{agent_id}'") from None

    def balance(self, agent_id: str) -> Price:
        return Price(self.account(agent_id).balance, self.currency)

    # ------------------------------------------------------------------
    # Écritures
    # ------------------------------------------------------------------

    def charge(self, proof: PaymentProof, now: Optional[float] = None) -> Charge:
        """Passe l'écriture correspondant à une preuve vérifiée.

        La signature doit avoir été validée **avant** — `verify_proof` dit
        que la preuve est authentique, `charge` dit qu'elle est recevable.
        Les deux questions sont distinctes et méritent deux appels.
        """
        if proof.nonce in self._seen_nonces:
            raise DuplicateNonce(
                f"nonce '{proof.nonce}' déjà honoré — preuve rejouée")

        amount = parse_price(f"{proof.amount} {proof.currency}")
        self._require_currency(amount.currency)
        if amount.amount <= 0:
            raise LedgerError("une écriture nulle ou négative n'a pas de sens")

        payer = self.account(proof.payer)
        payee = self.account(proof.pay_to)

        if amount.amount > payer.available:
            raise CreditLimitExceeded(
                f"'{payer.agent_id}' est à {payer.balance} {self.currency} avec "
                f"un plafond de {payer.credit_limit} : il reste "
                f"{payer.available}, la requête en demande {amount.amount}"
            )

        self._accounts[payer.agent_id] = Account(
            payer.agent_id, payer.currency, payer.credit_limit,
            quantize(payer.balance - amount.amount))
        self._accounts[payee.agent_id] = Account(
            payee.agent_id, payee.currency, payee.credit_limit,
            quantize(payee.balance + amount.amount))

        charge = Charge(payer=proof.payer, payee=proof.pay_to,
                        amount=amount.amount, currency=self.currency,
                        resource=proof.resource, nonce=proof.nonce,
                        at=now if now is not None else time.time())
        self._charges.append(charge)
        self._seen_nonces.add(proof.nonce)
        self.audit.log("CHARGE", sender=proof.payer, target=proof.pay_to,
                       metadata=charge.to_dict())
        self._changed()
        return charge

    def settle(self, agent_id: str, amount: str | Price) -> Account:
        """Enregistre un règlement reçu hors bande (virement, facture payée)."""
        received = parse_price(amount, default_currency=self.currency)
        self._require_currency(received.currency)
        if received.amount <= 0:
            raise LedgerError("un règlement doit être positif")

        account = self.account(agent_id)
        updated = Account(account.agent_id, account.currency, account.credit_limit,
                          quantize(account.balance + received.amount))
        self._accounts[agent_id] = updated
        self.audit.log("SETTLEMENT", sender=agent_id,
                       metadata={"amount": str(received.amount),
                                 "currency": self.currency,
                                 "balance": str(updated.balance)})
        self._changed()
        return updated

    # ------------------------------------------------------------------
    # Relevés
    # ------------------------------------------------------------------

    def statement(self, agent_id: str, since: Optional[float] = None,
                  until: Optional[float] = None) -> List[Charge]:
        """Les écritures où l'agent apparaît — la matière d'une facture."""
        return [c for c in self._charges
                if (c.payer == agent_id or c.payee == agent_id)
                and (since is None or c.at >= since)
                and (until is None or c.at < until)]

    def total_owed(self, agent_id: str, since: Optional[float] = None,
                   until: Optional[float] = None) -> Price:
        """Ce que l'agent doit sur la période, hors règlements."""
        total = sum((c.amount for c in self.statement(agent_id, since, until)
                     if c.payer == agent_id), Decimal("0"))
        return Price(quantize(total), self.currency)

    def verify_integrity(self) -> bool:
        """Le journal n'a pas été réécrit depuis sa création."""
        return self.audit.verify_integrity()

    # ------------------------------------------------------------------

    def export_state(self) -> dict:
        return {
            "currency": self.currency,
            "accounts": [a.to_dict() for a in self._accounts.values()],
            "charges": [c.to_dict() for c in self._charges],
            "audit": [e.to_dict() for e in self.audit.chain],
        }

    @classmethod
    def import_state(cls, state: dict) -> "Ledger":
        ledger = cls(currency=state.get("currency", "USD"),
                     entries=state.get("audit"))
        for row in state.get("accounts", []):
            ledger._accounts[row["agent_id"]] = Account(
                agent_id=row["agent_id"], currency=row["currency"],
                credit_limit=Decimal(row["credit_limit"]),
                balance=Decimal(row["balance"]))
        for row in state.get("charges", []):
            ledger._charges.append(Charge(
                payer=row["payer"], payee=row["payee"],
                amount=Decimal(row["amount"]), currency=row["currency"],
                resource=row["resource"], nonce=row["nonce"], at=row["at"]))
            ledger._seen_nonces.add(row["nonce"])
        return ledger

    def _changed(self) -> None:
        if self.on_change:
            self.on_change(self)

    def _require_currency(self, currency: str) -> None:
        if currency != self.currency:
            raise LedgerError(
                f"ce registre tient ses comptes en {self.currency}, "
                f"écriture en {currency} refusée")
