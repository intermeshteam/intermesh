"""
`NexusPipeline` et `fan_out` composent `discover()`/`submit_task()` sans
toucher au fil : les tests unitaires se contentent donc d'un orchestrateur
factice qui les reproduit. Le dernier test seul passe par un vrai Hub,
pour vérifier que la composition tient aussi en conditions réelles.
"""

import asyncio

import pytest

from nexus_sdk.pipeline import NexusPipeline, PipelineError, fan_out


class FakeOrchestrator:
    """
    Reproduit `discover`/`submit_task` sans réseau : un registre de
    capacités vers noms d'agent, et une table de résultats par titre de
    tâche. `calls` trace ce qui a été soumis, pour vérifier le câblage
    entrée/sortie entre étapes.
    """

    def __init__(self, agents_by_capability: dict, outputs_by_title: dict):
        self.agents_by_capability = agents_by_capability
        self.outputs_by_title = outputs_by_title
        self.calls = []

    async def discover(self, capabilities=None, roles=None, metadata=None):
        for cap in capabilities or []:
            if cap in self.agents_by_capability:
                name = self.agents_by_capability[cap]
                return {"count": 1, "agents": [{"name": name}]}
        return {"count": 0, "agents": []}

    async def submit_task(self, title, assignee, input_data, timeout=15.0):
        self.calls.append((title, assignee, input_data))
        if title not in self.outputs_by_title:
            raise RuntimeError(f"pas de sortie configurée pour '{title}'")
        result = self.outputs_by_title[title]
        if isinstance(result, Exception):
            raise result
        return result


# ----------------------------------------------------------------------
# NexusPipeline
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_chains_output_into_next_input():
    orch = FakeOrchestrator(
        agents_by_capability={"translate": "traducteur", "calculate": "calculateur"},
        outputs_by_title={
            "Traduire": {"translated_text": "42 * 2"},
            "Calculer": {"result": 84},
        },
    )
    pipeline = (
        NexusPipeline(orch)
        .step("Traduire", capabilities=["translate"])
        .step("Calculer", capabilities=["calculate"],
              input_fn=lambda prev: {"expression": prev["translated_text"]})
    )
    out = await pipeline.run({"text": "compute forty two doubled"})

    assert out.output == {"result": 84}
    assert [s.title for s in out.history] == ["Traduire", "Calculer"]
    assert orch.calls[1] == ("Calculer", "calculateur", {"expression": "42 * 2"})
    print("✓ Sortie d'une étape câblée dans l'entrée de la suivante")


@pytest.mark.asyncio
async def test_pipeline_resolves_agent_at_run_time_not_declaration_time():
    """L'agent devient disponible après la déclaration, avant l'exécution."""
    orch = FakeOrchestrator(agents_by_capability={}, outputs_by_title={"Étape": "ok"})
    pipeline = NexusPipeline(orch).step("Étape", capabilities=["x"])

    orch.agents_by_capability["x"] = "venu_en_retard"
    out = await pipeline.run()

    assert out.output == "ok"
    assert orch.calls[0][1] == "venu_en_retard"
    print("✓ Découverte différée jusqu'à l'exécution")


@pytest.mark.asyncio
async def test_pipeline_explicit_agent_skips_discovery():
    orch = FakeOrchestrator(agents_by_capability={}, outputs_by_title={"Étape": "ok"})
    pipeline = NexusPipeline(orch).step("Étape", agent="nommé_directement")
    out = await pipeline.run()

    assert orch.calls[0][1] == "nommé_directement"
    print("✓ Agent explicite : pas de découverte")


@pytest.mark.asyncio
async def test_pipeline_raises_when_no_agent_found():
    orch = FakeOrchestrator(agents_by_capability={}, outputs_by_title={})
    pipeline = NexusPipeline(orch).step("Étape", capabilities=["introuvable"])

    with pytest.raises(PipelineError, match="introuvable"):
        await pipeline.run()
    print("✓ Étape sans agent : erreur explicite")


@pytest.mark.asyncio
async def test_pipeline_stops_at_first_failing_step():
    orch = FakeOrchestrator(
        agents_by_capability={"a": "agent_a", "b": "agent_b"},
        outputs_by_title={"A": RuntimeError("échec distant")},
    )
    pipeline = (
        NexusPipeline(orch)
        .step("A", capabilities=["a"])
        .step("B", capabilities=["b"])
    )
    with pytest.raises(RuntimeError, match="échec distant"):
        await pipeline.run()

    assert len(orch.calls) == 1, "l'étape B ne doit jamais être soumise"
    print("✓ Échec d'une étape : les suivantes ne s'exécutent pas")


def test_pipeline_requires_at_least_a_target():
    with pytest.raises(PipelineError):
        NexusPipeline(FakeOrchestrator({}, {})).step("Étape")
    print("✓ Une étape sans agent ni critère est rejetée à la déclaration")


@pytest.mark.asyncio
async def test_empty_pipeline_raises():
    with pytest.raises(PipelineError):
        await NexusPipeline(FakeOrchestrator({}, {})).run()
    print("✓ Pipeline vide rejeté")


# ----------------------------------------------------------------------
# fan_out
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fan_out_runs_branches_concurrently_and_keys_results():
    orch = FakeOrchestrator(
        agents_by_capability={},
        outputs_by_title={"fr": {"revenue": 1}, "de": {"revenue": 2}},
    )
    results = await fan_out(
        orch,
        [("fr", {"region": "FR"}), ("de", {"region": "DE"})],
        agents={"fr": "marché_fr", "de": "marché_de"},
    )
    assert results == {"fr": {"revenue": 1}, "de": {"revenue": 2}}
    print("✓ Branches parallèles regroupées par clé")


@pytest.mark.asyncio
async def test_fan_out_isolates_a_failing_branch():
    """Une branche en échec ne doit pas empêcher de lire les autres."""
    orch = FakeOrchestrator(
        agents_by_capability={},
        outputs_by_title={"ok": "résultat", "ko": RuntimeError("boom")},
    )
    results = await fan_out(
        orch, [("ok", {}), ("ko", {})],
        agents={"ok": "a", "ko": "b"},
    )
    assert results["ok"] == "résultat"
    assert isinstance(results["ko"], RuntimeError)
    print("✓ Branche en échec isolée, les autres restent lisibles")


@pytest.mark.asyncio
async def test_fan_out_discovers_by_capability_per_branch():
    orch = FakeOrchestrator(
        agents_by_capability={"cap_a": "agent_a", "cap_b": "agent_b"},
        outputs_by_title={"a": "ra", "b": "rb"},
    )
    results = await fan_out(
        orch, [("a", {}), ("b", {})],
        capabilities={"a": ["cap_a"], "b": ["cap_b"]},
    )
    assert results == {"a": "ra", "b": "rb"}
    assert ("a", "agent_a", {}) in orch.calls
    assert ("b", "agent_b", {}) in orch.calls
    print("✓ Découverte par capacité, par branche")


# ----------------------------------------------------------------------
# Bout en bout, à travers un vrai Hub
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_end_to_end_over_a_real_hub():
    import os, subprocess, sys, tempfile
    from nexus_sdk import NexusAgent

    port = 8811
    tempfile.mkdtemp()
    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "acme",
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2)

    try:
        translator = NexusAgent(name="traducteur", capabilities=["translate"],
                                hub_url=f"ws://localhost:{port}", encrypt=False)

        @translator.on_task
        async def _translate(input_data, task):
            return {"translated_text": input_data["expression"].replace("double de ", "") + " * 2"}

        calculator = NexusAgent(name="calculateur", capabilities=["calculate"],
                                hub_url=f"ws://localhost:{port}", encrypt=False)

        @calculator.on_task
        async def _calculate(input_data, task):
            return {"result": eval(input_data["expression"])}

        await translator.connect()
        await calculator.connect()
        await asyncio.sleep(0.6)

        lead = NexusAgent(name="lead", roles=["admin"],
                          hub_url=f"ws://localhost:{port}", encrypt=False)
        await lead.connect()
        await asyncio.sleep(0.3)

        pipeline = (
            NexusPipeline(lead)
            .step("Traduire", capabilities=["translate"])
            .step("Calculer", capabilities=["calculate"],
                  input_fn=lambda prev: {"expression": prev["translated_text"]})
        )
        out = await pipeline.run({"expression": "double de 21"})

        assert out.output == {"result": 42}
        assert [s.agent for s in out.history] == ["traducteur", "calculateur"]

        for a in (translator, calculator, lead):
            await a.ws.close()
        print("✓ Pipeline exécuté de bout en bout à travers un vrai Hub")
    finally:
        hub.terminate()
        try:
            hub.wait(timeout=5)
        except subprocess.TimeoutExpired:
            hub.kill()
