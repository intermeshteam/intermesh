import pytest
from intermesh.message import InterMeshMessage, MessageType, ValidationError
from intermesh.task import InterMeshTask, TaskStatus, TaskValidationError


def test_message_validation_nominal():
    payload = {
        "id": "12345",
        "version": "intermesh/v1",
        "type": "message",
        "sender": "agent_a",
        "to": "agent_b",
        "content": "hello",
        "timestamp": 1700000000.0
    }
    msg = InterMeshMessage.from_dict(payload)
    assert msg.id == "12345"
    assert msg.sender == "agent_a"
    assert msg.type == MessageType.MESSAGE


def test_message_validation_missing_mandatory():
    payload = {
        "version": "intermesh/v1",
        "sender": "agent_a"
    }
    with pytest.raises(ValidationError) as exc:
        InterMeshMessage.from_dict(payload)
    assert "Champ obligatoire absent" in str(exc.value)


def test_message_validation_bad_types():
    payload = {
        "type": "message",
        "sender": 12345  # Type incorrect, attendu : str
    }
    with pytest.raises(ValidationError) as exc:
        InterMeshMessage.from_dict(payload)
    assert "sender" in str(exc.value)


def test_message_validation_bad_version():
    payload = {
        "version": "nexus/v2",  # Version non supportee
        "type": "message",
        "sender": "agent_a"
    }
    with pytest.raises(ValidationError) as exc:
        InterMeshMessage.from_dict(payload)
    assert "Version de protocole non supportee" in str(exc.value)


def test_message_validation_bad_json():
    bad_raw_json = '{"type": "message", "sender": "agent_a",}'  # Virgule terminale invalide en JSON standard
    with pytest.raises(ValidationError) as exc:
        InterMeshMessage.from_json(bad_raw_json)
    assert "JSON invalide" in str(exc.value)


def test_task_validation_nominal():
    payload = {
        "task_id": "task-99",
        "title": "Compute task",
        "orchestrator": "master",
        "assignee": "worker",
        "input_data": {"x": 1},
        "status": "pending"
    }
    task = InterMeshTask.from_dict(payload)
    assert task.task_id == "task-99"
    assert task.status == TaskStatus.PENDING


def test_task_validation_bad_status():
    payload = {
        "title": "Compute task",
        "orchestrator": "master",
        "assignee": "worker",
        "input_data": {"x": 1},
        "status": "not_started_invalid"  # Statut invalide
    }
    with pytest.raises(TaskValidationError) as exc:
        InterMeshTask.from_dict(payload)
    assert "Statut de tache invalide" in str(exc.value)
