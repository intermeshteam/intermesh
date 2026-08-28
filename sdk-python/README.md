# InterMesh — Python SDK

The official Python SDK for **InterMesh Protocol**, the universal open-source coordination
protocol for AI agents.

Nexus lets agents — regardless of language, framework, or vendor — discover each other,
communicate with end-to-end encryption, and collaborate on distributed tasks.

```bash
pip install intermesh
```

> The distribution is named `intermesh`; the import module is `intermesh`.

---

## Quick start

**Start the coordination hub:**

```bash
nexus hub
```

**Write a worker agent:**

```python
import asyncio
from intermesh import InterMeshAgent

async def compute(input_data, task):
    return {"result": input_data["a"] + input_data["b"]}

async def main():
    agent = InterMeshAgent(
        name="calc_bot",
        capabilities=["calculate"],
        roles=["worker"],
    )
    agent.on_task(compute)
    await agent.connect()
    await asyncio.Future()   # stay online

asyncio.run(main())
```

**Delegate work from an orchestrator:**

```python
from intermesh import InterMeshAgent

orchestrator = InterMeshAgent(name="lead", roles=["admin"])
await orchestrator.connect()

# Find an agent by capability, then hand it a task
found = await orchestrator.discover(capabilities=["calculate"])
result = await orchestrator.submit_task(
    title="Add two numbers",
    assignee=found["agents"][0]["name"],
    input_data={"a": 20, "b": 22},
)
# {"result": 42}  — encrypted end-to-end in transit
```

---

## Bridge an existing framework agent

Wrap an existing agent without changing a line of it — it becomes discoverable
and receives delegated tasks like a native InterMesh agent.

A LangChain runnable:

```python
from intermesh import from_langchain

agent = from_langchain(my_chain, name="analyst", capabilities=["market_analysis"])
await agent.connect()
```

Anything else — a CrewAI crew, an AutoGen agent, a LlamaIndex engine, or a
plain function — goes through `from_callable`:

```python
import asyncio
from intermesh import from_callable

async def run(data):
    # to_thread keeps a blocking LLM call off the event loop, so the agent
    # stays responsive instead of freezing for the whole inference.
    return await asyncio.to_thread(lambda: my_crew.kickoff(inputs=data))

agent = from_callable(run, name="research", capabilities=["research"])
await agent.connect()
```

Or as a decorator:

```python
from intermesh import intermesh_service

@intermesh_service(name="summarizer", capabilities=["summarize"])
def summarize(data):
    return {"summary": my_model(data["text"])}
```

Runnable examples for all four frameworks are in
[`examples/frameworks/`](https://github.com/mrlomemba-cmd/nexus/tree/main/examples/frameworks).

## Orchestrate multiple agents

```python
from intermesh import InterMeshPipeline

pipeline = (
    InterMeshPipeline(orchestrator)
    .step("Translate", capabilities=["translate"])
    .step("Calculate", capabilities=["calculate"],
          input_fn=lambda prev: {"expression": prev["translated_text"]})
)
result = await pipeline.run({"text": "compute forty two doubled"})
```

`fan_out(orchestrator, branches, capabilities=...)` runs independent branches in
parallel instead. Full guide: [`docs/AGENT-INTEGRATION.md`](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/AGENT-INTEGRATION.md).

---

## Features

- **End-to-end encryption** — RSA-2048-OAEP + AES-256-GCM. The hub routes ciphertext it cannot read.
- **Verifiable identity** — SHA-256 fingerprints over roles, permissions, and capabilities.
- **JWT authentication** — every message after registration carries a hub-signed token.
- **Role-based access control** — per-agent policies enforced at the hub.
- **Discovery** — locate agents by capability, role, metadata, or name.
- **Distributed tasks** — async lifecycle: `pending → running → completed / failed`.
- **Federation** — hub-to-hub peering across organizations, encryption preserved end to end.
- **Immutable audit log** — Merkle-chained events; retroactive edits break the chain.
- **Rate limiting** — token-bucket throttling per agent.
- **Developer CLI** — `nexus hub | discover | ping | ask | task | keygen | dashboard | docs`.

---

## API summary

| Method | Purpose |
|---|---|
| `connect()` | Open the connection and obtain a JWT |
| `send(to, content)` | Fire-and-forget encrypted message |
| `ask(to, content)` | Encrypted request, awaits the reply |
| `discover(...)` | Find agents by capability, role, or metadata |
| `submit_task(title, assignee, input_data)` | Delegate a task and await its result |
| `who_is(name)` | Fetch an agent's certified identity and public key |
| `on_message / on_request / on_task` | Register inbound handlers |

Full reference: [`docs/API-REFERENCE.md`](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/API-REFERENCE.md)

---

## Documentation

- [Agent integration — adapters and orchestration](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/AGENT-INTEGRATION.md)
- [RFC-001 — Core protocol specification](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/RFC-001-CORE-PROTOCOL.md)
- [Security and encryption model](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/SECURITY-AND-ENCRYPTION.md)
- [API reference](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/API-REFERENCE.md)

## License

[Apache 2.0](https://github.com/mrlomemba-cmd/nexus/blob/main/LICENSE)
