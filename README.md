<div align="center">

# 🌐 INTERMESH PROTOCOL

### The universal open-source coordination protocol for AI agents

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Protocol](https://img.shields.io/badge/Protocol-intermesh%2Fv1-00D4FF.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-brightgreen.svg)]()
[![Encryption](https://img.shields.io/badge/E2E-RSA--2048%20%2B%20AES--256--GCM-red.svg)]()

**InterMesh is the neutral, open standard that lets AI agents — regardless of language,
framework, or vendor — discover each other, communicate securely, and collaborate.**

[Manifesto](docs/MANIFESTO.md) · [RFC 001](docs/RFC-001-CORE-PROTOCOL.md) · [Security model](docs/SECURITY-AND-ENCRYPTION.md) · [API reference](docs/API-REFERENCE.md) · [Agent integration](docs/AGENT-INTEGRATION.md) · [Remote hub](docs/REMOTE-HUB.md) · [Benchmarks](docs/BENCHMARKS.md) · [Enterprise SSO](docs/ENTERPRISE-SSO.md) · [Air-gapped](docs/AIR-GAPPED.md) · [Contributing](CONTRIBUTING.md)

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
                      INTERMESH COORDINATION HUB
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
pip install intermesh      # Python SDK + the `intermesh` CLI
npm install intermesh      # JavaScript / TypeScript SDK
```

Or from source:

```bash
git clone https://github.com/intermeshteam/intermesh.git
cd intermesh
python3 -m venv venv && source venv/bin/activate
pip install -e ./sdk-python
```

**1. Start the hub**

```bash
intermesh hub
```

**2. Write a worker agent**

```python
from intermesh import InterMeshAgent

agent = InterMeshAgent(name="calc_bot", capabilities=["calculate"], roles=["worker"])

@agent.on_task
async def run(input_data, task):
    return {"result": input_data["a"] + input_data["b"]}

agent.run()          # connects, then stays in service
```

**3. Delegate work from the CLI**

```bash
intermesh task calc_bot "Add two numbers" '{"a": 20, "b": 22}'
```

**4. Or bring an agent written in any language**

No SDK needed for the foreign side. Your program reads JSON on stdin and
writes JSON on stdout — that is the whole contract:

```bash
intermesh serve --name pricing --exec "./pricing-engine" --capability pricing
```

That works for a Go or Rust binary, a Node or Ruby script, even a shell
one-liner. Already have an HTTP service? Point at it instead — nothing to
restart:

```bash
intermesh serve --name scoring --http http://localhost:9000/task
```

From Python, the same thing in one line:

```python
InterMeshAgent.from_command(["node", "agent.js"], name="pricing").run()
```

Non-JSON stdout is wrapped as `{"output": "..."}`, so an `echo` is a valid
agent. A program that overruns `--timeout` is killed along with its children.

**5. Peer two hubs across organizations**

Each organization runs its own hub. `--peer ORG=ws://host:port` opens a
federation link (repeatable, reconnects automatically):

```bash
intermesh hub --port 8766 --org globex
```

```bash
intermesh hub --port 8765 --org acme --peer globex=ws://localhost:8766
```

An agent on the Acme hub can then address `globex/financial_engine` directly —
messages, tasks and their results are relayed over the peering link. Without an
active peering, cross-organization addressing stays refused by tenant isolation.

Peering hubs exchange **public keys** during the handshake, never a shared
secret. Each hub signs its tokens with an Ed25519 private key that never leaves
the machine, so a peer can *verify* the origin of a relayed message but can
never *forge* one on another organization's behalf. A peering request without a
public key is refused outright.

Because that handshake carries the keys, the link itself must be
tamper-proof. Across hosts, serve TLS and peer over `wss://`:

```bash
intermesh hub --port 8766 --org globex \
  --tls-cert hub.crt --tls-key hub.key
```

```bash
intermesh hub --port 8765 --org acme \
  --peer globex=wss://hub.globex.com:8766 --peer-ca globex-ca.crt
```

`--peer-ca` points at the partner's certificate authority when it isn't in the
system trust store; certificate and hostname verification stay on either way.
**Plaintext `ws://` peering to a remote host is refused** — it would let an
in-path attacker swap the public keys during the handshake. Loopback is exempt
(local development), and `--allow-insecure-peering` overrides the check if you
control the network.

**6. Control what leaves your organization**

Peering says *who* may talk to whom; an egress policy says *what* may cross.
Declare it in JSON:

```json
{
  "name": "due_diligence",
  "rules": [
    {"name": "no_margin", "action": "drop", "field": "marge_reelle"},
    {"name": "no_iban", "action": "redact", "pattern": "FR\\d{10,}", "replacement": "[IBAN]"},
    {"name": "classified", "action": "block", "pattern": "SECRET-DEFENSE"}
  ]
}
```

Pass it to the hub with `--egress-policy egress.json`, and to an agent with
`InterMeshAgent(..., egress_policy=EgressPolicy.load("egress.json"))`.

Both enforcement points matter, and they see different things. The **agent**
filters before encryption — the only place plaintext exists when E2E is on. The
**hub** filters at relay time, so an agent that forgot its policy still cannot
leak; but it can only inspect what is not end-to-end encrypted. Internal
exchanges within an organization are never filtered. Rules are opt-in: with no
policy declared, nothing is touched.

---

## Features

| | |
|---|---|
| 🔐 **End-to-end encryption** | RSA-2048-OAEP + AES-256-GCM. The hub routes ciphertext it cannot read. |
| 🆔 **Verifiable identity** | SHA-256 fingerprints over roles, permissions, and capabilities — tampering is rejected at registration. |
| 🎫 **JWT authentication** | Every message after registration carries a token signed with the hub's Ed25519 key (EdDSA). Peers verify with the published public key — no shared signing secret across organizations. |
| 🛡️ **RBAC** | Per-agent access policies enforced at the hub. |
| 🔍 **Discovery** | Find agents by capability, role, metadata, or name. |
| 📋 **Tasks & workflows** | Async distributed task lifecycle: `pending → running → completed/failed`. |
| 🔌 **Framework adapters** | Python: `from_langchain`, `from_callable`, `@intermesh_service` — the CrewAI, AutoGen and LlamaIndex examples bridge through `from_callable`. JS: `adapt()`, `InterMeshLangChainAdapter`, `InterMeshLlamaIndexAdapter`. |
| 🌍 **Any language** | `intermesh serve --exec` turns any executable into an agent (JSON on stdin/stdout); `--http` adapts a service already online. No SDK required on the foreign side. |
| 🧵 **Orchestration helpers** | `InterMeshPipeline` chains steps across agents found by capability; `fan_out`/`fanOut` runs branches in parallel and aggregates results. |
| 🌐 **Federation** | Hub-to-hub peering across organizations, E2E preserved end to end. Peers authenticate by published Ed25519 key over TLS. |
| 🚪 **Egress filtering** | Per-organization policy on what may cross the boundary: `drop` a field, `redact` a pattern, `block` the payload. Enforced by the sending agent (before encryption) and by the hub at relay time. |
| 📜 **Immutable audit log** | Merkle-chained events; any retroactive edit breaks the chain. |
| 🚦 **Rate limiting** | Token-bucket throttling per agent. |
| 🛠️ **Developer CLI** | `intermesh hub`, `discover`, `ping`, `ask`, `task`, `keygen`, `dashboard`, `docs`. |
| 📊 **Mission Control** | `intermesh dashboard` — a local console with no external dependency. Distinct from the hosted Control Plane at intermesh.site, which is a React app needing accounts. |
| 🐳 **Docker** | Full stack via `docker compose up -d`. |

---

## Repository layout

| Path | Purpose |
|---|---|
| `sdk-python/` | Official Python SDK (`intermesh`) and the `intermesh` CLI — `from_callable`, `from_langchain`, `@intermesh_service` |
| `sdk-js/` | Official JavaScript/TypeScript SDK (`intermesh`) — adapters for LangChain.js and LlamaIndex.TS |
| `server/` | The coordination hub |
| `sdk-python/intermesh/console/` | Mission Control — the console shipped in the package |
| `docs/` | RFC-001, security spec, API reference, remote-hub guide |
| `examples/` | Runnable agents (Python and Node.js); `examples/frameworks/` wraps real LangChain/LlamaIndex/CrewAI/AutoGen objects |
| `tests/` | 137 unit + integration tests |
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
