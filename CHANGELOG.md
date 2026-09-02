# Changelog

All notable changes to InterMesh Protocol are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.4.2] — 2026-09-02

### Fixed

- **An encryption mismatch produced wrong answers instead of an error.** An
  agent configured without encryption, given work by an orchestrator that
  encrypts, received the ciphertext **as if it were the data**. The handler
  processed it, the task completed successfully, and the answer was wrong —
  `"bonjour undefined"` instead of `"bonjour Adrien"`. Nothing failed
  anywhere.

  For a protocol whose argument is end-to-end encryption, that is the worst
  possible failure: silent, and it produces bad data rather than an error.
  Both SDKs now recognise a payload they cannot open and refuse it with a
  message carrying the remedy. The task is reported failed, so the
  orchestrator learns the reason instead of waiting out its timeout, and the
  agent stays in service rather than crashing.

  The same refusal covers the neighbouring case: encryption is on, but the
  payload was encrypted for a different public key — which happens when an
  agent reconnects under the same name and the sender caches a stale key.

  Detection is structural (base64 of the three-field envelope) and needs no
  key, so the wire format is unchanged and 0.4.x agents keep interoperating.
  Ordinary strings, including valid base64, are not mistaken for ciphertext —
  a false positive would refuse perfectly good data, which is worse than the
  bug being fixed.

- **The CLI banner still drew the old name.** `intermesh hub` and
  `intermesh --help` rendered "NEXA" in ASCII art next to the words
  "INTERMESH PROTOCOL". First thing a user sees, and on every screenshot.

- **The README's first code block did not compile.** `await agent.connect()`
  at module level is a `SyntaxError` in Python, and it fails before anything
  runs — so nothing hints at the cause. The same shape was in the SDK README
  and the integration guide. JavaScript blocks were left alone: top-level
  `await` is valid in an ES module.

---

## [0.4.1] — 2026-09-02

### Added

- **The JavaScript SDK reconnects.** It had no reconnection logic of any
  kind: `hubUrl` was a single address, there was no `close()`, and an agent
  whose hub died simply stopped. It now takes one address or several, learns
  its hub's live siblings at registration, and fails over — measured at
  **0.14 s** against a real five-hub cluster. Off by default
  (`autoReconnect: true` to enable), so existing agents keep the behaviour
  they were written against.
- `onFailover(handler)`, `close()`, and in-flight calls that reject on
  disconnect instead of hanging until their own timeout — an agent that
  looks alive while disconnected is worse than one that fails.

### Fixed

- **A cluster could not cold-start.** Hubs starting together against an
  empty PostgreSQL database raced on schema creation: `CREATE TABLE IF NOT
  EXISTS` is not race-safe there, and the losers died on `duplicate key ...
  pg_type_typname_nsp_index` — a message that does not mention tables at
  all. Kubernetes and docker-compose start every hub at once, so this hit
  the first deployment and only the first, when nobody expects it. Five
  hubs now cold-start on an empty database with no casualties.
- Two test files claimed the same TCP ports, so one failed only when the
  whole suite ran. Found by not dismissing a test that passed in isolation.

---

## [0.4.0] — 2026-09-02

Everything in this release came from one question: what would stop a bank
from running this? The answers were measured rather than guessed, and
several of them were unflattering.

**The hub is no longer a single machine.** State can live in PostgreSQL, so
a hub restarted elsewhere finds its state again, and several hubs of one
organisation form a cluster: an agent on one is reachable from another, and
a task submitted on one completes on another. Measured on five hubs with a
thousand agents — 1 503 cross-hub requests/s and 413 tasks/s, no errors.
Killing a hub under load cost the survivors nothing measurable: 96 694
requests after the kill, none failed.

**Agents no longer die with their hub.** They used to. An agent knows only
the address it was given, so its hub gone, the reconnect loop replayed that
dead address forever while a sibling stood ready. Hubs now hand out their
live siblings at registration; re-attachment takes about half a second, and
the agent is reachable again afterwards — not merely connected.

### Added

- **PostgreSQL state backend** (`--state-dsn`), alongside SQLite and memory.
- **Clustering** — `--hub-id` and `--cluster-url`. Sibling hubs share a
  signing key and a database, and route between themselves.
- **Mutual TLS** — `--tls-client-ca` makes the hub demand a client
  certificate, refused during the TLS handshake rather than after.
  `--mtls-cert` / `--mtls-key` are what this hub presents to peers and
  siblings. The certificate's common name is written to the audit log.
- **Human approval on dangerous tasks** — a policy suspends a task and waits
  for a decision rather than refusing it outright.
- **`--max-agents`** — a configurable ceiling, unlimited by default.
- Load benchmarks: `scripts/benchmark.py` and `scripts/cluster_benchmark.py`.

### Changed — breaking

- **Self-declared identity is refused from remote connections.** Without an
  API key, a registering agent chose its own organisation, roles and
  permissions, and the hub accepted them whatever the origin — so anyone who
  knew the address could declare themselves admin. Local connections are
  unaffected; `--allow-self-declared` restores the old behaviour on a network
  you control, and `--require-api-key` refuses it even from localhost, which
  is the only setting that holds behind a reverse proxy.
- **Observers must authenticate.** A client declaring `roles: ["observer"]`
  received the agent inventory *and* the entire audit chain with no key at
  all, while the same client declaring itself an agent was refused: the
  identity check covered one door of two. Telemetry is now granted on the
  roles a key carries, not the roles a client claims.
- **Cluster links are encrypted.** Links between sibling hubs ran over no TLS
  at all — authentication rested on the shared signing key, which holds, but
  the traffic, tokens included, crossed in the clear.

### Fixed

- **A 15-agent cap, hardcoded and enforced before the API key was read** — so
  an enterprise key made no difference. Found by writing the benchmark.
- **A deadlock in the SDK, and silent plaintext with it.** Replying to a
  request happened inside the agent's own listen loop; encrypting the reply
  needed a key fetched through that same blocked loop. Every lookup timed out
  after 3 s, and the reply then went out **unencrypted** while the banner
  said encryption was on. Requests were encrypted; responses were not.
  3.01 s → 0.007 s, and responses are now actually encrypted.
- **The operations console could never sign in.** It declares
  `roles: ["admin", "observer"]`; the observer branch caught it first and
  issued the pseudo-token `"observer"`, which `authorize()` rejects — so its
  `hub.info` probe failed and it refused to open, including in the hardened
  stack shipped for closed networks.

### The JavaScript SDK

Ships as `0.4.0` alongside Python, so one number says which hub an SDK is
tested against. At 0.4.0 the number was the claim, not parity: the
JavaScript SDK had **no reconnection logic at all**, and an agent whose hub
died stopped there. That gap is closed in 0.4.1.

### Known limits

Named because a security review will find them: no LDAP or Active Directory,
no HSM, no SBOM or signed images, console access uses a shared API key
rather than per-person credentials, and the JavaScript SDK does not
re-attach after a hub is lost. See `docs/AIR-GAPPED.md`.

---

## [0.3.0] — 2026-08-29

**Renamed: Nexus is now InterMesh.** The `nexus` name was unavailable across
most domains and already crowded on both registries, so the project moved
before it had users to strand.

Both SDKs ship as `0.3.0`. The JavaScript SDK jumps from `0.1.1` to keep the
two languages on one number — under a brand-new package name, two different
versions would say nothing about which pairs speak to which.

**Federation now actually runs.** Two hub implementations had diverged, and
the one everything started — documentation, Dockerfile, tests — parsed
`--peer` without ever reading it. `peered_hubs` stayed empty for the life of
the process, task routing consulted only local agents, and discovery filtered
hard on the caller's organization: crossing an organizational boundary was
impossible by construction. The working implementation lived in a second file
nobody launched. It went unnoticed because the federation test contained no
`test_` function and was never collected by pytest.

Merging the two hubs exposed what federation depended on and did not have —
verifiable cross-organization identity, a tamper-proof channel to exchange
keys over, and control of what leaves an organization. Each is addressed
below. This release also makes `pip install intermesh` deliver a server,
which it previously did not.

### Changed — breaking

- Python package and import are both `intermesh` (was `nexus-mesh` /
  `nexus_sdk`); npm package is `intermesh` (was `nexus-mesh`).
- Classes are prefixed `InterMesh` (`InterMeshAgent`, `InterMeshTask`,
  `InterMeshStore`, …); the decorator is `@intermesh_service`.
- CLI command is `intermesh` (was `nexus`).
- Environment variables are `INTERMESH_*` (24 of them); the state directory
  is `~/.intermesh/`.
- **Wire protocol is `intermesh/v1`** (was `nexus/v1`). Agents built on 0.1.x
  or 0.2.x cannot talk to a 0.3.0 hub. This break is deliberate and taken now,
  while the protocol has no deployed users and the change costs nothing.
- Prometheus metrics are `intermesh_*`; the snapshot format is
  `intermesh-snapshot/1`.
- **`server/hub_telemetry.py` is removed.** It held the only working
  federation code, but no documentation, container image or test ever started
  it. Deployments that did must switch to `intermesh hub` or `server/hub.py`,
  which now carry federation and telemetry together.
- **Tokens are signed with EdDSA, not HS256.** A hub that has issued tokens
  under 0.2.x will not validate them after upgrading; agents reconnect and are
  re-issued. The signing secret itself is unchanged and still resolved the
  same way, so no configuration moves.

The old `nexus-mesh` packages remain on PyPI and npm for the published 0.1.x
and 0.2.x versions. They are not maintained.

### Added

- **Hub snapshots.** `snapshot.create`, `snapshot.restore` and `snapshot.list`
  admin commands, plus a `intermesh snapshot` CLI. A snapshot captures identities,
  tasks, API key digests, escrow holds and guardrail policies.
- **Encryption at rest for snapshots.** `encrypt_blob` / `decrypt_blob` derive
  a key with PBKDF2-HMAC (100 000 iterations, random salt) and seal it with
  AES-256-GCM. The passphrase is read with `getpass`, never from a command-line
  argument — `ps` and shell history would otherwise expose it to every user on
  the machine.
- State export/import across the SDK: `ApiKeyStore.export_hashed` /
  `import_hashed`, `InterMeshStore.replace_identities` / `replace_tasks`,
  `EscrowManager.export_state` / `import_state`,
  `AsimovGuardrailEngine.export_policies` / `import_policies`.
- Health probes (`/healthz`, `/readyz`, `/metrics`) served on the hub's
  WebSocket port, now also reporting `intermesh_peered_hubs` and
  `intermesh_observers`.
- **Working hub-to-hub federation.** `--peer ORG=wss://host:port` opens a
  link that reconnects on its own; messages, tasks and their results are
  relayed to the peer that owns the target agent. Tenant isolation remains the
  default and is lifted only towards an explicitly peered organization — with
  no peering, cross-organization addressing is still refused.
- **An agent written in any language, with no SDK.** `intermesh serve --exec`
  turns any executable into an agent: the task arrives as JSON on stdin, the
  answer is read from stdout. `--http` adapts a service already online instead
  of restarting it. Non-JSON stdout is wrapped as `{"output": "..."}` so a
  shell `echo` is a valid agent; demanding well-formed JSON would have killed
  the use case. From Python, `InterMeshAgent.from_command(...)` and
  `.from_http(...)`.
- **`agent.run()` and `serve_forever()`.** Without them the "one-line
  integration" still required writing the asyncio loop that keeps an agent
  alive.
- **The CLI gained the commands the README already documented**: `hub`,
  `ping`, `ask`, `task`, `keygen`. `hub` is dispatched before argument parsing
  and receives the hub's own options untouched, so the two cannot drift apart.
- `InterMeshAgent(ssl=...)` to reach a hub over `wss://` presenting a
  certificate from a private authority.

### Security

- API keys sourced from the environment are read-only: `import_hashed` refuses
  to overwrite them. They belong to the orchestrator (Kubernetes, CI), and
  restoring a snapshot over them would silently diverge the hub from its source
  of truth.
- `replace_identities` and `replace_tasks` run their `DELETE` and `INSERT` in a
  single transaction. A crash between the two would leave a hub with no
  persisted identities at all — worse than the state being restored.
- **Cross-organization identity is verifiable, not assumed.** Tokens are now
  signed with an Ed25519 private key that never leaves its hub, and peers
  exchange public keys when they pair. Under HS256 two federated hubs had to
  share their signing secret, so either could mint tokens in the other's name
  — unacceptable between organizations that, by definition, do not trust each
  other. A relayed message is checked against the issuing hub's published key:
  signature, expiry, and originating organization. A peering request carrying
  no public key is refused rather than trusted blindly.
- **The peering link must be tamper-proof.** `--tls-cert` / `--tls-key` serve
  `wss://`; `--peer-ca` accepts a partner's private authority without ever
  relaxing certificate or hostname verification. Plaintext peering to a remote
  host is refused: the handshake carries the public keys, so an in-path
  attacker could substitute them and leave the signature checks looking intact.
  Loopback stays exempt for local development, and
  `--allow-insecure-peering` is the explicit way out.
- **Egress filtering.** Peering governs who may talk to whom; it says nothing
  about what may leave. A per-organization policy can `drop` a field at any
  depth, `redact` a pattern, or `block` the payload outright. It is enforced in
  two places because they see different things: the sending agent filters
  before encryption — the only point where plaintext exists while E2E is on —
  and the hub filters at relay time, catching an agent that carries no policy
  but able to inspect only what is not end-to-end encrypted. Neither stops a
  malicious insider who encrypts before sending; this addresses leaks by
  negligence. Policies are opt-in, and the audit log records rule names, never
  the values they removed.
- `intermesh keygen` never prints the private key, which would land in shell
  history; with `--out` the file is created `0600` directly, leaving no window
  where it is world-readable.

### Fixed

- Documentation aligned with the real adapter API. The `examples/frameworks/`
  files imported `intermesh.adapters.crewai` and siblings — modules removed when
  the adapters package was flattened — and raised `ModuleNotFoundError` on the
  first line. See the notes below for the blocking-call caveat that came with
  the rewrite.
- **`pip install intermesh` now delivers a hub.** The server lived in
  `server/`, outside the packaged tree, so the published wheel contained a SDK
  and a CLI but no server — and `intermesh hub`, documented since 0.1.0, could
  not exist. It moved to `intermesh/hub.py`; `python3 server/hub.py` still
  works through a thin launcher.
- **The federation test is collected.** It was written as a `main()` script,
  so pytest ignored it: the only test covering the flagship feature never ran.
- **A foreign program that overruns its timeout is killed with its children.**
  Killing only the shell left descendants holding the pipes open, so the call
  blocked until they finished on their own and the timeout protected nothing.
- Agents may be addressed as `x` or `default/x`; the SDK used both while the
  hub registered only the short form.
- `intermesh ping` on an unknown agent reports it plainly instead of surfacing
  a raw `TimeoutError` — a hub answering nothing *is* the answer.

### Tests

- 171 passing with 1 failure before, 231 passing with none after. No existing
  test was modified to accommodate the new code.
- New coverage for the properties that matter and could silently regress: a
  peer cannot impersonate a third organization, certificate verification is
  genuinely enforced (with the matching positive case, so a hub that refused
  everything would not pass), egress filtering under active E2E encryption, a
  Node agent driven by a Python orchestrator, and the README quick start run
  end to end through the CLI.

---

## [0.2.0]

### Added

- **Admin console.** `dashboard/` is now a working administration console
  rather than a telemetry page that never received anything: `server/hub.py`
  emitted no telemetry at all, so the dashboard connected to the production
  hub and displayed nothing. The hub now broadcasts agent, task, routing, and
  admin events to subscribed consoles.
- **Admin command API** (`admin_request` / `admin_result`): `hub.info`,
  `agents.list`, `agent.disconnect`, `tasks.list`, `task.cancel`,
  `task.retry`, `audit.list`, `audit.verify`, `apikeys.list`,
  `apikey.create`, `apikey.revoke`.
- **API keys can be created and revoked at runtime**, persisted as SHA-256
  digests only. The plaintext value exists once, in the response, and is
  never written to disk or to the audit log.
- `InterMeshAgent.admin()` for scripting administration from Python.

### Security

- **Administration requires a key-authenticated identity.** At registration
  an agent picks its own roles (`roles = d.get("roles", ["standard"])`),
  which is fine for a message mesh and unacceptable for a console that can
  revoke keys. Admin commands therefore require both an identity proven by
  API key and the `admin` role. The proof is the `auth_method` claim inside
  the hub-signed JWT, so a client can neither forge nor alter it.
- Every mutation is audited as `ADMIN_ACTION` with its author; every refused
  attempt as `ADMIN_DENIED`.
- The web console never writes the API key to `localStorage` or
  `sessionStorage` — it lives in a variable for the lifetime of the tab.
- Key fingerprints are truncated to 12 characters in the interface.
- The console has no external dependencies, so it runs on a closed network.

### Changed

- **Mission Control redesign.** Top navigation, KPI cards with hand-drawn SVG
  sparklines, a terminal-style log stream with INFO/TASK/WARN/ERROR/ADMIN
  levels and source tags, search and pagination on every table, and a status
  bar carrying version, org, state backend, audit integrity, federation peers
  and session. Still zero external dependencies — the sparklines are computed
  and emitted as SVG rather than pulled from a charting library.
- Sparkline series are sampled client-side, since the hub reports point-in-time
  state and keeps no history; the curves therefore begin when the console opens.

---

## [0.1.1] — 2026-08-25

Hardening release. No protocol changes; the `intermesh/v1` wire format is
unchanged and 0.1.0 agents interoperate with a 0.1.1 hub.

All changes below are in the Python SDK and the hub. The JavaScript SDK
carries no code changes; it is released as `0.1.1` so that both SDKs
report the same version — a user seeing `intermesh` at 0.1.1 on PyPI and
0.1.0 on npm cannot tell whether the two are meant to work together.

### Security

- **API keys are no longer hardcoded in the hub.** Two service-account keys
  were written in plain text in `server/hub.py` and therefore published with
  the repository. Keys now load from `INTERMESH_API_KEYS`, `INTERMESH_API_KEYS_FILE`,
  or `~/.intermesh/api_keys.json`, and the hub retains only their SHA-256 digest —
  it can verify a key, never reveal one. With no configuration, service
  accounts are disabled; there is no guessable default.
  - Verification uses `secrets.compare_digest`; comparing digests with `==`
    leaks, through response time, how many leading bytes are correct.
  - A rejected key is never written to the audit log.
  - `--dev-api-keys` enables two deliberately public demo keys for tests, with
    a red warning on every startup.
- **New `intermesh apikey` command** to generate a service-account key and its
  configuration entry. The key is displayed once and cannot be recovered.
- The state database and key files are created `0600`, via
  `os.open(..., 0o600)` so they never exist world-readable, even briefly.

### Fixed

- **The JWT signing key survives restarts.** The hub called
  `secrets.token_hex(32)` at import time, so every restart invalidated every
  token already issued and ejected the entire agent fleet. The key now
  resolves from `INTERMESH_HUB_SECRET`, else a persistent `~/.intermesh/hub_secret`.
  Keys shorter than 32 characters are refused at startup. Two hubs starting
  concurrently on the same file converge on one key instead of signing
  differently and rejecting each other's agents.

### Added

- **State persistence.** Identities, tasks, and the audit log are stored in
  SQLite at `~/.intermesh/hub_state.db`. Live connections are deliberately not
  persisted — being "online" is a property of the running process.
- **The Merkle audit chain now protects its own file.** The chain is reloaded
  and verified at startup; editing an entry directly in the database is
  detected and reported. This is the tampering case the chain was designed
  for but could not previously catch, since nothing was written down.
- **Interrupted tasks resume.** A `pending` or `running` task is reassigned as
  soon as its assignee reconnects, whether it was interrupted by a hub restart
  or by the agent dropping. A `running` task returns to `pending` before being
  re-sent — the work in progress is genuinely lost, so **executors must be
  idempotent**. Each resumption is audited as `TASK_RESUMED`.
- New flags on both `server/hub.py` and `nexus hub`: `--secret-file`,
  `--ephemeral-secret`, `--state-file`, `--ephemeral-state`, `--dev-api-keys`.
- `INTERMESH_HOME` relocates the key, state database, and API key file together.
- The startup banner reports whether the signing key and state are persistent
  or ephemeral, and what was restored.
- `docker-compose` mounts a `nexus-hub-data` volume so a
  `docker compose down && up` no longer wipes the key and state.

### Documentation

- `docs/SECURITY-AND-ENCRYPTION.md` now covers key resolution, state
  persistence, task resumption, service accounts, and an explicit list of
  known limitations.

---

## [0.1.0] — 2026-08-25

First public release, on PyPI and npm as `intermesh`.

### Added

- RFC-001 core protocol (`intermesh/v1` envelope)
- End-to-end encryption: RSA-2048-OAEP + AES-256-GCM
- Verifiable agent identity with SHA-256 fingerprints
- JWT authentication and role-based access control
- Multi-criteria agent discovery
- Distributed task lifecycle
- Hub-to-hub federation across organizations
- Immutable Merkle audit log and token-bucket rate limiting
- Official Python and JavaScript/TypeScript SDKs
- `nexus` developer CLI and Mission Control dashboard
- Docker Compose stack

[0.3.0]: https://github.com/intermeshteam/intermesh/releases/tag/v0.3.0
[0.2.0]: https://github.com/intermeshteam/intermesh/releases/tag/v0.2.0
[0.1.1]: https://github.com/intermeshteam/intermesh/releases/tag/v0.1.1
[0.1.0]: https://github.com/intermeshteam/intermesh/releases/tag/v0.1.0
