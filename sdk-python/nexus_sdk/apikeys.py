"""
Comptes de service : magasin de clés d'API du Hub.

Les clés étaient auparavant écrites en clair dans le code source du Hub,
donc publiées avec le dépôt. Une clé versionnée dans Git est une clé
compromise : elle reste lisible dans l'historique même après suppression.

Ce module les charge depuis une source externe et ne conserve jamais que
leur empreinte SHA-256. Le Hub ne peut donc pas révéler une clé, même si
sa configuration fuit — il peut seulement vérifier qu'une clé présentée
correspond à une empreinte connue.

Sources, par ordre de priorité :

  1. NEXUS_API_KEYS       — JSON inline (Kubernetes, CI)
  2. NEXUS_API_KEYS_FILE  — chemin d'un fichier JSON
  3. ~/.nexus/api_keys.json
  4. aucune — les comptes de service sont simplement désactivés
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from pathlib import Path

ENV_INLINE = "NEXUS_API_KEYS"
ENV_FILE = "NEXUS_API_KEYS_FILE"

# Clés de démonstration, activées uniquement sur demande explicite
# (--dev-api-keys). Elles sont publiques par construction : ne jamais
# s'en servir ailleurs que pour une démo ou un test.
DEV_API_KEYS = {
    "nx_dev_acme_demo_key": {
        "org_id": "acme",
        "roles": ["admin", "service_account"],
        "permissions": ["admin:*"],
    },
    "nx_dev_globex_demo_key": {
        "org_id": "globex",
        "roles": ["worker", "service_account"],
        "permissions": ["compute:execute"],
    },
}


def default_keys_path() -> Path:
    base = os.environ.get("NEXUS_HOME")
    return (Path(base) if base else Path.home() / ".nexus") / "api_keys.json"


def hash_key(raw_key: str) -> str:
    """Empreinte SHA-256 d'une clé d'API."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_key(prefix: str = "nx_live") -> str:
    """Génère une clé d'API cryptographiquement aléatoire."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


class ApiKeyStore:
    """Vérifie les clés d'API sans jamais conserver leur valeur en clair."""

    def __init__(self, keys: dict[str, dict] | None = None, source: str = "aucune"):
        """
        Args:
            keys:   Mapping clé_en_clair -> {org_id, roles, permissions}.
                    Seules les empreintes sont conservées.
            source: Description de la provenance, pour la bannière de démarrage.
        """
        self._by_hash: dict[str, dict] = {}
        self.source = source

        for raw_key, info in (keys or {}).items():
            self._by_hash[hash_key(raw_key)] = {
                "org_id": info["org_id"],
                "roles": list(info.get("roles", [])),
                "permissions": list(info.get("permissions", [])),
            }

    def __len__(self) -> int:
        return len(self._by_hash)

    def lookup(self, raw_key: str) -> dict | None:
        """
        Retourne les privilèges associés à une clé, ou None si inconnue.

        La comparaison est à temps constant : comparer des empreintes avec
        `==` laisse fuir, par le temps de réponse, le nombre d'octets
        corrects en tête — de quoi reconstruire une empreinte valide
        octet par octet.
        """
        if not raw_key:
            return None

        candidate = hash_key(raw_key)
        matched = None
        for known_hash, info in self._by_hash.items():
            if secrets.compare_digest(candidate, known_hash):
                matched = info
        return matched

    # ------------------------------------------------------------------

    @classmethod
    def load(cls, dev_keys: bool = False) -> "ApiKeyStore":
        """Charge les clés depuis la première source disponible."""
        inline = os.environ.get(ENV_INLINE)
        if inline:
            try:
                return cls(json.loads(inline), source=f"variable {ENV_INLINE}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"{ENV_INLINE} n'est pas du JSON valide : {exc}") from exc

        explicit = os.environ.get(ENV_FILE)
        path = Path(explicit) if explicit else default_keys_path()

        if path.is_file():
            mode = path.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                print(
                    f"\033[33m⚠️  [SÉCURITÉ] {path} est lisible par d'autres utilisateurs.\033[0m\n"
                    f"    Corrigez avec : chmod 600 {path}"
                )
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} n'est pas du JSON valide : {exc}") from exc
            return cls(data, source=f"fichier {path}")

        if dev_keys:
            return cls(DEV_API_KEYS, source="clés de DÉMONSTRATION (publiques)")

        return cls({}, source="aucune — comptes de service désactivés")
