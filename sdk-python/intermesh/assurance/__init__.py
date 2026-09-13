"""InterMesh Assurance — intercepter, classer, décider, prouver.

    Toute action autonome critique doit être autorisée, contrôlée
    et prouvable.

Quatre briques, dans l'ordre où une action les traverse :

* `risk`     — R0 à R5, l'échelle de gravité
* `policy`   — quelle règle s'applique, et que décide-t-elle
* `proxy`    — l'interception, sur le chemin réseau plutôt que dans le code
* `evidence` — l'Action Evidence Record, signé et vérifiable sans nous

La vérification est volontairement utilisable seule : `verify_evidence`
n'ouvre aucune connexion et n'a besoin d'aucun compte. Une preuve qu'il
faudrait nous demander de valider ne vaudrait rien.
"""

from .evidence import (
    SPEC_VERSION,
    ActionEvidence,
    EvidenceError,
    VerificationReport,
    verify_chain,
    verify_evidence,
)
from .policy import ALLOW, APPROVAL, BLOCK, Policy, PolicyError, Rule, Verdict
from .proxy import AssuranceProxy, EvidenceStore, make_proxy_server
from .risk import DEFAULT_EVIDENCE_THRESHOLD, DESCRIPTIONS, RiskLevel

__all__ = [
    "RiskLevel", "DESCRIPTIONS", "DEFAULT_EVIDENCE_THRESHOLD",
    "Policy", "Rule", "Verdict", "PolicyError", "ALLOW", "BLOCK", "APPROVAL",
    "ActionEvidence", "EvidenceError", "SPEC_VERSION",
    "verify_evidence", "verify_chain", "VerificationReport",
    "AssuranceProxy", "EvidenceStore", "make_proxy_server",
]
