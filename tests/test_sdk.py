"""Tests basiques du SDK Nexus — exécutables sans Hub."""
from nexus_sdk import NexusAgent, NexusMessage, MessageType, AgentIdentity, NexusTask, TaskStatus
from nexus_sdk.crypto import generate_keypair, get_public_key_pem, encrypt_for, decrypt_with


def test_identity_fingerprint():
    """L'empreinte doit être stable et vérifiable."""
    identity = AgentIdentity(name="test", capabilities=["a", "b"], roles=["dev"])
    assert identity.verify_fingerprint()
    assert len(identity.fingerprint) == 64  # SHA-256 hex
    print("✅ test_identity_fingerprint")


def test_message_serialization():
    """Un message sérialisé puis désérialisé doit être identique."""
    msg = NexusMessage(type=MessageType.MESSAGE, sender="a", to="b", content="hello")
    restored = NexusMessage.from_json(msg.to_json())
    assert restored.sender == "a"
    assert restored.to == "b"
    assert restored.content == "hello"
    assert restored.type == MessageType.MESSAGE
    print("✅ test_message_serialization")


def test_task_lifecycle():
    """Le cycle de vie d'une tâche doit suivre les états corrects."""
    task = NexusTask(title="Test", orchestrator="a", assignee="b", input_data={"x": 1})
    assert task.status == TaskStatus.PENDING
    task.update_status(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    task.update_status(TaskStatus.COMPLETED, output_data={"result": 42})
    assert task.status == TaskStatus.COMPLETED
    assert task.output_data == {"result": 42}
    print("✅ test_task_lifecycle")


def test_e2e_encryption():
    """Le chiffrement E2E doit être réversible."""
    kp = generate_keypair()
    pk_pem = get_public_key_pem(kp)
    original = "Message secret ultra confidentiel 🔒"
    encrypted = encrypt_for(pk_pem, original)
    assert encrypted != original
    decrypted = decrypt_with(kp, encrypted)
    assert decrypted == original
    print("✅ test_e2e_encryption")


def test_agent_creation():
    """Un agent doit se créer avec une identité et des clés."""
    agent = NexusAgent(name="test_agent", capabilities=["search"], roles=["worker"])
    assert agent.identity.name == "test_agent"
    assert agent.identity.verify_fingerprint()
    assert agent._public_key_pem.startswith("-----BEGIN PUBLIC KEY-----")
    print("✅ test_agent_creation")


if __name__ == "__main__":
    test_identity_fingerprint()
    test_message_serialization()
    test_task_lifecycle()
    test_e2e_encryption()
    test_agent_creation()
    print("\n🎉 Tous les tests du SDK Nexus sont validés !")
