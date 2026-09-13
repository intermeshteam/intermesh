"""Un objet, un seul encodage — la base de toute signature vérifiable.

Deux parties ne peuvent vérifier la même signature que si elles obtiennent
les mêmes octets à partir du même objet. D'où trois contraintes, toutes
nécessaires :

* **clés triées**, sinon l'ordre d'insertion changerait l'empreinte ;
* **séparateurs fixes**, sans espace, sinon le formateur déciderait ;
* **aucun flottant** dans ce qui est signé. Python sérialise `1788459123.0`
  en « 1788459123.0 », JavaScript en « 1788459123 » : octets différents,
  signature différente, et un désaccord qui n'apparaît qu'une fois sur un
  million. `reject_floats` transforme ce piège silencieux en erreur bruyante.

Ce module est délibérément commun à la couche paiement et à la couche
assurance : une seconde implémentation cryptographique serait une seconde
occasion de diverger.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


class CanonicalError(ValueError):
    """Objet impossible à sérialiser de façon reproductible."""


def b64(raw: bytes) -> str:
    """Base64 URL-safe sans remplissage — passe dans un en-tête HTTP."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _assert_no_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise CanonicalError(
            f"{path} est un flottant ({value!r}) : il ne se sérialise pas "
            "identiquement en Python et en JavaScript. Utilisez un entier "
            "(millisecondes) ou une chaîne décimale.")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_floats(item, f"{path}[{index}]")


def canonical_bytes(payload: dict, reject_floats: bool = True) -> bytes:
    """Les octets exacts à signer ou à hacher."""
    if reject_floats:
        _assert_no_floats(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_hash(payload: dict) -> str:
    """Empreinte SHA-256 de l'objet canonique, en hexadécimal."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
