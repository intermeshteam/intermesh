import time
from typing import Dict


class TokenBucket:
    """
    Implémentation de l'algorithme standard Token Bucket pour le Rate Limiting.
    """

    def __init__(self, rate_per_sec: float, capacity: float):
        self.rate = rate_per_sec       # Nombre de jetons ajoutés par seconde
        self.capacity = capacity       # Capacité maximale de la réserve (burst)
        self.tokens = capacity         # Jetons actuellement disponibles
        self.last_update = time.time()

    def consume(self, tokens: float = 1.0) -> bool:
        """Consomme un jeton. Retourne True si autorisé, False si limite dépassée."""
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Recharger les jetons selon le temps écoulé
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """Gestionnaire de Rate Limiting multi-agents et multi-tenants."""

    def __init__(self, default_rate: float = 10.0, default_burst: float = 15.0):
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.buckets: Dict[str, TokenBucket] = {}

    def is_allowed(self, client_id: str) -> bool:
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(self.default_rate, self.default_burst)
        return self.buckets[client_id].consume(1.0)
