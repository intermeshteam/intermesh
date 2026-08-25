# Changelog

All notable changes to Nexus Protocol are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.1] — 2026-08-25

Hardening release. No protocol changes; the `nexus/v1` wire format is
unchanged and 0.1.0 agents interoperate with a 0.1.1 hub.

Python SDK only — the JavaScript SDK is unchanged and stays at `0.1.0`.

### Security

- **API keys are no longer hardcoded in the hub.** Two service-account keys
  were written in plain text in `server/hub.py` and therefore published with
  the repository. Keys now load from `NEXUS_API_KEYS`, `NEXUS_API_KEYS_FILE`,
  or `~/.nexus/api_keys.json`, and the hub retains only their SHA-256 digest —
  it can verify a key, never reveal one. With no configuration, service
  accounts are disabled; there is no guessable default.
  - Verification uses `secrets.compare_digest`; comparing digests with `==`
    leaks, through response time, how many leading bytes are correct.
  - A rejected key is never written to the audit log.
  - `--dev-api-keys` enables two deliberately public demo keys for tests, with
    a red warning on every startup.
- **New `nexus apikey` command** to generate a service-account key and its
  configuration entry. The key is displayed once and cannot be recovered.
- The state database and key files are created `0600`, via
  `os.open(..., 0o600)` so they never exist world-readable, even briefly.

### Fixed

- **The JWT signing key survives restarts.** The hub called
  `secrets.token_hex(32)` at import time, so every restart invalidated every
  token already issued and ejected the entire agent fleet. The key now
  resolves from `NEXUS_HUB_SECRET`, else a persistent `~/.nexus/hub_secret`.
  Keys shorter than 32 characters are refused at startup. Two hubs starting
  concurrently on the same file converge on one key instead of signing
  differently and rejecting each other's agents.

### Added

- **State persistence.** Identities, tasks, and the audit log are stored in
  SQLite at `~/.nexus/hub_state.db`. Live connections are deliberately not
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
- `NEXUS_HOME` relocates the key, state database, and API key file together.
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

First public release, on PyPI and npm as `nexus-mesh`.

### Added

- RFC-001 core protocol (`nexus/v1` envelope)
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

[0.1.1]: https://github.com/mrlomemba-cmd/nexus/releases/tag/v0.1.1
[0.1.0]: https://github.com/mrlomemba-cmd/nexus/releases/tag/v0.1.0
