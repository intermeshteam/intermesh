"""
Adaptateurs vers les frameworks d'agents.

Les frameworks réels ne sont pas installés — les importer ferait de
LangChain et de ses dépendances transitives un prérequis de la suite de
tests, alors que le SDK est précisément conçu pour ne pas en dépendre.

Les doublures ci-dessous reproduisent la convention d'appel exacte de
chaque framework : c'est elle, et rien d'autre, que l'adaptateur détecte.
"""

import asyncio
import time

import pytest

from nexus_sdk.adapters import AdapterError, NexusAdapter, adapt, detect_invoker
from nexus_sdk.adapters.autogen import NexusAutoGenAdapter
from nexus_sdk.adapters.crewai import NexusCrewAIAdapter
from nexus_sdk.adapters.langchain import NexusLangChainAdapter
from nexus_sdk.adapters.llamaindex import NexusLlamaIndexAdapter


# ----------------------------------------------------------------------
# Doublures
# ----------------------------------------------------------------------

class FakeRunnable:
    """LangChain : `Runnable.invoke(input)` synchrone, `ainvoke` asynchrone."""
    def invoke(self, data):
        return {"output": f"analysé: {data.get('input')}"}

    async def ainvoke(self, data):
        return {"output": f"async: {data.get('input')}"}


class FakeSyncRunnable:
    """Un Runnable sans variante asynchrone — le cas le plus courant."""
    def __init__(self):
        self.thread_ids = []

    def invoke(self, data):
        import threading
        self.thread_ids.append(threading.get_ident())
        time.sleep(0.25)
        return {"output": data["input"].upper()}


class FakeCrew:
    """CrewAI : `kickoff(inputs={...})` — mot-clé, pas positionnel."""
    def __init__(self):
        self.received = None

    def kickoff(self, inputs=None):
        self.received = inputs
        return FakeCrewOutput(f"rapport sur {inputs.get('sujet')}")


class FakeCrewOutput:
    """CrewAI renvoie un objet, pas un dict : non sérialisable tel quel."""
    def __init__(self, raw):
        self.raw = raw
        self.token_usage = object()   # délibérément non sérialisable


class FakeAutoGen:
    """AutoGen : `run(message)` sur une chaîne."""
    def run(self, message):
        return f"réponse à « {message} »"


class FakeQueryEngine:
    """LlamaIndex : `query(str)` renvoyant un objet à attribut `response`."""
    def query(self, q):
        return FakeResponse(f"trouvé : {q}")


class FakeResponse:
    def __init__(self, response):
        self.response = response


class NotAnAgent:
    """Ni méthode connue, ni appelable."""


# ----------------------------------------------------------------------
# Détection
# ----------------------------------------------------------------------

def test_async_variant_is_preferred_over_sync():
    """Mobiliser un thread alors qu'une coroutine existe serait du gâchis."""
    fn, is_async, style = detect_invoker(FakeRunnable())
    assert fn.__name__ == "ainvoke"
    assert is_async is True
    assert style == "single"
    print("✓ La variante asynchrone est préférée")


def test_crew_kickoff_uses_keyword_style():
    fn, is_async, style = detect_invoker(FakeCrew())
    assert fn.__name__ == "kickoff"
    assert style == "inputs_kw", "kickoff prend inputs= en mot-clé"
    print("✓ Convention kickoff(inputs=…) détectée")


def test_plain_callable_is_accepted():
    fn, is_async, _ = detect_invoker(lambda d: {"ok": True})
    assert callable(fn) and is_async is False

    async def coro(d):
        return {"ok": True}
    _, is_async2, _ = detect_invoker(coro)
    assert is_async2 is True
    print("✓ Fonctions simples, sync et async, acceptées")


def test_unusable_object_fails_with_guidance():
    with pytest.raises(AdapterError, match="invoke_method"):
        detect_invoker(NotAnAgent())
    print("✓ Objet inutilisable rejeté avec une piste")


def test_explicit_method_overrides_detection():
    fn, _, _ = detect_invoker(FakeRunnable(), prefer="invoke")
    assert fn.__name__ == "invoke", "le choix explicite doit primer"

    with pytest.raises(AdapterError, match="inexistante"):
        detect_invoker(FakeRunnable(), prefer="inexistante")
    print("✓ invoke_method= force la méthode")


# ----------------------------------------------------------------------
# Pontage
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_langchain_agent_receives_the_task_dict():
    a = NexusLangChainAdapter(FakeRunnable(), name="lc", capabilities=["analysis"])
    out = await a._handle_task({"input": "marché"}, None)
    assert out == {"output": "async: marché"}
    assert a.identity.capabilities == ["analysis"]
    print("✓ Agent LangChain ponté")


@pytest.mark.asyncio
async def test_crew_receives_task_input_as_its_inputs():
    """Le dict de la tâche Nexus alimente les {placeholders} du Crew."""
    crew = FakeCrew()
    a = NexusCrewAIAdapter(crew, name="crew", capabilities=["research"])
    out = await a._handle_task({"sujet": "agents IA"}, None)

    assert crew.received == {"sujet": "agents IA"}
    assert out == "rapport sur agents IA", "l'objet CrewOutput doit être aplati"
    print("✓ Crew alimenté par l'entrée de tâche")


@pytest.mark.asyncio
async def test_autogen_receives_a_string_not_a_dict():
    a = NexusAutoGenAdapter(FakeAutoGen(), name="ag", capabilities=["reasoning"])
    out = await a._handle_task({"message": "bonjour"}, None)
    assert out == "réponse à « bonjour »"
    print("✓ AutoGen reçoit une chaîne")


@pytest.mark.asyncio
async def test_llamaindex_response_object_is_flattened():
    a = NexusLlamaIndexAdapter(FakeQueryEngine(), name="li", capabilities=["rag"])
    out = await a._handle_task({"query": "quota"}, None)
    assert out == "trouvé : quota"
    print("✓ Réponse LlamaIndex aplatie")


@pytest.mark.asyncio
async def test_non_serializable_output_never_breaks_the_wire():
    """Un objet impossible à sérialiser doit dégrader, pas faire échouer."""
    class Opaque:
        def __init__(self):
            self.socket = object()

    a = adapt(lambda d: Opaque(), name="op", capabilities=["x"])
    out = await a._handle_task({}, None)

    import json
    json.dumps(out)   # ne doit pas lever
    assert isinstance(out, str)
    print("✓ Sortie opaque ramenée à du sérialisable")


# ----------------------------------------------------------------------
# Le point critique : ne pas bloquer la boucle
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_agent_does_not_freeze_the_event_loop():
    """
    `invoke()` d'un agent LLM bloque plusieurs secondes. Appelée dans la
    boucle asyncio, elle gèlerait tout l'agent Nexus : plus aucune tâche
    reçue, plus aucun message routé, pendant toute la durée de l'appel.
    """
    a = NexusLangChainAdapter(FakeSyncRunnable(), name="sync", capabilities=["x"])

    ticks = 0

    async def heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.02)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    out = await a._handle_task({"input": "test"}, None)
    beat.cancel()

    assert out == {"output": "TEST"}
    assert ticks >= 5, (
        f"la boucle n'a battu que {ticks} fois pendant un appel de 250 ms — "
        "l'agent synchrone a bloqué la boucle"
    )
    print(f"✓ Boucle restée vivante ({ticks} battements pendant l'appel bloquant)")


@pytest.mark.asyncio
async def test_sync_call_really_runs_off_the_main_thread():
    import threading
    fake = FakeSyncRunnable()
    a = NexusLangChainAdapter(fake, name="thr", capabilities=["x"])
    await a._handle_task({"input": "x"}, None)

    assert fake.thread_ids and fake.thread_ids[0] != threading.get_ident()
    print("✓ L'appel synchrone s'exécute hors du thread principal")


@pytest.mark.asyncio
async def test_run_in_thread_can_be_disabled():
    import threading
    fake = FakeSyncRunnable()
    a = NexusLangChainAdapter(fake, name="inline", capabilities=["x"], run_in_thread=False)
    await a._handle_task({"input": "x"}, None)

    assert fake.thread_ids[0] == threading.get_ident()
    print("✓ run_in_thread=False exécute en ligne")


# ----------------------------------------------------------------------
# Transformations
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_and_output_adapters():
    a = adapt(
        lambda s: {"len": len(s)},
        name="custom", capabilities=["x"],
        input_adapter=lambda d: d["texte"],
        output_adapter=lambda r: {"longueur": r["len"], "unite": "caracteres"},
    )
    assert await a._handle_task({"texte": "bonjour"}, None) == {
        "longueur": 7, "unite": "caracteres"}
    print("✓ Transformations d'entrée et de sortie")


@pytest.mark.asyncio
async def test_adapter_also_answers_direct_requests():
    """Un agent ponté répond aussi bien à `ask()` qu'à `submit_task()`."""
    class Msg:
        content = {"input": "ping"}

    a = NexusLangChainAdapter(FakeRunnable(), name="both", capabilities=["x"])
    assert await a._handle_request(Msg()) == {"output": "async: ping"}
    print("✓ Le pont sert aussi les requêtes directes")


def test_adapter_is_a_real_nexus_agent():
    """Il doit se comporter comme un agent natif, pas comme un cas à part."""
    from nexus_sdk import NexusAgent

    a = adapt(lambda d: d, name="x", capabilities=["c"], roles=["worker"])
    assert isinstance(a, NexusAgent)
    assert a.identity.verify_fingerprint()
    assert a.identity.capabilities == ["c"]
    assert a.identity.roles == ["worker"]
    assert "NexusAdapter" in repr(a)
    print("✓ L'adaptateur est un agent Nexus à part entière")


# ----------------------------------------------------------------------
# Bout en bout, à travers un vrai Hub
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wrapped_agent_is_discoverable_and_usable_over_the_wire():
    """
    La promesse du pilier : un agent d'un autre framework, sans une ligne
    de changement, devient découvrable par ses capacités et exécute des
    tâches déléguées à distance.
    """
    import os, subprocess, sys, tempfile
    from nexus_sdk import NexusAgent

    port = 8809
    work = tempfile.mkdtemp()
    os.system(f"fuser -k {port}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "acme",
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2)

    try:
        # Un Crew CrewAI existant, exposé tel quel.
        crew = FakeCrew()
        worker = NexusCrewAIAdapter(
            crew, name="equipe_recherche", capabilities=["research"],
            hub_url=f"ws://localhost:{port}", encrypt=False)
        await worker.connect()

        # Un orchestrateur qui ne sait rien de CrewAI.
        lead = NexusAgent(name="lead", roles=["admin"],
                          hub_url=f"ws://localhost:{port}", encrypt=False)
        await lead.connect()
        await asyncio.sleep(0.6)

        found = await lead.discover(capabilities=["research"])
        assert found["count"] == 1
        assert found["agents"][0]["name"] == worker.qualified_name

        result = await lead.submit_task(
            "Étude de marché", worker.qualified_name,
            {"sujet": "protocoles d'agents"}, timeout=15)

        assert result == "rapport sur protocoles d'agents"
        assert crew.received == {"sujet": "protocoles d'agents"}

        await worker.ws.close()
        await lead.ws.close()
        print("✓ Agent CrewAI découvert et exécuté via le protocole")
    finally:
        hub.terminate()
        try:
            hub.wait(timeout=5)
        except subprocess.TimeoutExpired:
            hub.kill()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
