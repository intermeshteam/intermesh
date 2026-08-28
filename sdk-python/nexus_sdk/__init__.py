from nexus_sdk.agent import NexusAgent
from nexus_sdk.message import MessageType, NexusMessage
from nexus_sdk.identity import AgentIdentity
from nexus_sdk.task import NexusTask, TaskStatus
from nexus_sdk.audit import ImmutableAuditLog, AuditEntry
from nexus_sdk.ratelimit import RateLimiter, TokenBucket
from nexus_sdk.adapters import from_callable, from_langchain, nexus_service
from nexus_sdk.guardrails import AsimovGuardrailEngine, GuardrailPolicy, PolicyViolationError, CircuitBreaker

# Imports optionnels pour la rétro-compatibilité complète
try:
    from nexus_sdk.store import NexusStore
except ImportError:
    pass

try:
    from nexus_sdk.pipeline import NexusPipeline, PipelineError, fan_out
except ImportError:
    pass

try:
    from nexus_sdk.logger import get_logger, JSONFormatter, StandardFormatter
except ImportError:
    pass

try:
    from nexus_sdk.metrics import NexusMetricsCollector
except ImportError:
    pass

try:
    from nexus_sdk.policy import NexusPolicy
except ImportError:
    pass

try:
    from nexus_sdk.health import NexusHealthChecker
except ImportError:
    pass

try:
    from nexus_sdk.config import Settings
except ImportError:
    pass

__version__ = "0.2.0"
