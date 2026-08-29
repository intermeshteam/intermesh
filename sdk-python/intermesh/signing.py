"""
Signature asymétrique des jetons du Hub (Ed25519 / EdDSA).

Pourquoi : en HS256, deux Hubs qui se fédèrent devaient partager le même
secret de signature — chacun pouvait donc forger des jetons au nom des
agents de l'autre. Inacceptable entre deux organisations qui, par
définition, ne se font pas confiance.

Chaque Hub signe désormais avec une clé privée Ed25519 qui ne quitte
jamais sa machine, et publie sa clé publique à ses pairs lors du
pairage. Un pair peut donc *vérifier* l'émetteur sans jamais pouvoir
*usurper* son identité.

La clé est dérivée du secret déjà résolu par `intermesh.secret`, ce qui
préserve les propriétés acquises : priorité à l'environnement, fichier
0600, stabilité d'un redémarrage à l'autre, mode éphémère pour les tests.
"""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ALGORITHM = "EdDSA"


def derive_signing_key(secret: str) -> Ed25519PrivateKey:
    """Dérive la clé privée Ed25519 du Hub à partir de son secret.

    Le secret peut être de longueur et d'alphabet quelconques (variable
    d'environnement fournie par l'opérateur) ; SHA-256 le ramène aux
    32 octets de graine attendus par Ed25519, de façon déterministe.
    """
    seed = hashlib.sha256(secret.encode("utf-8")).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_pem(private_key: Ed25519PrivateKey) -> str:
    """Clé publique au format PEM — c'est le seul élément publiable."""
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def load_public_pem(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("clé publique attendue au format Ed25519")
    return key


def key_fingerprint(pem: str) -> str:
    """Empreinte courte d'une clé publique, utilisée comme `kid` du jeton.

    Permet à un pair de constater qu'une organisation a changé de clé
    plutôt que de rejeter silencieusement ses jetons.
    """
    return hashlib.sha256(pem.encode("utf-8")).hexdigest()[:16]
