"""
Nexus Escrow — séquestre inter-organisations pour les tâches payantes.

Portée volontairement limitée : ceci est le PROTOCOLE (états, règles,
traçabilité), pas une passerelle de paiement. Le `SimulatedLedger` tient des
soldes en mémoire, alimentés uniquement par `grant()` (un robinet de test/démo,
jamais une vraie source de fonds). Brancher un vrai mouvement d'argent (Stripe
Connect, stablecoins...) suppose de remplacer `SimulatedLedger` par un backend
qui parle à un processeur de paiement réel, en respectant la même interface
(`debit`/`credit`/`balance`) — volontairement pas fourni ici.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class EscrowError(Exception):
    """Séquestre impossible ou opération invalide sur un séquestre existant."""


class InsufficientFundsError(EscrowError):
    """Solde insuffisant pour couvrir le montant demandé."""


class EscrowStatus(str, Enum):
    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"


@dataclass
class EscrowHold:
    hold_id: str
    task_id: str
    payer_org: str
    payee_org: str
    amount: float
    currency: str
    status: EscrowStatus
    auto_release: bool
    created_at: float
    resolved_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "hold_id": self.hold_id,
            "task_id": self.task_id,
            "payer_org": self.payer_org,
            "payee_org": self.payee_org,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value,
            "auto_release": self.auto_release,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }


class SimulatedLedger:
    """
    Soldes en mémoire, par (organisation, devise).

    `grant()` est le seul moyen de créer des fonds : un robinet explicite de
    démonstration/test, jamais une source de vérité financière. Aucune
    écriture ici ne représente un mouvement d'argent réel.
    """

    def __init__(self):
        self._balances: Dict[Tuple[str, str], float] = {}

    def balance(self, org_id: str, currency: str = "USD") -> float:
        return self._balances.get((org_id, currency), 0.0)

    def grant(self, org_id: str, amount: float, currency: str = "USD") -> float:
        if amount <= 0:
            raise EscrowError("Le montant crédité doit être positif.")
        key = (org_id, currency)
        self._balances[key] = self._balances.get(key, 0.0) + amount
        return self._balances[key]

    def debit(self, org_id: str, amount: float, currency: str = "USD") -> bool:
        """Retourne False sans rien modifier si le solde est insuffisant."""
        key = (org_id, currency)
        current = self._balances.get(key, 0.0)
        if current < amount:
            return False
        self._balances[key] = current - amount
        return True

    def credit(self, org_id: str, amount: float, currency: str = "USD") -> float:
        key = (org_id, currency)
        self._balances[key] = self._balances.get(key, 0.0) + amount
        return self._balances[key]

    def export_state(self) -> List[dict]:
        """Soldes sérialisables — le tuple (org, devise) ne survit pas à JSON."""
        return [
            {"org_id": org, "currency": currency, "amount": amount}
            for (org, currency), amount in sorted(self._balances.items())
        ]

    def import_state(self, rows: List[dict]) -> None:
        """Remplace intégralement les soldes."""
        self._balances = {
            (r["org_id"], r["currency"]): float(r["amount"]) for r in rows
        }


class EscrowManager:
    """Un séquestre par tâche : créé à la soumission, résolu à l'issue de la tâche."""

    def __init__(self, ledger: Optional[SimulatedLedger] = None):
        self.ledger = ledger or SimulatedLedger()
        self._holds: Dict[str, EscrowHold] = {}  # task_id -> EscrowHold

    def create_hold(
        self,
        task_id: str,
        payer_org: str,
        payee_org: str,
        amount: float,
        currency: str = "USD",
        auto_release: bool = True,
        metadata: Optional[dict] = None,
    ) -> EscrowHold:
        if not task_id:
            raise EscrowError("task_id requis pour créer un séquestre.")
        if amount <= 0:
            raise EscrowError("Le montant séquestré doit être positif.")
        if task_id in self._holds:
            raise EscrowError(f"Un séquestre existe déjà pour la tâche '{task_id}'.")

        if not self.ledger.debit(payer_org, amount, currency):
            balance = self.ledger.balance(payer_org, currency)
            raise InsufficientFundsError(
                f"ESCROW_INSUFFICIENT_FUNDS: '{payer_org}' a {balance:.2f} {currency}, "
                f"{amount:.2f} {currency} requis."
            )

        hold = EscrowHold(
            hold_id=str(uuid.uuid4()), task_id=task_id, payer_org=payer_org, payee_org=payee_org,
            amount=amount, currency=currency, status=EscrowStatus.HELD, auto_release=auto_release,
            created_at=time.time(), metadata=metadata or {},
        )
        self._holds[task_id] = hold
        return hold

    def get(self, task_id: str) -> Optional[EscrowHold]:
        return self._holds.get(task_id)

    def list_holds(self, org_id: Optional[str] = None) -> List[EscrowHold]:
        holds = list(self._holds.values())
        if org_id:
            holds = [h for h in holds if org_id in (h.payer_org, h.payee_org)]
        return holds

    def release(self, task_id: str) -> EscrowHold:
        """Débloque les fonds vers le bénéficiaire (tâche livrée avec succès)."""
        hold = self._require_held(task_id)
        self.ledger.credit(hold.payee_org, hold.amount, hold.currency)
        hold.status = EscrowStatus.RELEASED
        hold.resolved_at = time.time()
        return hold

    def refund(self, task_id: str) -> EscrowHold:
        """Rend les fonds au payeur (tâche échouée, annulée, ou litige tranché en sa faveur)."""
        hold = self._require_held(task_id)
        self.ledger.credit(hold.payer_org, hold.amount, hold.currency)
        hold.status = EscrowStatus.REFUNDED
        hold.resolved_at = time.time()
        return hold

    def export_state(self) -> dict:
        """Séquestres et soldes, pour un instantané du Hub."""
        return {
            "ledger": self.ledger.export_state(),
            "holds": [h.to_dict() for h in self._holds.values()],
        }

    def import_state(self, state: dict) -> None:
        """Remplace intégralement séquestres et soldes."""
        self.ledger.import_state(state.get("ledger") or [])
        self._holds = {}
        for raw in state.get("holds") or []:
            hold = EscrowHold(
                hold_id=raw["hold_id"], task_id=raw["task_id"],
                payer_org=raw["payer_org"], payee_org=raw["payee_org"],
                amount=float(raw["amount"]), currency=raw["currency"],
                status=EscrowStatus(raw["status"]), auto_release=bool(raw["auto_release"]),
                created_at=float(raw["created_at"]), resolved_at=raw.get("resolved_at"),
                metadata=raw.get("metadata") or {},
            )
            self._holds[hold.task_id] = hold

    def _require_held(self, task_id: str) -> EscrowHold:
        hold = self._holds.get(task_id)
        if hold is None:
            raise EscrowError(f"Aucun séquestre pour la tâche '{task_id}'.")
        if hold.status != EscrowStatus.HELD:
            raise EscrowError(f"Séquestre déjà résolu ({hold.status.value}).")
        return hold
