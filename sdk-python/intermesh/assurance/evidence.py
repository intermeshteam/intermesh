"""Action Evidence Record — la primitive du produit.

Un journal dit ce que le système se souvient d'avoir fait. Une preuve
permet à quelqu'un qui ne vous fait pas confiance de le vérifier lui-même.
Toute la différence tient dans trois propriétés, et chacune doit être
vraie pour qu'une preuve vaille quelque chose devant un tiers :

* **intégrité** — le hachage couvre tout le contenu ; modifier un champ
  après coup se voit ;
* **non-répudiation** — la signature Ed25519 désigne l'émetteur. Il ne
  peut pas soutenir ensuite qu'il n'a rien émis ;
* **chaînage** — chaque preuve porte l'empreinte de la précédente.
  Falsifier une preuve ne suffit pas : il faut réécrire toute la suite.

Ce que la preuve **ne** garantit **pas**, et qu'il faut dire clairement :
elle atteste de ce que le proxy a observé. Si l'agent contourne le proxy,
il n'y a pas de preuve du tout — l'absence de preuve n'est pas une preuve
d'absence d'action. C'est la limite structurelle du dispositif.

Aucun corps de requête n'est stocké : seulement son empreinte. Une preuve
qui contiendrait le contenu d'un virement deviendrait elle-même la fuite
de données qu'elle prétend documenter.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..canonical import b64, canonical_bytes, canonical_hash, sha256_hex, unb64
from ..payments.clock import now_ms
from ..signing import key_fingerprint, load_public_pem, public_pem
from .risk import RiskLevel

SPEC_VERSION = "0.1"
GENESIS = "0" * 64


class EvidenceError(ValueError):
    """Preuve illisible, incomplète, altérée ou mal signée."""


@dataclass
class ActionEvidence:
    """Ce qu'un agent a tenté, ce qui a été décidé, ce qui s'est passé.

    Les quatre blocs — action, risque, autorisation, exécution — répondent
    aux quatre questions d'un auditeur : quoi, à quel point c'est grave,
    qui l'a permis, et qu'est-ce qui est réellement arrivé.
    """

    agent_id: str
    organization_id: str
    action: Dict[str, Any]
    risk: Dict[str, Any]
    authorization: Dict[str, Any]
    execution: Dict[str, Any]
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=now_ms)  # ms entières : voir canonical
    prev_hash: str = GENESIS
    version: str = SPEC_VERSION

    # ------------------------------------------------------------------

    @classmethod
    def build(cls, *, agent_id: str, organization_id: str, method: str,
              target: str, risk: RiskLevel, decision: str, policy: str,
              rule: Optional[str] = None, payload_hash: Optional[str] = None,
              action_type: Optional[str] = None, status: str = "pending",
              response_status: Optional[int] = None,
              response_hash: Optional[str] = None,
              prev_hash: str = GENESIS,
              extra: Optional[Dict[str, Any]] = None) -> "ActionEvidence":
        """Fabrique une preuve depuis ce que le proxy a observé."""
        return cls(
            agent_id=agent_id,
            organization_id=organization_id,
            action={
                "method": method.upper(),
                "target": target,
                "type": action_type or "http_request",
                "payload_hash": payload_hash,
            },
            risk={"level": str(risk), "label": risk.name, "value": int(risk)},
            authorization={"policy": policy, "rule": rule, "decision": decision},
            execution=_clean({
                "status": status,
                "response_status": response_status,
                "response_hash": response_hash,
                **(extra or {}),
            }),
            prev_hash=prev_hash,
        )

    # ------------------------------------------------------------------

    def body(self) -> Dict[str, Any]:
        """Le contenu couvert par le hachage et la signature."""
        return {
            "version": self.version,
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "organization_id": self.organization_id,
            "action": _clean(self.action),
            "risk": self.risk,
            "authorization": _clean(self.authorization),
            "execution": _clean(self.execution),
            "prev_hash": self.prev_hash,
        }

    def evidence_hash(self) -> str:
        return canonical_hash(self.body())

    def sign(self, private_key: Ed25519PrivateKey,
             issuer: Optional[str] = None) -> Dict[str, Any]:
        """Rend la preuve complète, prête à être écrite ou transmise.

        La signature couvre le hachage plutôt que le corps : un vérificateur
        recalcule le hachage depuis le corps, puis contrôle la signature sur
        ce hachage. Les deux contrôles restent ainsi distincts, et une preuve
        peut échouer sur l'intégrité *ou* sur la signature — ce que le rapport
        de vérification doit pouvoir distinguer.
        """
        digest = self.evidence_hash()
        pem = public_pem(private_key)
        return {
            **self.body(),
            "evidence": {
                "hash": digest,
                "algorithm": "Ed25519",
                "signature": b64(private_key.sign(digest.encode("ascii"))),
                "issuer": issuer or self.organization_id,
                "public_key": pem,
                "key_fingerprint": key_fingerprint(pem),
            },
        }


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    """Retire les champs vides : un `null` signé n'apporte rien et alourdit."""
    return {k: v for k, v in data.items() if v is not None}


def payload_digest(raw: bytes) -> Optional[str]:
    """Empreinte d'un corps de requête — jamais son contenu."""
    return sha256_hex(raw) if raw else None


# ----------------------------------------------------------------------
# Vérification — utilisable sans serveur, sans compte, sans nous
# ----------------------------------------------------------------------

REQUIRED = ("version", "action_id", "timestamp", "agent_id", "organization_id",
            "action", "risk", "authorization", "execution", "prev_hash")


@dataclass
class VerificationReport:
    """Le résultat détaillé, pour que « INVALIDE » dise *pourquoi*."""

    schema_ok: bool = False
    integrity_ok: bool = False
    signature_ok: bool = False
    errors: list = field(default_factory=list)
    decision: Optional[str] = None
    risk: Optional[str] = None
    action_id: Optional[str] = None
    issuer: Optional[str] = None
    key_fingerprint: Optional[str] = None

    @property
    def valid(self) -> bool:
        return self.schema_ok and self.integrity_ok and self.signature_ok

    def to_dict(self) -> dict:
        return {"valid": self.valid, "schema": self.schema_ok,
                "integrity": self.integrity_ok, "signature": self.signature_ok,
                "decision": self.decision, "risk": self.risk,
                "action_id": self.action_id, "issuer": self.issuer,
                "key_fingerprint": self.key_fingerprint, "errors": self.errors}


def verify_evidence(record: dict,
                    trusted_key: Optional[Ed25519PublicKey] = None
                    ) -> VerificationReport:
    """Vérifie une preuve isolée, sans rien contacter.

    `trusted_key` est facultative mais change la portée du résultat. Sans
    elle, on vérifie que la preuve est cohérente avec la clé qu'elle
    transporte — ce qui prouve qu'elle n'a pas été modifiée, pas qu'elle
    vient de qui elle prétend. Avec elle, on vérifie l'émetteur.

    Cette nuance est capitale et doit rester visible dans le rapport : une
    preuve auto-cohérente signée par un inconnu n'atteste de rien.
    """
    report = VerificationReport()

    if not isinstance(record, dict):
        report.errors.append("la preuve n'est pas un objet JSON")
        return report

    missing = [f for f in REQUIRED if f not in record]
    envelope = record.get("evidence")
    if not isinstance(envelope, dict):
        missing.append("evidence")
    if missing:
        report.errors.append(f"champs manquants : {sorted(set(missing))}")
        return report

    report.schema_ok = True
    report.action_id = record.get("action_id")
    report.decision = (record.get("authorization") or {}).get("decision")
    report.risk = (record.get("risk") or {}).get("level")
    report.issuer = envelope.get("issuer")
    report.key_fingerprint = envelope.get("key_fingerprint")

    body = {f: record[f] for f in REQUIRED}
    try:
        recomputed = canonical_hash(body)
    except Exception as exc:
        report.errors.append(f"corps non sérialisable : {exc}")
        return report

    claimed = envelope.get("hash")
    if recomputed != claimed:
        report.errors.append(
            "le contenu ne correspond plus à son empreinte — la preuve a été "
            f"modifiée (calculé {recomputed[:16]}…, annoncé {str(claimed)[:16]}…)")
    else:
        report.integrity_ok = True

    key = trusted_key
    if key is None:
        pem = envelope.get("public_key")
        if not pem:
            report.errors.append("aucune clé publique dans la preuve, et "
                                 "aucune clé de confiance fournie")
            return report
        try:
            key = load_public_pem(pem)
        except Exception as exc:
            report.errors.append(f"clé publique illisible : {exc}")
            return report

    try:
        key.verify(unb64(str(envelope.get("signature", ""))),
                   str(claimed).encode("ascii"))
        report.signature_ok = True
    except (InvalidSignature, ValueError) as exc:
        report.errors.append(f"signature invalide : {exc or 'ne correspond pas'}")

    return report


def verify_chain(records: list) -> VerificationReport:
    """Vérifie une suite de preuves et leur chaînage.

    Le chaînage est ce qui empêche la suppression discrète : retirer une
    preuve du milieu casse le lien de la suivante.
    """
    report = VerificationReport(schema_ok=True, integrity_ok=True, signature_ok=True)
    previous = GENESIS

    for index, record in enumerate(records):
        single = verify_evidence(record)
        if not single.valid:
            report.schema_ok &= single.schema_ok
            report.integrity_ok &= single.integrity_ok
            report.signature_ok &= single.signature_ok
            report.errors.extend(f"preuve #{index} : {e}" for e in single.errors)
            continue
        if record.get("prev_hash") != previous:
            report.integrity_ok = False
            report.errors.append(
                f"preuve #{index} : chaînage rompu — une preuve a été retirée "
                "ou insérée")
        previous = (record.get("evidence") or {}).get("hash", GENESIS)

    report.action_id = f"{len(records)} preuve(s)"
    return report
