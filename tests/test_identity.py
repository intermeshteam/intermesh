import pytest
from nexus_sdk.identity import AgentIdentity


def test_identity_fingerprint_integrity():
    """Vérifie la validité de l'empreinte SHA-256."""
    identity = AgentIdentity(
        name="test_worker",
        capabilities=["translate", "summarize"],
        roles=["worker"],
        permissions=["text:read"]
    )
    
    assert identity.verify_fingerprint() is True
    assert len(identity.fingerprint) == 64  # Longueur SHA-256


def test_identity_tamper_detection():
    """Vérifie qu'une falsification de rôle invalide l'empreinte."""
    identity = AgentIdentity(
        name="normal_user",
        capabilities=["browse"],
        roles=["guest"],
        permissions=[]
    )
    
    # L'attaquant tente de s'octroyer le rôle admin localement
    identity.roles.append("admin")
    
    # L'empreinte doit détecter l'altération
    assert identity.verify_fingerprint() is False


def test_rbac_permissions_matching():
    """Vérifie la logique d'autorisation basée sur les rôles et permissions."""
    admin = AgentIdentity(name="admin_bot", roles=["admin"])
    worker = AgentIdentity(name="worker_bot", roles=["worker"], permissions=["compute:execute"])
    guest = AgentIdentity(name="guest_bot", roles=["guest"])
    
    # Admin a tous les droits
    assert admin.has_role("admin") is True
    assert admin.has_role("worker") is True
    assert admin.has_permission("system:reboot") is True
    
    # Worker a des droits spécifiques
    assert worker.has_role("worker") is True
    assert worker.has_role("admin") is False
    assert worker.has_permission("compute:execute") is True
    assert worker.has_permission("system:reboot") is False
    
    # Guest n'a aucun droit élevé
    assert guest.has_role("admin") is False
    assert guest.has_permission("compute:execute") is False
