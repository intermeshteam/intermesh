"""Les six niveaux de risque, et ce qu'ils veulent dire.

L'échelle est volontairement grossière. Un score sur cent donnerait une
illusion de précision qu'aucune donnée ne justifie aujourd'hui : personne
ne sait dire si une action vaut 71 ou 78. Six paliers, en revanche, se
discutent avec un responsable conformité — et c'est cette conversation-là
qui compte, pas la décimale.

Le principe qui gouverne le classement n'est pas « est-ce grave » mais
**« est-ce réversible, et par qui »**. Une suppression de données est plus
haute qu'un virement, parce qu'un virement se conteste et qu'une base
détruite ne revient pas.

Le seuil de preuve est configurable, mais sa valeur par défaut dit la
thèse du produit : à partir de R2, une action laisse une trace signée.
"""

from __future__ import annotations

from enum import IntEnum


class RiskLevel(IntEnum):
    """R0 à R5. Comparable : `level >= RiskLevel.R3` a du sens."""

    R0 = 0  # sans conséquence — lecture publique
    R1 = 1  # réversible, faible impact
    R2 = 2  # impact métier significatif
    R3 = 3  # sensible — données confidentielles, ressource protégée
    R4 = 4  # critique — mouvement financier, infrastructure
    R5 = 5  # potentiellement catastrophique — destruction, système physique

    @classmethod
    def parse(cls, raw: "str | int | RiskLevel") -> "RiskLevel":
        if isinstance(raw, RiskLevel):
            return raw
        text = str(raw).strip().upper()
        digits = text[1:] if text.startswith("R") else text
        # Un `cls(9)` nu remonterait « 9 is not a valid RiskLevel », message
        # de l'énumération Python qui ne dit pas ce qui était attendu.
        if digits.isdigit() and 0 <= int(digits) <= 5:
            return cls(int(digits))
        raise ValueError(f"niveau de risque illisible : {raw!r} (attendu R0 à R5)")

    def __str__(self) -> str:
        return f"R{self.value}"


# Ce qu'un humain lit dans un rapport d'incident.
DESCRIPTIONS = {
    RiskLevel.R0: "sans conséquence notable",
    RiskLevel.R1: "réversible, faible impact",
    RiskLevel.R2: "impact métier significatif",
    RiskLevel.R3: "sensible — données confidentielles ou ressource protégée",
    RiskLevel.R4: "critique — financier, infrastructure, destruction partielle",
    RiskLevel.R5: "potentiellement catastrophique — irréversible ou physique",
}

# À partir d'ici, une action laisse une preuve. C'est la thèse du produit,
# exprimée en une constante : en dessous, du bruit ; au-dessus, une trace
# que quelqu'un pourra opposer à quelqu'un d'autre.
DEFAULT_EVIDENCE_THRESHOLD = RiskLevel.R2
