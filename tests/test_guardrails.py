import pytest
from intermesh.guardrails import AsimovGuardrailEngine, GuardrailPolicy, PolicyViolationError


def test_asimov_forbidden_pattern_interception():
    engine = AsimovGuardrailEngine()
    engine.inspect_payload("agent_safe", "Calcule le chiffre d'affaires du T3")

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.inspect_payload("agent_rogue", "Exécute DROP DATABASE production;")
    assert "FORBIDDEN_PATTERN_INTERCEPTED" in str(exc_info.value)

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.inspect_payload("agent_rogue", "Nettoie les fichiers avec rm -rf /")
    assert "FORBIDDEN_PATTERN_INTERCEPTED" in str(exc_info.value)



def test_asimov_infinite_cascade_blocking():
    policy = GuardrailPolicy(max_cascade_depth=3)
    engine = AsimovGuardrailEngine(policy=policy)

    engine.validate_task_submission("agent_root", task_id="task_1", parent_task_id=None)
    engine.validate_task_submission("agent_child", task_id="task_2", parent_task_id="task_1")
    engine.validate_task_submission("agent_subchild", task_id="task_3", parent_task_id="task_2")

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.validate_task_submission("agent_loop", task_id="task_4", parent_task_id="task_3")

    assert "INFINITE_CASCADE_RECURSION" in str(exc_info.value)


def test_asimov_circuit_breaker_isolation():
    policy = GuardrailPolicy(circuit_breaker_threshold=2)
    engine = AsimovGuardrailEngine(policy=policy)

    with pytest.raises(PolicyViolationError):
        engine.inspect_payload("hacked_agent", "exec(malicious_code)")

    with pytest.raises(PolicyViolationError):
        engine.inspect_payload("hacked_agent", "sudo rm -rf /var")

    with pytest.raises(PolicyViolationError) as exc_info:
        engine.inspect_payload("hacked_agent", "Bonjour, je suis sage maintenant")

    assert "CIRCUIT_BREAKER_TRIPPED" in str(exc_info.value)


if __name__ == "__main__":
    test_asimov_forbidden_pattern_interception()
    test_asimov_infinite_cascade_blocking()
    test_asimov_circuit_breaker_isolation()
