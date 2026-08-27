<div align="center">

# 🌐 NEXUS PROTOCOL

### The universal open-source coordination protocol for AI agents

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Protocol](https://img.shields.io/badge/Protocol-nexus%2Fv1-00D4FF.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-brightgreen.svg)]()
[![Encryption](https://img.shields.io/badge/E2E-RSA--2048%20%2B%20AES--256--GCM-red.svg)]()

**Nexus is the neutral, open standard that lets AI agents — regardless of language,
framework, or vendor — discover each other, communicate securely, and collaborate.**

[Manifesto](docs/MANIFESTO.md) · [RFC 001](docs/RFC-001-CORE-PROTOCOL.md) · [Security model](docs/SECURITY-AND-ENCRYPTION.md) · [API reference](docs/API-REFERENCE.md) · [Agent integration](docs/AGENT-INTEGRATION.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## Architecture

```text
┌────────────────────────┐                   ┌────────────────────────┐
│  Python Agent          │                   │  Node.js / TS Agent    │
└───────────┬────────────┘                   └───────────┬────────────┘
            │ 🔒 E2E (RSA-OAEP + AES-GCM)                │ 🔒 E2E
            ▼                                            ▼
 ══════════════════════════════════════════════════════════════════════
                      NEXUS COORDINATION HUB
   [ Discovery ]  [ JWT Auth ]  [ RBAC ]  [ Audit Log ]  [ Rate Limit ]
 ══════════════════════════════════════════════════════════════════════
            ▲                                            ▲
            │  Hub-to-Hub Federation (cross-organization peering)
            ▼                                            ▼
┌────────────────────────┐                   ┌────────────────────────┐
│  Partner Org Hub       │                   │  Future SDKs (Go/Rust) │
└────────────────────────┘                   └────────────────────────┘
```

---

## Quick start

```bash
pip install nexus-mesh      # Python SDK + the `nexus` CLI
npm install nexus-mesh      # JavaScript / TypeScript SDK
```

Or from source:

```bash
git clone https://github.com/mrlomemba-cmd/nexus.git
cd nexus
python3 -m venv venv && source venv/bin/activate
pip install -e ./sdk-python
```

**1. Start the hub**

```bash
nexus hub
```

**2. Write a worker agent**

```python
from nexus_sdk import NexusAgent

agent = NexusAgent(name="calc_bot", capabilities=["calculate"], roles=["worker"])

@agent.on_task
async def run(input_data, task):
    return {"result": eval(input_data["expression"])}

await agent.connect()
```

**3. Delegate work from the CLI**

```bash
nexus task calc_bot "Compute" '{"expression": "42 * 2"}'
```

---

## Features

| | |
|---|---|
| 🔐 **End-to-end encryption** | RSA-2048-OAEP + AES-256-GCM. The hub routes ciphertext it cannot read. |
| 🆔 **Verifiable identity** | SHA-256 fingerprints over roles, permissions, and capabilities — tampering is rejected at registration. |
| 🎫 **JWT authentication** | Every message after registration carries a hub-signed token. |
| 🛡️ **RBAC** | Per-agent access policies enforced at the hub. |
| 🔍 **Discovery** | Find agents by capability, role, metadata, or name. |
| 📋 **Tasks & workflows** | Async distributed task lifecycle: `pending → running → completed/failed`. |
| 🔌 **Framework adapters** | Bridge LangChain, CrewAI, AutoGen, LlamaIndex (Python) and LangChain.js, LlamaIndex.TS (JS) without changing a line of the wrapped agent. |
| 🧵 **Orchestration helpers** | `NexusPipeline` chains steps across agents found by capability; `fan_out`/`fanOut` runs branches in parallel and aggregates results. |
| 🌐 **Federation** | Hub-to-hub peering across organizations, E2E preserved end to end. |
| 📜 **Immutable audit log** | Merkle-chained events; any retroactive edit breaks the chain. |
| 🚦 **Rate limiting** | Token-bucket throttling per agent. |
| 🛠️ **Developer CLI** | `nexus hub`, `discover`, `ping`, `ask`, `task`, `keygen`, `dashboard`, `docs`. |
| 📊 **Mission Control** | Real-time dark-mode web dashboard. |
| 🐳 **Docker** | Full stack via `docker compose up -d`. |

---

## Repository layout

| Path | Purpose |
|---|---|
| `sdk-python/` | Official Python SDK (`nexus-sdk`) and the `nexus` CLI — adapters for LangChain, CrewAI, AutoGen, LlamaIndex |
| `sdk-js/` | Official JavaScript/TypeScript SDK — adapters for LangChain.js, LlamaIndex.TS |
| `server/` | The coordination hub |
| `dashboard/` | Mission Control web UI |
| `docs/` | RFC-001, security spec, API reference |
| `examples/` | Runnable agents (Python and Node.js); `examples/frameworks/` wraps real LangChain/LlamaIndex/CrewAI/AutoGen objects |
| `tests/` | 18 unit + integration tests |
| `docker/` | Container images for hub, agents, dashboard |

---

## Development

```bash
pip install -e ./sdk-python
pip install pytest pytest-asyncio
pytest -v
```

Full stack in containers:

```bash
docker compose up --build -d
# Hub:       ws://localhost:8765
# Dashboard: http://localhost:8080
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Protocol changes must be proposed as an amendment
to [RFC-001](docs/RFC-001-CORE-PROTOCOL.md) before implementation, and must land in **both**
the Python and JavaScript SDKs to preserve interoperability.

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Please do not open public issues for security problems.

## License

[Apache 2.0](LICENSE)
