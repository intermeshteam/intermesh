import datetime
import json
import logging
import os
import sys
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formateur produisant des lignes de log JSON strictes pour la production."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inclusion des metadonnees de contexte structure
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    """Formateur console lisible avec horodatage UTC et metadonnees explicites."""

    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.datetime.fromtimestamp(
            record.created, tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")

        base = f"[{dt} UTC] [{record.levelname:<7}] [{record.name}] {record.getMessage()}"

        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            base = f"{base} | {extra_str}"

        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"

        return base


class InterMeshLoggerAdapter(logging.LoggerAdapter):
    """Adaptateur permettant d'attacher dynamiquement des donnees de contexte."""

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = kwargs.get("extra", {})
        if self.extra:
            merged = {**self.extra, **extra}
        else:
            merged = extra
        kwargs["extra"] = {"extra_fields": merged}
        return msg, kwargs


def get_logger(name: str = "intermesh", **default_context: Any) -> InterMeshLoggerAdapter:
    """
    Retourne une instance de logger configuree selon les parametres systeme.
    """
    log_level_str = os.environ.get("INTERMESH_LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("INTERMESH_LOG_FORMAT", "text").lower()

    level = getattr(logging, log_level_str, logging.INFO)

    raw_logger = logging.getLogger(name)
    raw_logger.setLevel(level)

    # Eviter la multiplication des handlers lors d'appels repetes
    if not raw_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        if log_format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(StandardFormatter())

        raw_logger.addHandler(handler)
        raw_logger.propagate = False

    return InterMeshLoggerAdapter(raw_logger, default_context)
