"""Le moteur de politique : quelle règle s'applique, et que décide-t-elle.

La mécanique reprend celle d'`approval.py`, éprouvée sur les tâches : des
critères qui **se cumulent** — tous doivent correspondre — et une première
règle gagnante. Deux choix qui méritent d'être défendus :

* **première règle gagnante, pas la plus spécifique.** Un moteur qui
  « choisit la meilleure règle » devient impossible à raisonner dès la
  vingtième ligne. L'ordre du fichier est l'ordre d'évaluation : ce que
  l'auteur lit est ce que le moteur fait.
* **refus par défaut de l'ambiguïté, pas de l'action.** Une requête qui ne
  correspond à aucune règle tombe sur le `default` du fichier. Ce défaut
  est obligatoire : laisser le moteur choisir à la place de l'opérateur
  serait décider de sa politique de sécurité à sa place.

Une règle sans critère est refusée au chargement. Le cas probable n'est
pas qu'on veuille tout bloquer, c'est qu'on ait oublié de la remplir — et
une politique qui bloque tout par distraction est un incident.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from .risk import DEFAULT_EVIDENCE_THRESHOLD, RiskLevel

ALLOW, BLOCK, APPROVAL = "allow", "block", "approval"
DECISIONS = (ALLOW, BLOCK, APPROVAL)


class PolicyError(ValueError):
    """Politique illisible, incohérente ou vide."""


@dataclass
class Rule:
    """Un critère composé, et ce qu'il décide."""

    name: str
    risk: RiskLevel
    decision: str
    method: Optional[str] = None
    host: Optional[str] = None
    path_contains: Optional[str] = None
    path_regex: Optional[str] = None
    reason: str = ""

    def __post_init__(self):
        if not self.name:
            raise PolicyError("une règle doit avoir un `name`")
        if self.decision not in DECISIONS:
            raise PolicyError(
                f"règle '{self.name}' : décision '{self.decision}' inconnue "
                f"(attendu {', '.join(DECISIONS)})")
        if not any((self.method, self.host, self.path_contains, self.path_regex)):
            raise PolicyError(
                f"règle '{self.name}' : aucun critère. Une règle vide "
                "s'appliquerait à tout — c'est presque toujours un oubli.")
        if self.path_regex:
            try:
                self._compiled = re.compile(self.path_regex)
            except re.error as exc:
                raise PolicyError(
                    f"règle '{self.name}' : expression régulière invalide — {exc}"
                ) from None
        else:
            self._compiled = None

    def matches(self, method: str, host: str, path: str) -> bool:
        if self.method and self.method.upper() != method.upper():
            return False
        if self.host and self.host.lower() not in host.lower():
            return False
        if self.path_contains and self.path_contains not in path:
            return False
        if self._compiled and not self._compiled.search(path):
            return False
        return True

    @classmethod
    def from_dict(cls, raw: dict) -> "Rule":
        match = raw.get("match") or {}
        if not isinstance(match, dict):
            raise PolicyError(f"règle '{raw.get('name')}' : `match` doit être un objet")
        try:
            risk = RiskLevel.parse(raw.get("risk", "R0"))
        except ValueError as exc:
            raise PolicyError(f"règle '{raw.get('name')}' : {exc}") from None
        return cls(
            name=str(raw.get("name", "")),
            risk=risk,
            decision=str(raw.get("decision", ALLOW)).lower(),
            method=match.get("method"),
            host=match.get("host"),
            path_contains=match.get("path_contains"),
            path_regex=match.get("path_regex"),
            reason=str(raw.get("reason", "")),
        )


@dataclass
class Verdict:
    """Ce que le proxy applique, et ce que la preuve enregistre."""

    decision: str
    risk: RiskLevel
    rule: str
    reason: str = ""

    @property
    def needs_evidence_default(self) -> bool:
        return self.risk >= DEFAULT_EVIDENCE_THRESHOLD


@dataclass
class Policy:
    """Un jeu de règles ordonné, plus un comportement par défaut."""

    name: str
    rules: List[Rule] = field(default_factory=list)
    default_decision: str = BLOCK
    default_risk: RiskLevel = RiskLevel.R3
    evidence_threshold: RiskLevel = DEFAULT_EVIDENCE_THRESHOLD

    def evaluate(self, method: str, url: str) -> Verdict:
        """Première règle qui correspond ; sinon le défaut déclaré."""
        parts = urlsplit(url if "//" in url else f"//{url}")
        host = parts.netloc or ""
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"

        for rule in self.rules:
            if rule.matches(method, host, path):
                return Verdict(rule.decision, rule.risk, rule.name, rule.reason)

        return Verdict(self.default_decision, self.default_risk, "default",
                       "aucune règle ne correspond")

    def requires_evidence(self, risk: RiskLevel) -> bool:
        return risk >= self.evidence_threshold

    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, raw: dict) -> "Policy":
        if not isinstance(raw, dict):
            raise PolicyError("la politique doit être un objet")

        rules_raw = raw.get("rules")
        if not isinstance(rules_raw, list) or not rules_raw:
            raise PolicyError("la politique doit contenir au moins une règle")

        default = raw.get("default") or {}
        decision = str(default.get("decision", BLOCK)).lower()
        if decision not in DECISIONS:
            raise PolicyError(f"décision par défaut inconnue : {decision!r}")

        try:
            default_risk = RiskLevel.parse(default.get("risk", "R3"))
            threshold = RiskLevel.parse(
                raw.get("evidence_threshold", str(DEFAULT_EVIDENCE_THRESHOLD)))
        except ValueError as exc:
            raise PolicyError(str(exc)) from None

        policy = cls(name=str(raw.get("name", "sans-nom")),
                     rules=[Rule.from_dict(r) for r in rules_raw],
                     default_decision=decision, default_risk=default_risk,
                     evidence_threshold=threshold)

        seen = set()
        for rule in policy.rules:
            if rule.name in seen:
                raise PolicyError(
                    f"deux règles portent le nom '{rule.name}' — la seconde "
                    "serait invisible dans les preuves")
            seen.add(rule.name)
        return policy

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        file = Path(path)
        if not file.is_file():
            raise PolicyError(f"politique introuvable : {file}")

        text = file.read_text(encoding="utf-8")
        if file.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as exc:
                raise PolicyError(
                    "lire une politique YAML demande PyYAML : "
                    "pip install 'intermesh[assurance]' — ou utilisez du JSON"
                ) from exc
            try:
                raw = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise PolicyError(f"YAML invalide dans {file} : {exc}") from None
        else:
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise PolicyError(f"JSON invalide dans {file} : {exc}") from None

        policy = cls.from_dict(raw)
        if policy.name == "sans-nom":
            policy.name = file.stem
        return policy

    def fingerprint(self) -> str:
        """Identifie la version exacte de politique citée par une preuve.

        Sans cela, « policy: finance-v1 » ne prouve rien : le fichier a pu
        changer entre l'action et l'audit.
        """
        from ..canonical import canonical_hash

        return canonical_hash({
            "name": self.name,
            "default": [self.default_decision, int(self.default_risk)],
            "threshold": int(self.evidence_threshold),
            "rules": [[r.name, int(r.risk), r.decision, r.method or "",
                       r.host or "", r.path_contains or "", r.path_regex or ""]
                      for r in self.rules],
        })[:16]

    def version_label(self) -> str:
        return f"{self.name}@{self.fingerprint()}"
