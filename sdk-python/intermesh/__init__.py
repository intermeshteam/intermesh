from intermesh.agent import InterMeshAgent
from intermesh.message import MessageType, InterMeshMessage
from intermesh.identity import AgentIdentity
from intermesh.task import InterMeshTask, TaskStatus
from intermesh.audit import ImmutableAuditLog, AuditEntry
from intermesh.ratelimit import RateLimiter, TokenBucket
from intermesh.adapters import from_callable, from_langchain, intermesh_service
from intermesh.bridge import (
    BridgeError, exec_handler, from_command, from_http, http_handler,
    post_task, run_command,
)
from intermesh.egress import EgressBlocked, EgressPolicy, EgressRule, apply_egress
from intermesh.guardrails import AsimovGuardrailEngine, GuardrailPolicy, PolicyViolationError, CircuitBreaker

# Imports optionnels pour la rétro-compatibilité complète
try:
    from intermesh.store import InterMeshStore
except ImportError:
    pass

try:
    from intermesh.pipeline import InterMeshPipeline, PipelineError, fan_out
except ImportError:
    pass

try:
    from intermesh.logger import get_logger, JSONFormatter, StandardFormatter
except ImportError:
    pass

try:
    from intermesh.metrics import InterMeshMetricsCollector
except ImportError:
    pass

try:
    from intermesh.policy import InterMeshPolicy
except ImportError:
    pass

try:
    from intermesh.health import InterMeshHealthChecker
except ImportError:
    pass

try:
    from intermesh.config import Settings
except ImportError:
    pass

try:
    from intermesh.snapshot import SnapshotError
except ImportError:
    pass

__version__ = "0.3.0"
