# Running a hub other people can reach

By default a hub listens on `localhost` and only the machine it runs on can
talk to it. That is the right setup for developing, and it is why the Control
Plane at [intermesh.site](https://intermesh.site) defaults to
`ws://localhost:8765`.

This document covers the other case: a hub on a server, reachable by agents
running elsewhere.

---

## The one rule that decides everything

**A remote hub must serve `wss://`, not `ws://`.**

This is not a recommendation. A page served over HTTPS — which the hosted
Control Plane is — cannot open a plain `ws://` socket to another machine. The
browser refuses in the `WebSocket` constructor itself:

```
SecurityError: Failed to construct 'WebSocket': An insecure WebSocket
connection may not be initiated from a page loaded over HTTPS.
```

No packet is sent. No firewall rule, port opening, or server change can make it
work, because the connection is never attempted.

`localhost` is the single exception: browsers treat it as a trustworthy origin,
which is why local development over `ws://` works fine.

The Control Plane detects this case and reports **"Blocked by the browser"** in
amber, separately from a hub that is simply unreachable. If you see that, the
problem is the scheme, not your network.

---

## Option A — the hub terminates TLS itself

Use this on a VPS you control (Hostinger, Hetzner, DigitalOcean, a bare
machine).

Get a certificate with [certbot](https://certbot.eff.org/), then:

```bash
intermesh hub \
  --port 8765 \
  --org your-org \
  --tls-cert /etc/letsencrypt/live/hub.example.com/fullchain.pem \
  --tls-key  /etc/letsencrypt/live/hub.example.com/privkey.pem
```

`--tls-cert` and `--tls-key` must both be given; the hub refuses to start with
only one. It binds `0.0.0.0`, so no extra flag is needed to accept outside
connections — but you do need to open the port in your firewall:

```bash
sudo ufw allow 8765/tcp
```

Point a DNS `A` record at the server, and the Control Plane connects to
`wss://hub.example.com:8765`.

**Certificates expire.** Certbot renews them, but the hub reads them at
startup — it needs a restart after each renewal, or it will keep serving an
expired certificate and every browser will refuse it.

## Option B — a reverse proxy terminates TLS

Use this if the machine already runs nginx or Caddy, or if you would rather
keep certificate handling out of the hub. Run the hub in plain `ws://` bound to
localhost, and let the proxy handle TLS and forward to it.

Caddy, which obtains and renews certificates on its own:

```
hub.example.com {
    reverse_proxy localhost:8765
}
```

The hub then runs without any TLS flag. Externally it is `wss://`; internally
the proxy speaks `ws://` to it over the loopback interface, which never leaves
the machine.

---

## Identity: who gets to declare their own roles

Without an API key, a registering agent **declares its own identity** — its
`org_id`, its `roles`, its `permissions`. On `localhost` that is a development
convenience. From a remote address it means anyone who finds the address can
claim to be an admin of any organization.

The hub always binds `0.0.0.0`, so "exposed" cannot be inferred from any
setting. The decision is made **per connection**, by where it comes from:

| Connection | Without an API key | With a valid API key |
|---|---|---|
| From `localhost` | allowed | allowed |
| From anywhere else | **refused** | allowed |

A refused registration gets `SELF_DECLARED_REFUSED` naming what to do. This is
the default; nothing needs enabling.

### The two flags

```bash
# Private network or testing: accept self-declared identities remotely.
intermesh hub --allow-self-declared

# Strictest: require an API key everywhere, including from localhost.
intermesh hub --require-api-key
```

### ⚠️ Behind a reverse proxy, the origin check protects nothing

If nginx or Caddy terminates TLS in front of the hub (Option B above), the
proxy is the TCP peer — so **every connection looks local** and self-declared
identities are accepted from the whole internet.

`X-Forwarded-For` is deliberately not consulted: the client supplies that
header unless a trusted proxy rewrites it, so trusting it would turn the check
into a formality.

**In that setup, `--require-api-key` is the only setting that holds.** The hub
prints a warning at startup when no API key is configured, for this reason.

### Issuing keys

```bash
intermesh apikey --org your-org
```

Keys are read from `INTERMESH_API_KEYS` (JSON) or `~/.intermesh/api_keys.json`.

**Do not use `--dev-api-keys` on a public hub.** It enables demonstration keys
whose values are in this repository's source.

Holding a key is authentication, not authorization for everything. If the hub
is publicly reachable, restrict it at the network level as well — a firewall
allowlist, a VPN, or a private network.

---

## Where the state lives

By default the hub keeps its state in a SQLite file, created `0600`. That is
the right choice for a hub on one machine, and nothing below is needed to run
one.

A SQLite file is tied to its filesystem, though: no hub running elsewhere can
read it, and losing the disk loses the identities, the tasks and the audit
chain with it. For a deployment where that matters, point the hub at
PostgreSQL instead:

```bash
pip install 'intermesh[postgres]'

intermesh hub --org your-org \
  --state-dsn postgresql://user:password@db.internal:5432/intermesh
```

The DSN can also come from `INTERMESH_STATE_DSN`. Prefer that in a container:
a password passed as a command-line argument is visible in the process table
to every user on the machine. The hub prints the DSN with its password
replaced by `***`, so it does not end up in logs or in `hub.info`.

Schema creation is automatic and idempotent — the hub issues
`CREATE TABLE IF NOT EXISTS` at startup, so there is no migration step.

**What this gives you:** state that outlives the machine. A hub restarted
elsewhere against the same database recovers its identities, its tasks and a
verifiably intact audit chain. Backups become your usual PostgreSQL tooling
rather than a file to copy.

**On its own it is not clustering.** Connected agents' sockets live in the
memory of whichever process holds them, so state sharing alone does not let
one hub reach an agent connected to another. That is what the next section
adds.

---

## Running several hubs at once

A single hub is a single process: one machine, one point of failure, and a
throughput ceiling ([measured here](BENCHMARKS.md)). Several hubs of the same
organization can serve one mesh together.

Each hub needs three things in common with its siblings, and one of its own:

```bash
intermesh hub --port 8765 --org acme \
  --state-dsn postgresql://user:pass@db:5432/intermesh \
  --secret-file /etc/intermesh/hub_secret \
  --cluster-url ws://hub-1.internal:8765
```

- **`--state-dsn`** — the same database. Without it there is no shared
  presence table, so nothing routes; the hub warns at startup if you enable
  clustering without it.
- **`--secret-file`** — the same signing key. A token issued by one hub has
  to be accepted by the others, and that key is also what authenticates
  siblings to each other.
- **`--cluster-url`** — how *this* hub is reachable by the others. Different
  on every hub. Its presence is what enables clustering.
- `--hub-id` is optional; one is generated if you leave it out.

Put a load balancer in front and point agents at it. They connect wherever
they land.

### How a message finds its way

Each hub records, in the shared `presence` table, which agents are connected
to it. When a hub has to deliver to an agent it does not hold, it looks up the
owner and forwards the message there over a direct link between the two hubs.

The receiving hub delivers locally and **does not forward again**. One hop is
what makes loops impossible without counting them — at the price of requiring
the presence table to be right, which is exactly what the shared database
provides.

Presence entries carry a timestamp, refreshed every 15 seconds. An entry older
than 45 seconds is ignored: a hub killed outright cannot clean up after
itself, and without expiry its siblings would keep forwarding into the void.

### What this is not

**Not federation.** Federation crosses an organization boundary: it verifies
an Ed25519 signature and applies the egress policy to what leaves. Clustering
stays inside one tenant, so neither applies — a sibling presenting a token
signed with a different key is refused, and a `CLUSTER_JOIN` from another
organization is refused outright with a pointer to federation.

**Not a guarantee against every race.** If an agent moves between hubs in the
window between a presence lookup and the message arriving, the receiving hub
records `CLUSTER_RELAY_UNDELIVERED` rather than guessing. Tasks are resumed on
reconnection; a fire-and-forget message in that window is lost.

---

## Not covered here

**Platform-as-a-service deployment** (Railway, Render, Fly.io) would be the
accessible route for people who do not administer servers: those platforms give
an HTTPS subdomain with a valid certificate automatically, so there is no
certbot, no firewall, and no DNS to configure.

One thing still stands in the way, and it is not a documentation problem:

1. **The hub does not read the `PORT` environment variable**, which those
   platforms assign dynamically. It only accepts `--port`.
2. ~~The self-declared registration.~~ **Fixed** — remote registrations now
   require an API key by default, so a deployed hub is no longer open. What
   remains is generating and delivering that first key to someone who does not
   use a terminal.

The first is tracked as work to do, not a step you can follow.

**A managed hub** — where the hub is run for you and you never touch a
server — does not exist. It is the intended answer for non-developers, and it
is why the paid tier is planned. See
[the pricing page](https://intermesh.site/pricing).
