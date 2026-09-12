"""Qui a le droit de signer au nom de qui.

Vérifier une preuve suppose de connaître la clé publique du payeur. Ce
trousseau est l'annuaire qui répond à cette question, et rien d'autre :
il ne décide pas si le paiement est recevable, seulement si la signature
vient bien de l'agent annoncé.

Un `dict` suffit pour commencer. Une fonction convient dès qu'il faut
interroger le relais — la signature `(agent_id) -> pem | None` est la
seule chose que le vérificateur exige.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..signing import key_fingerprint, load_public_pem

KeyLookup = Union[Dict[str, str], Callable[[str], Optional[str]]]


class UnknownPayer(LookupError):
    """Aucune clé publique connue pour cet agent."""


class Keyring:
    """Annuaire des clés publiques, avec un cache de déchiffrement PEM."""

    def __init__(self, source: Optional[KeyLookup] = None):
        self._lookup = source if callable(source) else None
        self._keys: Dict[str, str] = dict(source) if isinstance(source, dict) else {}
        self._parsed: Dict[str, Ed25519PublicKey] = {}

    def add(self, agent_id: str, public_pem: str) -> str:
        """Enregistre une clé et renvoie son empreinte.

        L'empreinte est ce qu'on montre à un humain : elle permet de
        constater qu'un agent a changé de clé plutôt que de découvrir des
        signatures refusées sans explication.
        """
        load_public_pem(public_pem)  # rejette tout de suite une clé illisible
        self._keys[agent_id] = public_pem
        self._parsed.pop(agent_id, None)
        return key_fingerprint(public_pem)

    def public_pem(self, agent_id: str) -> Optional[str]:
        if agent_id in self._keys:
            return self._keys[agent_id]
        return self._lookup(agent_id) if self._lookup else None

    def public_key(self, agent_id: str) -> Ed25519PublicKey:
        if agent_id in self._parsed:
            return self._parsed[agent_id]

        pem = self.public_pem(agent_id)
        if not pem:
            raise UnknownPayer(
                f"aucune clé publique connue pour '{agent_id}' — il doit "
                "s'enregistrer auprès du registre avant de payer")

        key = load_public_pem(pem)
        self._parsed[agent_id] = key
        return key

    def __contains__(self, agent_id: str) -> bool:
        return self.public_pem(agent_id) is not None

    def __len__(self) -> int:
        return len(self._keys)

    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, str]:
        return dict(self._keys)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self._keys, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Keyring":
        file = Path(path)
        if not file.is_file():
            return cls()
        return cls(json.loads(file.read_text(encoding="utf-8")))
