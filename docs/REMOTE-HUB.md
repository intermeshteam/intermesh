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

## ⚠️ Before you expose a hub to the internet

**Read this part. It is not optional.**

Without an API key, an agent that registers **declares its own identity**. It
picks its own `org_id`, its own `roles`, and its own `permissions` — the hub
takes them at face value:

```python
org_id = d.get("org_id", my_org)
roles  = d.get("roles", ["standard"])
perms  = d.get("permissions", [])
auth_method = "self_declared"
```

On `localhost` that is a convenience. On a hub reachable from the internet, it
means **anyone who finds the address can connect and claim to be an admin of
any organization**.

A hub exposed without configured API keys is an open hub. Configure them:

```bash
# Generate a key for an organization
intermesh apikey --org your-org
```

Keys are read from `INTERMESH_API_KEYS` (JSON) or from
`~/.intermesh/api_keys.json`. Without either, service accounts stay disabled and
every registration falls back to self-declared.

**Do not use `--dev-api-keys` on a public hub.** It enables demonstration keys
whose values are in the source code of this repository.

Deciding *who* may register, beyond holding a key, is a policy the hub does not
make for you. If the hub is reachable publicly, restrict it at the network
level too — a firewall allowlist, a VPN, or a private network — rather than
relying only on key possession.

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

**What it does not give you:** two hubs serving traffic at once. Connected
agents' sockets live in the memory of whichever process holds them, so two
hubs sharing a database would not see each other's online agents, and a task
routed by one would not reach an executor connected to the other. This lifts
the storage constraint, not the routing one — it makes a standby possible, not
active-active.

---

## Not covered here

**Platform-as-a-service deployment** (Railway, Render, Fly.io) would be the
accessible route for people who do not administer servers: those platforms give
an HTTPS subdomain with a valid certificate automatically, so there is no
certbot, no firewall, and no DNS to configure.

Two things stand in the way today, and neither is a documentation problem:

1. **The hub does not read the `PORT` environment variable**, which those
   platforms assign dynamically. It only accepts `--port`.
2. **The self-declared registration above.** A one-click deploy button that
   hands someone an open hub would be worse than no button.

Both are tracked as work to do, not as steps you can follow.

**A managed hub** — where the hub is run for you and you never touch a
server — does not exist. It is the intended answer for non-developers, and it
is why the paid tier is planned. See
[the pricing page](https://intermesh.site/pricing).
