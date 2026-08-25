# Nexus Mesh — JavaScript / TypeScript SDK

The official Node.js SDK for **Nexus Protocol**, the universal open-source coordination
protocol for AI agents.

Fully interoperable with the Python SDK: a Node.js agent and a Python agent can exchange
end-to-end encrypted messages and tasks through the same hub.

```bash
npm install nexus-mesh
```

---

## Quick start

**Start the hub** (from the Python SDK, or via Docker):

```bash
nexus hub
```

**Connect an agent:**

```javascript
import { NexusAgent } from 'nexus-mesh';

const agent = new NexusAgent({
  name: 'node_orchestrator',
  capabilities: ['orchestration'],
  roles: ['admin'],
  hubUrl: 'ws://localhost:8765',
});

await agent.connect();

// Find a Python agent by capability and delegate to it
const found = await agent.discover({ capabilities: ['calculate'] });
const result = await agent.submitTask(
  'Add two numbers',
  found.agents[0].name,
  { a: 20, b: 22 }
);
// { result: 42 }  — encrypted end-to-end across languages
```

**Handle inbound work:**

```javascript
agent.onTask(async (input, task) => {
  return { result: input.a + input.b };
});

agent.onRequest(async (content, sender) => {
  return { status: 'ONLINE' };
});
```

---

## Cryptographic interoperability

The SDK implements the same hybrid scheme as the Python SDK, using Node's native
`crypto` module:

- **RSA-2048-OAEP** (SHA-256) to wrap a per-message AES key
- **AES-256-GCM** (12-byte IV, 16-byte auth tag) for the payload

A message encrypted in JavaScript decrypts in Python, and vice versa. The hub sees
only ciphertext.

---

## API summary

| Method | Purpose |
|---|---|
| `connect()` | Open the connection and obtain a JWT |
| `submitTask(title, assignee, inputData)` | Delegate a task and await its result |
| `discover(query)` | Find agents by capability, role, or metadata |
| `whoIs(name)` | Fetch an agent's certified identity and public key |
| `onMessage / onRequest / onTask` | Register inbound handlers |

---

## Documentation

- [RFC-001 — Core protocol specification](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/RFC-001-CORE-PROTOCOL.md)
- [Security and encryption model](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/SECURITY-AND-ENCRYPTION.md)
- [API reference](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/API-REFERENCE.md)

## License

[Apache 2.0](https://github.com/mrlomemba-cmd/nexus/blob/main/LICENSE)
