import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set


class PolicyViolationError(PermissionError):
    def __init__(self, rule_name: str, message: str, agent_name: str):
        self.rule_name = rule_name
        self.agent_name = agent_name
        super().__init__(f"ASIMOV_GUARDRAIL_VIOLATION [{rule_name}] ({agent_name}): {message}")


@dataclass
class GuardrailPolicy:
    name: str = "default_safety_policy"
    max_cascade_depth: int = 4
    max_cost_per_task: float = 100.0
    max_tasks_per_minute: int = 60
    circuit_breaker_threshold: int = 3
    blocked_patterns: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf",
        r"DROP\s+DATABASE",
        r"DROP\s+TABLE",
        r"TRUNCATE\s+TABLE",
        r"format\s+[c-z]:",
        r"eval\(",
        r"exec\(",
        r"os\.system\(",
        r"subprocess\.Popen\(",
        r"sudo\s+",
        r"chmod\s+777",
        r"SELECT\s+.*\s+FROM\s+users.*password"
    ])


class TaskCascadeTracker:
    def __init__(self):
        self._depth_map: Dict[str, int] = {}
        self._parent_map: Dict[str, str] = {}

    def register_task(self, task_id: str, parent_id: Optional[str] = None) -> int:
        if not parent_id or parent_id not in self._depth_map:
            depth = 1
        else:
            depth = self._depth_map[parent_id] + 1

        self._depth_map[task_id] = depth
        if parent_id:
            self._parent_map[task_id] = parent_id

        return depth

    def get_depth(self, task_id: str) -> int:
        return self._depth_map.get(task_id, 1)


class RateWindowTracker:
    """Fenêtre glissante de 60s : combien de tâches un agent a soumises récemment."""

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = {}

    def count_recent(self, agent_name: str, now: Optional[float] = None) -> int:
        now = now if now is not None else time.time()
        window = self._events.get(agent_name)
        if not window:
            return 0
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        return len(window)

    def record(self, agent_name: str, now: Optional[float] = None) -> None:
        now = now if now is not None else time.time()
        self._events.setdefault(agent_name, deque()).append(now)


class CircuitBreaker:
    def __init__(self, threshold: int = 3, cooldown_seconds: float = 60.0):
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self._violation_counts: Dict[str, int] = {}
        self._tripped_until: Dict[str, float] = {}

    def record_violation(self, agent_name: str) -> bool:
        count = self._violation_counts.get(agent_name, 0) + 1
        self._violation_counts[agent_name] = count

        if count >= self.threshold:
            self._tripped_until[agent_name] = time.time() + self.cooldown_seconds
            print(f"\033[31m⚡ [DISJONCTEUR ISOLATION]\033[0m Agent '{agent_name}' isolé pendant {self.cooldown_seconds}s ({count} violations).")
            return True
        return False

    def is_tripped(self, agent_name: str) -> bool:
        if agent_name in self._tripped_until:
            if time.time() < self._tripped_until[agent_name]:
                return True
            else:
                del self._tripped_until[agent_name]
                self._violation_counts[agent_name] = 0
        return False


class AsimovGuardrailEngine:
    """
    Moteur de garde-fous appliqué à chaque soumission de tâche.

    Une policy par défaut s'applique à tout le Hub ; `set_org_policy` permet
    à une organisation de recevoir des limites différentes (plus strictes ou
    plus larges) sans affecter les autres locataires du même Hub.
    """

    def __init__(self, policy: Optional[GuardrailPolicy] = None):
        self.policy = policy or GuardrailPolicy()
        self.cascade_tracker = TaskCascadeTracker()
        self.circuit_breaker = CircuitBreaker(threshold=self.policy.circuit_breaker_threshold)
        self.rate_tracker = RateWindowTracker()
        self._org_policies: Dict[str, GuardrailPolicy] = {}
        self._compiled_patterns_cache: Dict[int, List[re.Pattern]] = {}

    def set_org_policy(self, org_id: str, policy: GuardrailPolicy) -> None:
        """Remplace la policy par défaut pour une organisation donnée."""
        self._org_policies[org_id] = policy

    def get_policy(self, org_id: Optional[str] = None) -> GuardrailPolicy:
        """Policy applicable : celle de l'organisation si elle en a une, sinon la policy par défaut du Hub."""
        if org_id and org_id in self._org_policies:
            return self._org_policies[org_id]
        return self.policy

    def _compiled_patterns(self, policy: GuardrailPolicy) -> List[re.Pattern]:
        key = id(policy)
        cached = self._compiled_patterns_cache.get(key)
        if cached is None:
            cached = [re.compile(pat, re.IGNORECASE) for pat in policy.blocked_patterns]
            self._compiled_patterns_cache[key] = cached
        return cached

    def inspect_payload(self, agent_name: str, payload_text: str, org_id: Optional[str] = None):
        if self.circuit_breaker.is_tripped(agent_name):
            raise PolicyViolationError(
                "CIRCUIT_BREAKER_TRIPPED",
                f"L'agent '{agent_name}' est temporairement bloqué suite à de multiples violations.",
                agent_name
            )

        policy = self.get_policy(org_id)
        for pattern in self._compiled_patterns(policy):
            if pattern.search(payload_text):
                self.circuit_breaker.record_violation(agent_name)
                rule_name = "FORBIDDEN_PATTERN_INTERCEPTED"
                msg = f"Commande ou pattern destructeur détecté : '{pattern.pattern}' dans la charge utile."
                raise PolicyViolationError(rule_name, msg, agent_name)

    def validate_task_submission(
        self,
        agent_name: str,
        task_id: str,
        parent_task_id: Optional[str] = None,
        estimated_cost: float = 0.0,
        payload_text: Optional[str] = None,
        org_id: Optional[str] = None,
    ):
        if self.circuit_breaker.is_tripped(agent_name):
            raise PolicyViolationError(
                "CIRCUIT_BREAKER_TRIPPED",
                f"L'agent '{agent_name}' est isolé suite à de multiples infractions.",
                agent_name
            )

        policy = self.get_policy(org_id)

        depth = self.cascade_tracker.register_task(task_id, parent_task_id)
        if depth > policy.max_cascade_depth:
            self.circuit_breaker.record_violation(agent_name)
            raise PolicyViolationError(
                "INFINITE_CASCADE_RECURSION",
                f"Profondeur de récursion maximale dépassée ({depth}/{policy.max_cascade_depth}). Boucle d'agents bloquée.",
                agent_name
            )

        if estimated_cost > policy.max_cost_per_task:
            self.circuit_breaker.record_violation(agent_name)
            raise PolicyViolationError(
                "TASK_COST_CAP_EXCEEDED",
                f"Coût estimé ({estimated_cost:.2f} $) dépasse le plafond autorisé ({policy.max_cost_per_task:.2f} $).",
                agent_name
            )

        if self.rate_tracker.count_recent(agent_name) >= policy.max_tasks_per_minute:
            self.circuit_breaker.record_violation(agent_name)
            raise PolicyViolationError(
                "RATE_LIMIT_EXCEEDED",
                f"Plus de {policy.max_tasks_per_minute} tâches/minute pour '{agent_name}'.",
                agent_name
            )

        if payload_text:
            self.inspect_payload(agent_name, payload_text, org_id=org_id)

        # Enregistré seulement une fois toutes les vérifications passées : une
        # tâche refusée ne doit pas consommer le quota de débit de l'agent.
        self.rate_tracker.record(agent_name)
