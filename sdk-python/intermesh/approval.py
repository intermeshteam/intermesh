"""
Validation humaine : les tâches qu'un agent n'a pas le droit de lancer seul.

Les garde-fous Asimov répondent à « cette tâche est-elle légitime ? » et
refusent celles qui ne le sont pas. Ils ne répondent pas à « celle-ci est
légitime, mais quelqu'un doit-il la regarder avant ? ». Signer un contrat,
virer de l'argent, supprimer une base : ce sont des actions qu'un agent
peut vouloir légitimement, et qu'une organisation veut néanmoins tenir
sous décision humaine.

C'est la différence entre un refus et une suspension. Une règle qui
correspond ici ne rejette rien : elle met la tâche en attente jusqu'à ce
qu'une personne tranche.

Politique vide par défaut. Rien n'est suspendu tant que rien n'est
déclaré — un système qui met en attente ce qu'on ne lui a pas demandé de
retenir est un système qu'on désactive.

Portée : ce module décide *si* une tâche doit être approuvée. Il ne dit
rien de *qui* approuve — cette autorisation relève des rôles admin, au
même titre que les autres commandes d'administration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ANY = "*"


@dataclass
class ApprovalRule:
    """Une règle de mise en attente.

    Tous les critères renseignés doivent correspondre — ils se cumulent au
    lieu de s'additionner. Une règle sans aucun critère correspondrait à
    toutes les tâches, ce que `__post_init__` refuse : le plus probable est
    qu'on ait oublié de la remplir, pas qu'on veuille tout suspendre.

    `reason` n'est pas décoratif : c'est le texte que lit la personne à qui
    l'on demande de trancher. Sans lui, elle voit une tâche en attente sans
    savoir ce qui l'y a mise.
    """

    name: str
    reason: str
    assignees: list[str] = field(default_factory=lambda: [ANY])
    capabilities: list[str] = field(default_factory=lambda: [ANY])
    pattern: str | None = None
    min_cost: float | None = None
    cross_org_only: bool = False

    def __post_init__(self):
        if not self.name:
            raise ValueError("une règle d'approbation doit avoir un `name`")
        if not self.reason:
            raise ValueError(f"règle '{self.name}' : `reason` est obligatoire — "
                             "c'est ce que lit la personne qui approuve")
        specific = (
            self.assignees != [ANY]
            or self.capabilities != [ANY]
            or self.pattern is not None
            or self.min_cost is not None
            or self.cross_org_only
        )
        if not specific:
            raise ValueError(
                f"règle '{self.name}' : aucun critère, elle suspendrait toutes les "
                "tâches. Précisez au moins assignees, capabilities, pattern, "
                "min_cost ou cross_org_only."
            )
        self._compiled = re.compile(self.pattern, re.IGNORECASE) if self.pattern else None

    def matches(
        self,
        assignee: str,
        capabilities: list[str],
        payload_text: str,
        estimated_cost: float,
        is_cross_org: bool,
    ) -> bool:
        if self.cross_org_only and not is_cross_org:
            return False
        if self.assignees != [ANY] and assignee not in self.assignees:
            return False
        if self.capabilities != [ANY] and not any(c in self.capabilities for c in capabilities):
            return False
        if self.min_cost is not None and estimated_cost < self.min_cost:
            return False
        if self._compiled is not None and not self._compiled.search(payload_text or ""):
            return False
        return True

    @classmethod
    def from_dict(cls, raw: dict) -> "ApprovalRule":
        return cls(
            name=raw["name"],
            reason=raw["reason"],
            assignees=raw.get("assignees", [ANY]),
            capabilities=raw.get("capabilities", [ANY]),
            pattern=raw.get("pattern"),
            min_cost=raw.get("min_cost"),
            cross_org_only=bool(raw.get("cross_org_only", False)),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "reason": self.reason,
            "assignees": self.assignees,
            "capabilities": self.capabilities,
            "pattern": self.pattern,
            "min_cost": self.min_cost,
            "cross_org_only": self.cross_org_only,
        }


@dataclass
class ApprovalPolicy:
    name: str = "empty"
    rules: list[ApprovalRule] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.rules

    @classmethod
    def from_dict(cls, raw: dict) -> "ApprovalPolicy":
        return cls(
            name=raw.get("name", "unnamed"),
            rules=[ApprovalRule.from_dict(r) for r in raw.get("rules", [])],
        )

    def to_dict(self) -> dict:
        return {"name": self.name, "rules": [r.to_dict() for r in self.rules]}

    @classmethod
    def load(cls, path: str | Path) -> "ApprovalPolicy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _payload_text(task: dict) -> str:
    """Texte sur lequel `pattern` est évalué.

    Le titre et les données d'entrée sont concaténés : une règle qui
    cherche « contrat » doit correspondre que le mot soit dans l'intitulé
    ou dans la charge utile.
    """
    parts = [str(task.get("title") or "")]
    data = task.get("input_data")
    if data is not None:
        parts.append(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))
    return "\n".join(parts)


def requires_approval(
    task: dict,
    policy: ApprovalPolicy | None,
    *,
    capabilities: list[str] | None = None,
    is_cross_org: bool = False,
) -> ApprovalRule | None:
    """Retourne la première règle qui met cette tâche en attente, sinon None.

    La première suffit : une tâche est suspendue ou ne l'est pas, et c'est
    le motif de cette règle qui sera montré à la personne qui tranche.
    """
    if policy is None or policy.is_empty:
        return None

    assignee = str(task.get("assignee") or "")
    try:
        cost = float(task.get("estimated_cost") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    text = _payload_text(task)
    caps = capabilities or []

    for rule in policy.rules:
        if rule.matches(assignee, caps, text, cost, is_cross_org):
            return rule
    return None
