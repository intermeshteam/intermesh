# Nexus Mesh — Python SDK

The official Python SDK for **Nexus Protocol**, the universal open-source coordination
protocol for AI agents.

Nexus lets agents — regardless of language, framework, or vendor — discover each other,
communicate with end-to-end encryption, and collaborate on distributed tasks.

```bash
pip install nexus-mesh
```

> The distribution is named `nexus-mesh`; the import module is `nexus_sdk`.

---

## Quick start

**Start the coordination hub:**

```bash
nexus hub
```

**Write a worker agent:**

```python
import asyncio
from nexus_sdk import NexusAgent

async def compute(input_data, task):
    return {"result": input_data["a"] + input_data["b"]}

async def main():
    agent = NexusAgent(
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
from nexus_sdk import NexusAgent

orchestrator = NexusAgent(name="lead", roles=["admin"])
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

- [RFC-001 — Core protocol specification](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/RFC-001-CORE-PROTOCOL.md)
- [Security and encryption model](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/SECURITY-AND-ENCRYPTION.md)
- [API reference](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/API-REFERENCE.md)

## License

[Apache 2.0](https://github.com/mrlomemba-cmd/nexus/blob/main/LICENSE)
