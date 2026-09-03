"""
Contre-pression : dire non quand le Hub est saturé, plutôt que d'accepter.

Le garde-fou existant plafonne les soumissions **par agent** (60/minute).
Il protège d'un agent devenu fou, pas de la saturation : cent agents
sages, à un tiers de leur quota chacun, dépassent largement ce qu'un Hub
soutient.

Ce que le banc de mesure a montré, et qu'il ne faut pas contredire sans
nouvelle mesure :

  * plafond observé sur un Hub : environ 11 tâches/s, indépendant du
    nombre d'agents (78 comme 234) — c'est le Hub qui borne, pas la flotte ;
  * zone saine : jusqu'à 8 tâches/s avec chiffrement, p50 sous la seconde ;
  * au-delà, le Hub acceptait tout, mettait en file, la latence explosait,
    et les clients mouraient sur un délai de ping WebSocket. Le processus
    survivait, mais **aucun signal ne disait que le Hub était saturé**.

Un refus explicite vaut mieux qu'une acceptation qui n'aboutira pas :
l'émetteur peut réessayer plus tard, réduire sa cadence, ou basculer
ailleurs. Une file qui gonfle en silence ne lui laisse que le délai
d'attente, c'est-à-dire l'ignorance.

Ce module ne connaît rien du Hub : il reçoit les compteurs et rend une
décision. C'est ce qui le rend vérifiable sans réseau.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


@dataclass
class BackpressureLimits:
    """Les trois plafonds, et l'interrupteur.

    Les défauts viennent de la mesure, pas d'une intuition : 10 tâches/s
    est le plafond observé arrondi, et laisse la zone saine (8/s) intacte.
    Un déploiement qui mesure autre chose sur son propre matériel doit les
    relever — d'où des réglages, et non des constantes.
    """

    max_tasks_per_sec: int = 10
    max_in_flight: int = 200
    max_queue_depth: int = 100
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "BackpressureLimits":
        return cls(
            max_tasks_per_sec=_env_int("INTERMESH_MAX_TASKS_PER_SEC", 10),
            max_in_flight=_env_int("INTERMESH_MAX_TASKS_IN_FLIGHT", 200),
            max_queue_depth=_env_int("INTERMESH_MAX_TASK_QUEUE_DEPTH", 100),
            enabled=_env_bool("INTERMESH_BACKPRESSURE_ENABLED", True),
        )


@dataclass
class Rejection:
    """Un refus, avec de quoi agir : pourquoi, et dans combien de temps."""

    reason: str                      # rate_limited | in_flight_limit | task_queue_full
    retry_after_ms: int
    queue_depth: int
    in_flight: int
    limits: BackpressureLimits

    code: str = "HUB_SATURATED"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "reason": self.reason,
            "retry_after_ms": self.retry_after_ms,
            "queue_depth": self.queue_depth,
            "in_flight": self.in_flight,
            "hub_tasks_per_sec_limit": self.limits.max_tasks_per_sec,
            "hub_in_flight_limit": self.limits.max_in_flight,
            "hub_queue_depth_limit": self.limits.max_queue_depth,
        }

    def __str__(self) -> str:
        return (f"HUB_SATURATED ({self.reason}) : le Hub refuse cette tâche pour "
                f"ne pas la mettre dans une file qui n'avancera pas. "
                f"Réessayez dans {self.retry_after_ms} ms. "
                f"File {self.queue_depth}/{self.limits.max_queue_depth}, "
                f"en vol {self.in_flight}/{self.limits.max_in_flight}, "
                f"plafond {self.limits.max_tasks_per_sec} tâches/s.")


class BackpressureGate:
    """Décide d'accepter ou de refuser une soumission.

    Le débit est contrôlé par un seau à jetons plutôt qu'une fenêtre
    glissante : à cadence régulière les deux se valent, mais le seau
    absorbe une rafale courte sans la refuser, ce qui correspond à ce que
    fait un orchestrateur qui découpe un travail en lots.
    """

    def __init__(self, limits: BackpressureLimits | None = None,
                 now: float | None = None):
        self.limits = limits or BackpressureLimits()
        # Le seau démarre plein : un Hub qui vient de démarrer ne doit pas
        # refuser la première rafale au motif qu'il n'a pas encore
        # accumulé de jetons.
        self._tokens = float(self.limits.max_tasks_per_sec)
        self._last = now if now is not None else time.monotonic()

        self.accepted = 0
        self.rejected = 0
        self.rejected_by_reason: dict[str, int] = {}
        self._last_logged: float | None = None

    # ------------------------------------------------------------------

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self._last)
        self._last = now
        capacity = float(self.limits.max_tasks_per_sec)
        self._tokens = min(capacity, self._tokens + elapsed * capacity)

    def _retry_after_ms(self) -> int:
        """Délai avant qu'un jeton soit à nouveau disponible.

        Renvoyé au client pour qu'il attende la bonne durée plutôt que de
        réessayer aussitôt — un réessai immédiat aggrave la saturation
        qu'il vient de rencontrer.
        """
        rate = self.limits.max_tasks_per_sec
        if rate <= 0:
            return 1000
        missing = max(0.0, 1.0 - self._tokens)
        return max(1, int(round((missing / rate) * 1000)))

    # ------------------------------------------------------------------

    def admit(self, in_flight: int, queue_depth: int,
              now: float | None = None) -> Rejection | None:
        """Renvoie None si la tâche est acceptée, sinon le refus.

        L'ordre des contrôles n'est pas indifférent : les plafonds d'état
        (en vol, file) passent avant le débit, parce qu'un Hub déjà plein
        doit refuser même s'il lui reste des jetons — sinon on accepterait
        une tâche dont on sait déjà qu'elle attendra.
        """
        if not self.limits.enabled:
            self.accepted += 1
            return None

        now = time.monotonic() if now is None else now

        if self.limits.max_in_flight and in_flight >= self.limits.max_in_flight:
            return self._refuse("in_flight_limit", 1000, in_flight, queue_depth)

        if self.limits.max_queue_depth and queue_depth >= self.limits.max_queue_depth:
            return self._refuse("task_queue_full", 1000, in_flight, queue_depth)

        self._refill(now)
        if self.limits.max_tasks_per_sec and self._tokens < 1.0:
            return self._refuse("rate_limited", self._retry_after_ms(),
                                in_flight, queue_depth)

        self._tokens -= 1.0
        self.accepted += 1
        return None

    def _refuse(self, reason: str, retry_after_ms: int,
                in_flight: int, queue_depth: int) -> Rejection:
        self.rejected += 1
        self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
        return Rejection(
            reason=reason, retry_after_ms=retry_after_ms,
            queue_depth=queue_depth, in_flight=in_flight, limits=self.limits,
        )

    # ------------------------------------------------------------------

    def note_rejection(self, now: float, window_s: float = 10.0) -> bool:
        """Faut-il journaliser ce refus ? Une fois par période, pas plus.

        Écrire chaque refus dans la chaîne d'audit ajoute un hachage Merkle
        par refus — donc du travail proportionnel à la saturation, au pire
        moment. Le compte exact reste disponible dans les compteurs ; ce
        qu'un exploitant a besoin de voir dans l'audit, c'est *quand* le Hub
        est entré en saturation, pas les milliers de refus qui suivent.
        """
        if self._last_logged is None or (now - self._last_logged) >= window_s:
            self._last_logged = now
            return True
        return False

    def snapshot(self, in_flight: int, queue_depth: int) -> dict:
        """État lisible par un exploitant ou une sonde."""
        return {
            "enabled": self.limits.enabled,
            "in_flight": in_flight,
            "queue_depth": queue_depth,
            "accepted_total": self.accepted,
            "rejected_total": self.rejected,
            "rejected_by_reason": dict(self.rejected_by_reason),
            "tokens_available": round(self._tokens, 2),
            "limits": {
                "tasks_per_sec": self.limits.max_tasks_per_sec,
                "in_flight": self.limits.max_in_flight,
                "queue_depth": self.limits.max_queue_depth,
            },
            # Ce que l'exploitant regarde en premier : suis-je proche du mur ?
            "saturation": {
                "in_flight_pct": _pct(in_flight, self.limits.max_in_flight),
                "queue_depth_pct": _pct(queue_depth, self.limits.max_queue_depth),
            },
        }


def _pct(value: int, limit: int) -> int:
    if not limit:
        return 0
    return min(100, int(round(100.0 * value / limit)))
