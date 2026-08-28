import json
import logging
from intermesh.logger import get_logger, JSONFormatter, StandardFormatter


def test_json_formatter_structure():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test structured log",
        args=(),
        exc_info=None
    )
    record.extra_fields = {"agent": "agent_alpha", "task_id": "task_123"}
    
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test structured log"
    assert parsed["agent"] == "agent_alpha"
    assert parsed["task_id"] == "task_123"
    assert "timestamp" in parsed


def test_standard_formatter_structure():
    formatter = StandardFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg="Test warning message",
        args=(),
        exc_info=None
    )
    record.extra_fields = {"org": "acme"}
    formatted = formatter.format(record)
    
    assert "[WARNING]" in formatted
    assert "Test warning message" in formatted
    assert "org=acme" in formatted


def test_logger_adapter_extra_context():
    logger = get_logger("test.context", initial_key="initial_val")
    assert logger.extra["initial_key"] == "initial_val"
