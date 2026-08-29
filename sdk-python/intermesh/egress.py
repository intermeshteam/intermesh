"""
Filtrage de sortie : ce qu'une organisation accepte de laisser franchir
sa frontière.

L'isolement multi-tenant, le pairage explicite et la signature Ed25519
répondent à « qui parle à qui ». Ils ne disent rien de « ce qui sort » :
une fois le lien de fédération établi, un agent peut transmettre à un
partenaire n'importe quel contenu auquel il a accès. C'est le manque que
ce module comble.

Deux points d'application, parce qu'ils ne voient pas la même chose :

  * L'agent émetteur (SDK), avant chiffrement. C'est le seul endroit où le
    contenu est en clair sur le chemin nominal, donc le seul filtre qui
    morde réellement quand le chiffrement E2E est actif.
  * Le Hub, au moment de relayer vers un pair. Il ne voit que ce qui n'est
    pas chiffré, mais il applique la politique même à un agent qui ne
    l'aurait pas fait — un agent est du code, pas une autorité.

Ni l'un ni l'autre ne protège d'un agent interne malveillant qui
chiffrerait lui-même avant l'envoi. Le filtre d'egress traite la fuite
par négligence, pas l'exfiltration délibérée.

Politique vide par défaut : rien n'est filtré tant que rien n'est déclaré.
Caviarder en silence serait pire que ne pas filtrer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REDACT = "redact"
DROP = "drop"
BLOCK = "block"
ACTIONS = (REDACT, DROP, BLOCK)

DEFAULT_REPLACEMENT = "[REDACTED]"
ANY_ORG = "*"


class EgressBlocked(PermissionError):
    """Le contenu contient quelque chose qui ne doit pas franchir la frontière."""

    def __init__(self, rule_name: str, target_org: str):
        self.rule_name = rule_name
        self.target_org = target_org
        super().__init__(
            f"EGRESS_BLOCKED: la règle '{rule_name}' interdit d'envoyer ce contenu "
            f"à l'organisation '{target_org}'."
        )


@dataclass
class EgressRule:
    """Une règle de sortie.

    `action` :
      - `redact` : remplace les portions de texte correspondant à `pattern`.
      - `drop`   : supprime toute clé nommée `field` (à n'importe quelle
                   profondeur), quelle que soit sa valeur.
      - `block`  : refuse l'envoi entier si `pattern` apparaît.

    `to_orgs` restreint la règle à certaines organisations destinataires ;
    `["*"]` l'applique à toute sortie hors de l'organisation.
    """

    name: str
    action: str
    pattern: str | None = None
    field_name: str | None = None
    replacement: str = DEFAULT_REPLACEMENT
    to_orgs: list[str] = field(default_factory=lambda: [ANY_ORG])

    def __post_init__(self):
        if self.action not in ACTIONS:
            raise ValueError(f"action inconnue : {self.action!r} (attendu {ACTIONS})")
        if self.action in (REDACT, BLOCK) and not self.pattern:
            raise ValueError(f"règle '{self.name}' : action {self.action} exige un `pattern`")
        if self.action == DROP and not self.field_name:
            raise ValueError(f"règle '{self.name}' : action drop exige un `field`")
        self._compiled = re.compile(self.pattern, re.IGNORECASE) if self.pattern else None

    def applies_to(self, target_org: str) -> bool:
        return ANY_ORG in self.to_orgs or target_org in self.to_orgs

    @classmethod
    def from_dict(cls, raw: dict) -> "EgressRule":
        return cls(
            name=raw["name"],
            action=raw["action"],
            pattern=raw.get("pattern"),
            field_name=raw.get("field"),
            replacement=raw.get("replacement", DEFAULT_REPLACEMENT),
            to_orgs=raw.get("to_orgs", [ANY_ORG]),
        )


@dataclass
class EgressPolicy:
    name: str = "empty"
    rules: list[EgressRule] = field(default_factory=list)

    def rules_for(self, target_org: str) -> list[EgressRule]:
        return [r for r in self.rules if r.applies_to(target_org)]

    @property
    def is_empty(self) -> bool:
        return not self.rules

    @classmethod
    def from_dict(cls, raw: dict) -> "EgressPolicy":
        return cls(
            name=raw.get("name", "unnamed"),
            rules=[EgressRule.from_dict(r) for r in raw.get("rules", [])],
        )

    @classmethod
    def load(cls, path: str | Path) -> "EgressPolicy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def apply_egress(payload: Any, target_org: str, policy: EgressPolicy | None
                 ) -> tuple[Any, list[str]]:
    """Applique la politique de sortie à `payload`.

    Retourne le contenu filtré et la liste des noms de règles déclenchées —
    des *noms*, jamais les valeurs retirées : un journal d'audit ne doit pas
    devenir l'endroit où fuit ce qu'on vient de caviarder.

    Raises:
        EgressBlocked: si une règle `block` correspond.
    """
    if policy is None or policy.is_empty:
        return payload, []

    rules = policy.rules_for(target_org)
    if not rules:
        return payload, []

    triggered: list[str] = []

    def visit(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for key, value in node.items():
                dropped = False
                for rule in rules:
                    if rule.action == DROP and key.lower() == rule.field_name.lower():
                        if rule.name not in triggered:
                            triggered.append(rule.name)
                        dropped = True
                        break
                if not dropped:
                    out[key] = visit(value)
            return out

        if isinstance(node, list):
            return [visit(item) for item in node]

        if isinstance(node, str):
            text = node
            for rule in rules:
                if rule.action == BLOCK and rule._compiled.search(text):
                    raise EgressBlocked(rule.name, target_org)
            for rule in rules:
                if rule.action == REDACT:
                    replaced, count = rule._compiled.subn(rule.replacement, text)
                    if count:
                        text = replaced
                        if rule.name not in triggered:
                            triggered.append(rule.name)
            return text

        return node

    return visit(payload), triggered
