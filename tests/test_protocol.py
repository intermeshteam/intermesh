import uuid
import pytest
from nexus_sdk import NexusMessage, MessageType, NexusTask, TaskStatus


def test_nexus_message_creation():
    """Vérifie la conformité de création d'un message."""
    msg = NexusMessage(
        type=MessageType.MESSAGE,
        sender="agent_alpha",
        to="agent_beta",
        content={"data": "test_payload"}
    )
    assert msg.version == "nexus/v1"
    assert msg.sender == "agent_alpha"
    assert msg.to == "agent_beta"
    assert msg.type == MessageType.MESSAGE
    assert isinstance(msg.id, str)
    assert len(msg.id) > 0


def test_nexus_message_serialization():
    """Vérifie l'idempotence de la sérialisation/désérialisation JSON."""
    msg_id = str(uuid.uuid4())
    original = NexusMessage(
        type=MessageType.REQUEST,
        sender="orchestrator",
        to="worker",
        content="execute_calc",
        reply_to="parent-id-123",
        msg_id=msg_id,
        token="jwt.mock.token"
    )
    
    raw_json = original.to_json()
    restored = NexusMessage.from_json(raw_json)
    
    assert restored.id == original.id
    assert restored.type == MessageType.REQUEST
    assert restored.sender == "orchestrator"
    assert restored.to == "worker"
    assert restored.content == "execute_calc"
    assert restored.reply_to == "parent-id-123"
    assert restored.token == "jwt.mock.token"


def test_task_status_lifecycle():
    """Vérifie le cycle de vie formel d'une tâche."""
    task = NexusTask(
        title="Traitement Image",
        orchestrator="agent_a",
        assignee="agent_b",
        input_data={"image_url": "https://example.com/image.png"}
    )
    
    assert task.status == TaskStatus.PENDING
    assert task.output_data is None
    
    # Transition vers RUNNING
    task.update_status(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    
    # Transition vers COMPLETED
    task.update_status(TaskStatus.COMPLETED, output_data={"status": "processed", "objects": 3})
    assert task.status == TaskStatus.COMPLETED
    assert task.output_data["objects"] == 3
    assert task.error_message is None
