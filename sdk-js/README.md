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

## Adapters: bridge an existing framework agent

Wrap an existing LangChain.js `Runnable` or LlamaIndex.TS query/chat engine without
changing a line of it — it becomes discoverable and receives delegated tasks like a
native Nexus agent:

```javascript
import { NexusLangChainAdapter } from 'nexus-mesh/adapters/langchain';

const agent = new NexusLangChainAdapter(myRunnable, {
  name: 'analyst',
  capabilities: ['market_analysis'],
});
await agent.connect();
```

```javascript
import { NexusLlamaIndexAdapter } from 'nexus-mesh/adapters/llamaindex';

const agent = new NexusLlamaIndexAdapter(index.asQueryEngine(), {
  name: 'knowledge_base',
  capabilities: ['document_search', 'rag'],
});
await agent.connect();
```

Any other object exposing `invoke`, `run`, `call`, `query`, `chat`, `predict` — or a
plain function — works with the generic `adapt()`:

```javascript
import { adapt } from 'nexus-mesh/adapters';

const agent = adapt(myExistingAgent, { name: 'x', capabilities: ['c'] });
```

No framework is imported by these modules: the adapter detects the calling
convention at runtime instead of depending on a specific package version. CrewAI and
AutoGen have no established JS port, so only LangChain.js and LlamaIndex.TS have a
dedicated bridge here.

The Python SDK works differently: it detects the calling convention only for
LangChain (`from_langchain`). Everything else goes through `from_callable`, where
you write the adapting function yourself — see
[`docs/AGENT-INTEGRATION.md`](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/AGENT-INTEGRATION.md).

---

## Orchestration: chain and parallelize agents

`NexusPipeline` chains tasks across agents found by capability — the output of
one step feeds the next:

```javascript
import { NexusPipeline } from 'nexus-mesh';

const pipeline = new NexusPipeline(orchestrator)
  .step('Translate', { capabilities: ['translate'] })
  .step('Calculate', {
    capabilities: ['calculate'],
    inputFn: (prev) => ({ expression: prev.translated_text }),
  });

const result = await pipeline.run({ text: 'compute forty two doubled' });
```

`fanOut` runs independent branches concurrently and keys the results:

```javascript
import { fanOut } from 'nexus-mesh';

const results = await fanOut(orchestrator, [
  ['fr', { region: 'FR' }],
  ['de', { region: 'DE' }],
], { capabilities: { fr: ['market_analysis'], de: ['market_analysis'] } });
```

See [Agent integration](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/AGENT-INTEGRATION.md)
for the full picture, including the Python-side equivalents.

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

- [Agent integration — adapters and orchestration](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/AGENT-INTEGRATION.md)
- [RFC-001 — Core protocol specification](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/RFC-001-CORE-PROTOCOL.md)
- [Security and encryption model](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/SECURITY-AND-ENCRYPTION.md)
- [API reference](https://github.com/mrlomemba-cmd/nexus/blob/main/docs/API-REFERENCE.md)

## License

[Apache 2.0](https://github.com/mrlomemba-cmd/nexus/blob/main/LICENSE)
