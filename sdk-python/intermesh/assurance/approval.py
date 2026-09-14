"""Approbation humaine : le chemin entre « bloqué » et « autorisé ».

Une action classée `approval` n'est pas exécutée et produit une preuve
d'attente. Un humain examine cette preuve, l'approuve, et l'agent rejoue
son appel en présentant le jeton d'approbation.

Trois propriétés dictent la forme de ce module, et chacune répond à une
manière précise de contourner l'approbation :

* **l'approbation nomme son action.** Elle enregistre la méthode et la
  cible exactes de la preuve approuvée. Sans cela, un feu vert donné pour
  un virement de 100 € servirait à supprimer une base ;
* **elle ne sert qu'une fois.** Une approbation réutilisable est une
  autorisation permanente déguisée ;
* **elle expire.** Un accord donné mardi ne doit pas ouvrir la porte le
  mois suivant.

Ce module ne décide de rien : il enregistre ce qu'un humain a décidé. Le
circuit de validation — qui approuve, par quel canal, avec quelle
authentification — est délibérément hors du MVP.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ..payments.clock import now_ms

HEADER = "X-InterMesh-Approval"
DEFAULT_TTL_MS = 3_600_000  # une heure


class ApprovalError(ValueError):
    """Approbation absente, périmée, déjà consommée, ou d'une autre action."""


@dataclass
class Approval:
    action_id: str
    method: str
    target: str
    approved_by: str
    approved_at: int
    expires_at: int
    used_at: Optional[int] = None

    @property
    def spent(self) -> bool:
        return self.used_at is not None

    def is_expired(self, now: Optional[int] = None) -> bool:
        return (now if now is not None else now_ms()) > self.expires_at

    def to_dict(self) -> dict:
        return {"action_id": self.action_id, "method": self.method,
                "target": self.target, "approved_by": self.approved_by,
                "approved_at": self.approved_at, "expires_at": self.expires_at,
                "used_at": self.used_at}

    @classmethod
    def from_dict(cls, raw: dict) -> "Approval":
        return cls(action_id=str(raw["action_id"]), method=str(raw["method"]),
                   target=str(raw["target"]), approved_by=str(raw["approved_by"]),
                   approved_at=int(raw["approved_at"]),
                   expires_at=int(raw["expires_at"]),
                   used_at=raw.get("used_at"))


class ApprovalStore:
    """Les approbations accordées, sur disque pour survivre au redémarrage."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self._lock = threading.RLock()
        self._approvals: Dict[str, Approval] = {}
        if self.path and self.path.is_file():
            for raw in json.loads(self.path.read_text(encoding="utf-8")):
                approval = Approval.from_dict(raw)
                self._approvals[approval.action_id] = approval

    def grant(self, action_id: str, method: str, target: str,
              approved_by: str, ttl_ms: int = DEFAULT_TTL_MS) -> Approval:
        with self._lock:
            now = now_ms()
            approval = Approval(action_id=action_id, method=method.upper(),
                                target=target, approved_by=approved_by,
                                approved_at=now, expires_at=now + ttl_ms)
            self._approvals[action_id] = approval
            self._save()
        return approval

    def consume(self, action_id: str, method: str, target: str,
                now: Optional[int] = None) -> Approval:
        """Valide et brûle une approbation, ou explique le refus."""
        with self._lock:
            approval = self._approvals.get(action_id)
            if approval is None:
                raise ApprovalError(
                    f"aucune approbation pour '{action_id}' — cette action "
                    "n'a pas été validée")
            if approval.spent:
                raise ApprovalError(
                    f"approbation '{action_id}' déjà utilisée — une "
                    "approbation ne vaut que pour un seul rejeu")
            if approval.is_expired(now):
                raise ApprovalError(f"approbation '{action_id}' périmée")
            if approval.method != method.upper() or approval.target != target:
                # La tentative évidente : faire valider une action anodine
                # puis rejouer le jeton sur une action destructrice.
                raise ApprovalError(
                    f"approbation accordée pour {approval.method} "
                    f"{approval.target}, présentée pour {method.upper()} {target}")

            approval.used_at = now if now is not None else now_ms()
            self._save()
            return approval

    def get(self, action_id: str) -> Optional[Approval]:
        return self._approvals.get(action_id)

    def __len__(self) -> int:
        return len(self._approvals)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.to_dict() for a in self._approvals.values()]
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.path)
        self.path.chmod(0o600)
