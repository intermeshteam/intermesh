"""
Résolution de la clé de signature JWT du Hub.

Un Hub qui régénère sa clé à chaque démarrage invalide tous les tokens
déjà distribués : chaque redémarrage force la reconnexion de la totalité
de la flotte d'agents. Ce module résout la clé de manière stable, par
ordre de priorité :

  1. Variable d'environnement NEXUS_HUB_SECRET (déploiements 12-factor,
     Docker, Kubernetes — la clé ne touche jamais le disque)
  2. Fichier de clé persistant, créé en 0600 au premier démarrage
  3. Clé éphémère, uniquement sur demande explicite (tests, CI)
"""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

ENV_VAR = "NEXUS_HUB_SECRET"
MIN_SECRET_LENGTH = 32


def default_secret_path() -> Path:
    """Emplacement par défaut du fichier de clé, surchargeable via NEXUS_HOME."""
    base = os.environ.get("NEXUS_HOME")
    return (Path(base) if base else Path.home() / ".nexus") / "hub_secret"


def _read_secret_file(path: Path) -> str | None:
    """Lit la clé si le fichier existe, en signalant des permissions trop ouvertes."""
    if not path.is_file():
        return None

    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(
            f"\033[33m⚠️  [SÉCURITÉ] {path} est lisible par d'autres utilisateurs.\033[0m\n"
            f"    Corrigez avec : chmod 600 {path}"
        )

    secret = path.read_text(encoding="utf-8").strip()
    return secret or None


def _write_secret_file(path: Path, secret: str) -> None:
    """Écrit la clé avec des permissions restrictives, sans fenêtre d'exposition."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # os.open avec 0600 évite la course où le fichier existe brièvement
    # en lecture pour tous entre la création et le chmod.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, secret.encode("utf-8"))
    finally:
        os.close(fd)


def resolve_hub_secret(
    secret_file: str | os.PathLike | None = None,
    ephemeral: bool = False,
) -> tuple[str, str]:
    """
    Retourne (clé, description_de_la_source).

    Args:
        secret_file: Chemin du fichier de clé. Par défaut ~/.nexus/hub_secret.
        ephemeral:   Génère une clé jetable sans rien écrire sur disque.
                     Tous les tokens émis meurent avec le processus.

    Raises:
        ValueError: si la clé fournie via l'environnement est trop courte.
    """
    env_secret = os.environ.get(ENV_VAR)
    if env_secret:
        env_secret = env_secret.strip()
        if len(env_secret) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"{ENV_VAR} fait {len(env_secret)} caractères ; "
                f"{MIN_SECRET_LENGTH} au minimum sont requis. "
                f"Générez-en une avec : python3 -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return env_secret, f"variable d'environnement {ENV_VAR}"

    if ephemeral:
        return secrets.token_hex(32), "éphémère (perdue au redémarrage)"

    path = Path(secret_file) if secret_file else default_secret_path()

    existing = _read_secret_file(path)
    if existing:
        return existing, f"fichier {path}"

    new_secret = secrets.token_hex(32)
    try:
        _write_secret_file(path, new_secret)
    except FileExistsError:
        # Un autre processus a créé le fichier entre notre lecture et
        # notre écriture : sa clé fait foi, sinon les deux Hubs
        # signeraient avec des clés différentes.
        concurrent = _read_secret_file(path)
        if concurrent:
            return concurrent, f"fichier {path}"
        raise
    except OSError as exc:
        print(
            f"\033[33m⚠️  Impossible d'écrire la clé dans {path} ({exc}).\033[0m\n"
            f"    Bascule sur une clé éphémère : les tokens ne survivront pas au redémarrage.\n"
            f"    Définissez {ENV_VAR} pour une clé stable."
        )
        return new_secret, "éphémère (écriture impossible)"

    return new_secret, f"fichier {path} (créé)"
