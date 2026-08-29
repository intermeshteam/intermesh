"""
Transport des liens de fédération : TLS et refus du clair.

Les Hubs échangent leurs clés publiques dans le canal de pairage lui-même.
Sans TLS, ce canal est modifiable en transit : un attaquant en position
d'interception substitue sa propre clé pendant la poignée de main et
signe ensuite tout ce qu'il veut, alors que la vérification asymétrique
côté message paraît intacte. Chiffrer et *authentifier* le lien est donc
ce qui donne sa valeur à la signature Ed25519, pas un supplément.

Conséquence assumée : un pairage en clair vers un hôte distant est refusé
par défaut. Il faut le demander explicitement (--allow-insecure-peering),
ce qui réserve le cas au développement local et aux tests.
"""

from __future__ import annotations

import ipaddress
import ssl
from urllib.parse import urlparse

SECURE_SCHEMES = ("wss",)
INSECURE_SCHEMES = ("ws",)


def parse_peer_spec(spec: str) -> tuple[str, str]:
    """Découpe `ORG=ws(s)://host:port`. Lève ValueError si la forme est invalide."""
    if "=" not in spec:
        raise ValueError(f"format attendu ORG=wss://host:port, reçu : {spec!r}")

    org, url = spec.split("=", 1)
    org, url = org.strip(), url.strip()
    if not org:
        raise ValueError(f"organisation absente dans : {spec!r}")

    scheme = urlparse(url).scheme
    if scheme not in SECURE_SCHEMES + INSECURE_SCHEMES:
        raise ValueError(f"schéma {scheme!r} non supporté (attendu ws:// ou wss://) : {url!r}")
    return org, url


def is_loopback_url(url: str) -> bool:
    """Vrai si l'URL désigne la machine locale.

    Un lien qui ne quitte pas la machine n'est pas exposé à l'interception,
    ce qui rend le clair acceptable pour les tests et le développement.
    """
    host = urlparse(url).hostname
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def assert_peer_link_is_secure(org: str, url: str, allow_insecure: bool = False) -> None:
    """Refuse un pairage en clair vers un hôte distant.

    Raises:
        ValueError: si le lien est en `ws://` hors machine locale sans
            dérogation explicite.
    """
    if urlparse(url).scheme in SECURE_SCHEMES:
        return
    if is_loopback_url(url):
        return
    if allow_insecure:
        return
    raise ValueError(
        f"pairage refusé vers '{org}' ({url}) : un lien en clair vers un hôte "
        f"distant permet de substituer les clés publiques pendant la poignée "
        f"de main. Utilisez wss://, ou --allow-insecure-peering si vous "
        f"maîtrisez le réseau."
    )


def build_server_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """Contexte TLS du Hub pour servir en wss://."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def build_peer_ssl_context(url: str, ca_file: str | None = None) -> ssl.SSLContext | None:
    """Contexte TLS pour se connecter à un Hub pair, ou None en ws://.

    La vérification du certificat et du nom d'hôte est toujours active :
    la désactiver ramènerait exactement le trou que ce module ferme.
    `ca_file` permet d'utiliser une autorité privée (PKI interne, certificat
    auto-signé d'un partenaire) sans jamais renoncer à la vérification.
    """
    if urlparse(url).scheme not in SECURE_SCHEMES:
        return None

    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context
