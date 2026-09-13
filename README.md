<div align="center">

# INTERMESH

### Autonomous Action Assurance

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Spec](https://img.shields.io/badge/Action%20Evidence-v0.1%20draft-00D4FF.svg)](specs/action-evidence-v0.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()
[![Any language](https://img.shields.io/badge/Client-any%20language-brightgreen.svg)]()

**Every critical autonomous action should be authorized, controlled and provable.**

*Toute action autonome critique doit être autorisée, contrôlée et prouvable.*

[Action Evidence spec](specs/action-evidence-v0.md) · [Assurance guide](docs/ASSURANCE.md) · [Demo](examples/assurance/) · [Contributing](CONTRIBUTING.md)

</div>

---

## The problem

An AI agent no longer just answers. It calls APIs, moves money, deploys
code, deletes resources. When one of those actions goes wrong, the
question is not *what did the model say* — it is:

> **Prove that this action was authorized, controlled, and actually executed.**

Logs cannot answer that. A log is what a system remembers. **Evidence is
what someone who does not trust that system can verify themselves.**

## How it works

InterMesh sits on the network path, not in your code:

```bash
intermesh proxy --config policy.yaml --evidence evidence.jsonl
export HTTP_PROXY=http://localhost:8443
```

```text
  Agent  ──►  InterMesh  ──►  risk (R0–R5)  ──►  policy  ──►  allow / block / approval
                  │
                  └──►  signed Action Evidence  ──►  intermesh verify
```

**Zero lines of code, in any language.** Your agent is a normal program
making normal HTTP calls — Python, Node, Go, Rust, a shell script. It
needs no SDK and no modification. That is deliberate: a proxy records
what *actually left the system*, while an SDK records only what the agent
*claims* it did. For evidence meant for a third party, the difference is
the whole point.

## Try it

```bash
python3 examples/assurance/demo.py
```

```text
1. ACTION DANGEREUSE — POST /delete/database
   HTTP 403   risque R5   → BLOCKED        evidence: 2fdbfae5…

2. ACTION À VALIDER  — POST /transfer
   HTTP 403   risque R4   → APPROVAL_REQUIRED

3. ACTION AUTORISÉE  — POST /items
   HTTP 200   risque R2   → executed, evidence written

4. VÉRIFICATION      Evidence VALID · Integrity VALID · Signature VALID

5. FALSIFICATION     un champ modifié  →  INVALID, détecté
```

## Verify without trusting us

```bash
intermesh verify evidence.jsonl
```

This runs offline. No account, no server, no network call. A proof you
would have to ask us to validate would not be a proof.

## What this does not claim

Stated as plainly as the rest, because a security tool that oversells is
worse than none:

- **Absence of evidence is not evidence of absence.** An agent that
  bypasses the proxy leaves no record at all.
- **The key is not authenticated by the proof.** Valid means *intact and
  signed by the key it carries*. Binding that key to a real organization
  happens out of band.
- **Under TLS, the proof covers the host, not the path.** `CONNECT`
  hides everything else. See [the spec](specs/action-evidence-v0.md#6-limite-du-tls).

---

---

## The coordination protocol

InterMesh began as an open protocol for AI agents to discover each other
and delegate work — hub, federation, end-to-end encryption, 326 tests.
That layer still works and is documented below, but **it is no longer the
product**. It is a technical foundation the assurance layer draws on:
identity, signing, the Merkle-chained journal.

The last release before the pivot is tagged `v0.4.5-mesh`.

<details>
<summary><b>Coordination protocol — architecture and usage</b></summary>

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

</details>

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Protocol changes must be proposed as an amendment
to [RFC-001](docs/RFC-001-CORE-PROTOCOL.md) before implementation, and must land in **both**
the Python and JavaScript SDKs to preserve interoperability.

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Please do not open public issues for security problems.

## License

[Apache 2.0](LICENSE)
