"""Tests de la traduction de schémas Nexus (déterministe, pas de modèle IA)."""

import os
import subprocess
import sys
import tempfile
import time

import pytest

from nexus_sdk import NexusAgent
from nexus_sdk.schema import SchemaError, SchemaRegistry, default_registry, translate_payload

PORT = 8895


# ----------------------------------------------------------------------
# Unitaire : registre de schémas, sans Hub
# ----------------------------------------------------------------------

def test_translate_between_two_named_schemas():
    out = translate_payload({"prompt": "salut"}, target_schema="llama_style", source_schema="claude_style")
    assert out == {"user_query": "salut"}
    print("✓ Traduction explicite entre deux schémas nommés")


def test_heuristic_translation_without_a_declared_source_schema():
    """Un champ non ambigu se traduit même si l'émetteur n'a jamais déclaré de schéma."""
    out = translate_payload({"query": "salut", "temperature": 0.2}, target_schema="claude_style")
    assert out["prompt"] == "salut"
    assert out["temperature"] == 0.2  # inchangé : même nom des deux côtés
    print("✓ Traduction par synonyme non ambigu, sans schéma source déclaré")


def test_unresolved_field_is_passed_through_verbatim():
    out = translate_payload({"totally_custom_field": 42}, target_schema="claude_style")
    assert out == {"totally_custom_field": 42}
    print("✓ Un champ non reconnu traverse sans modification")


def test_unregistered_target_schema_raises():
    with pytest.raises(SchemaError):
        translate_payload({"prompt": "x"}, target_schema="does_not_exist")
    print("✓ Schéma cible inconnu signalé explicitement")


def test_custom_registry_is_isolated_from_the_default_one():
    registry = SchemaRegistry()
    registry.register("mine", {"txt": "input_text"})
    registry.register("theirs", {"body": "input_text"})

    out = registry.translate({"txt": "salut"}, target_schema="theirs", source_schema="mine")
    assert out == {"body": "salut"}

    with pytest.raises(SchemaError):
        default_registry().translate({}, target_schema="mine")  # inconnu du registre par défaut
    print("✓ Un registre personnalisé n'affecte pas le registre par défaut")


# ----------------------------------------------------------------------
# Intégration : contre un vrai Hub, deux agents en désaccord de format
# ----------------------------------------------------------------------

@pytest.fixture
def hub():
    work = tempfile.mkdtemp()
    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(PORT), "--org", "acme",
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    yield
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_orchestrator_and_worker_never_have_to_agree_on_a_wire_format(hub):
    """
    L'orchestrateur parle 'llama_style' (user_query/answer), le worker parle
    'claude_style' (prompt/response). Ni l'un ni l'autre n'a été codé pour
    connaître le format de l'autre : la traduction est automatique dans les
    deux sens (requête et réponse), pilotée par le schéma que chacun déclare
    à l'enregistrement.
    """
    worker = NexusAgent(name="worker", org_id="acme", hub_url=f"ws://localhost:{PORT}",
                        schema="claude_style", encrypt=False)

    @worker.on_task
    async def _handle(input_data, task):
        assert "prompt" in input_data, f"le worker attend 'prompt', reçu {input_data}"
        return {"response": f"echo: {input_data['prompt']}"}

    await worker.connect()

    lead = NexusAgent(name="lead", org_id="acme", hub_url=f"ws://localhost:{PORT}",
                      schema="llama_style", roles=["admin"], encrypt=False)
    await lead.connect()

    result = await lead.submit_task("Traduction cross-schéma", "acme/worker",
                                    {"user_query": "bonjour"}, timeout=5.0)

    assert result == {"answer": "echo: bonjour"}, f"la réponse doit revenir dans LE schéma de lead, reçu {result}"

    await worker.close()
    await lead.close()
    print("✓ Traduction automatique bidirectionnelle entre deux schémas différents")


@pytest.mark.asyncio
async def test_same_schema_on_both_sides_is_left_untouched(hub):
    """Aucune traduction quand les deux agents partagent déjà le même schéma."""
    worker = NexusAgent(name="worker2", org_id="acme", hub_url=f"ws://localhost:{PORT}",
                        schema="claude_style", encrypt=False)

    @worker.on_task
    async def _handle(input_data, task):
        return {"response": input_data["prompt"].upper()}

    await worker.connect()

    lead = NexusAgent(name="lead2", org_id="acme", hub_url=f"ws://localhost:{PORT}",
                      schema="claude_style", roles=["admin"], encrypt=False)
    await lead.connect()

    result = await lead.submit_task("Même schéma", "acme/worker2", {"prompt": "silence"}, timeout=5.0)
    assert result == {"response": "SILENCE"}

    await worker.close()
    await lead.close()
    print("✓ Aucune traduction inutile quand les schémas coïncident déjà")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
