# Changelog

All notable changes to InterMesh Protocol are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.3.0]

**Renamed: Nexus is now InterMesh.** The `nexus` name was unavailable across
most domains and already crowded on both registries, so the project moved
before it had users to strand.

Both SDKs ship as `0.3.0`. The JavaScript SDK jumps from `0.1.1` to keep the
two languages on one number — under a brand-new package name, two different
versions would say nothing about which pairs speak to which.

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
  WebSocket port.

### Security

- API keys sourced from the environment are read-only: `import_hashed` refuses
  to overwrite them. They belong to the orchestrator (Kubernetes, CI), and
  restoring a snapshot over them would silently diverge the hub from its source
  of truth.
- `replace_identities` and `replace_tasks` run their `DELETE` and `INSERT` in a
  single transaction. A crash between the two would leave a hub with no
  persisted identities at all — worse than the state being restored.

### Fixed

- Documentation aligned with the real adapter API. The `examples/frameworks/`
  files imported `intermesh.adapters.crewai` and siblings — modules removed when
  the adapters package was flattened — and raised `ModuleNotFoundError` on the
  first line. See the notes below for the blocking-call caveat that came with
  the rewrite.

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

[0.1.1]: https://github.com/intermeshteam/intermesh/releases/tag/v0.1.1
[0.1.0]: https://github.com/intermeshteam/intermesh/releases/tag/v0.1.0
