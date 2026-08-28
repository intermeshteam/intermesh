import logging
from typing import Set

class RoutingPolicyEnforcer:
    """
    Controleur de securite multi-tenant et de politiques de routage.
    """

    def __init__(self, allow_cross_tenant_by_default: bool = False):
        self.allow_cross_tenant_by_default = allow_cross_tenant_by_default
        # Ensemble des relations inter-tenant explicitement autorisees "tenant_source->tenant_cible"
        self._allowed_connections: Set[str] = set()

    def allow_cross_tenant_connection(self, from_org: str, to_org: str) -> None:
        """Autorise explicitement les messages de from_org vers to_org."""
        self._allowed_connections.add(f"{from_org}->{to_org}")

    def revoke_cross_tenant_connection(self, from_org: str, to_org: str) -> None:
        """Revoque l'autorisation de communication inter-tenant."""
        self._allowed_connections.discard(f"{from_org}->{to_org}")

    def can_route(self, sender_org: str, recipient_org: str) -> bool:
        """
        Determine si un message emis par sender_org peut etre route vers recipient_org.
        """
        # Un meme tenant peut toujours communiquer avec lui-meme
        if sender_org == recipient_org:
            return True
            
        # Si la securite globale autorise le cross-tenant
        if self.allow_cross_tenant_by_default:
            return True
            
        # Sinon, verifier la presence d'une politique d'accord explicite (peering local)
        return f"{sender_org}->{recipient_org}" in self._allowed_connections
