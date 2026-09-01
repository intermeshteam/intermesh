# Running InterMesh in a closed data centre

Written for the case where the machine has no route to the internet and
somebody has to answer for what runs on it — a bank, a hospital, a defence
contractor.

`docker-compose.yml` is the development stack: SQLite, open ports, demo
agents. `docker-compose.hardened.yml` assumes the opposite.

```bash
cp docker/hardened.env.example docker/hardened.env
chmod 600 docker/hardened.env          # then fill in the three secrets

docker compose --env-file docker/hardened.env \
               -f docker-compose.hardened.yml up -d
```

`--env-file` is not optional. `env_file:` puts variables *inside* the
containers, but the `${...}` interpolation in the compose file is resolved by
the CLI against its own environment. Without the flag the stack stops and asks
for variables it appears to already have.

---

## What the software does not do

Verified by reading the source, not by assertion:

- **No licence check, no telemetry, no analytics, no crash reporting.** There
  is no code that calls out. A hub cut off from the internet behaves exactly
  like a connected one.
- **One outbound call exists** — `bridge.py` POSTs to the HTTP endpoint *you*
  name with `--http`. It goes where you point it and nowhere else.
- **Three Python dependencies**: `websockets`, `PyJWT`, `cryptography`, plus
  `psycopg` when PostgreSQL is used. All installable from an internal mirror.

## What the hardened stack does

| | |
|---|---|
| State | PostgreSQL, not a file attached to the container |
| Registration | API key required everywhere, including from localhost |
| Database network | `internal` — no route out, no published port |
| Filesystems | read-only, with tmpfs for the few writable paths |
| Privileges | non-root (uid 10001), all capabilities dropped, `no-new-privileges` |
| Images | pinned by digest, not by tag |
| Published ports | loopback only |

`--require-api-key` rather than the default origin check is deliberate: behind
a reverse proxy every connection looks local, so the origin check protects
nothing. See
[the remote-hub guide](REMOTE-HUB.md#️-behind-a-reverse-proxy-the-origin-check-protects-nothing).

### Verified, not asserted

Run against the live stack:

```
$ docker exec intermesh-hub id
uid=10001(intermesh) gid=10001(intermesh)

$ docker exec intermesh-hub touch /app/test
touch: cannot touch '/app/test': Read-only file system

$ docker exec intermesh-postgres getent hosts pypi.org
(no answer — DNS does not resolve)

$ docker exec intermesh-postgres nc -z 1.1.1.1 443
(no route to the outside)

$ nc -z 127.0.0.1 5432
(the database port is not published)
```

An agent registering without a key is refused with `SELF_DECLARED_REFUSED`;
the same agent presenting a key from `hardened.env` connects and reports
`state_ephemeral: false`.

---

## Building without a package index

The image build runs `pip install`, which needs an index. On a machine with no
internet, point pip at your internal mirror:

```bash
# In docker/Dockerfile.hub.hardened, alongside the pip install:
#   --index-url https://pypi.internal.bank/simple --trusted-host pypi.internal.bank
```

Or build the image on a connected machine and move it across:

```bash
docker save intermesh/hub:hardened | gzip > intermesh-hub.tar.gz
# transfer, then on the closed machine:
gunzip -c intermesh-hub.tar.gz | docker load
```

The base images are pinned by digest, so the image built outside is the image
that runs inside — that is the point of pinning rather than tagging.

---

## The Control Plane is not the console

The Control Plane at intermesh.site **cannot be used here.** It requires
Supabase, an external service, and pulls a font from Google at build time.

The stack ships `dashboard/` instead — served by the `console` container. It
loads no CDN, no remote font and no external library; its charts are SVG
computed in place. That is the interface for a closed network.

Being blunt about it: the console is plainer than the hosted Control Plane.
Making the Control Plane run offline is a separate piece of work — it would
mean replacing Supabase authentication with something local.

---

## What is still missing for a regulated deployment

Named rather than glossed over, because a security review will find them:

- **No LDAP or Active Directory.** Agents authenticate with API keys, which is
  the right mechanism for programs. Human access to the console has no
  authentication at all — put it behind whatever your organisation already
  uses.
- **No mTLS between agents and hub.** The hub can serve `wss://`
  (`--tls-cert` / `--tls-key`), but it does not verify client certificates.
- **No HSM integration.** The signing key is a secret in the environment.
- **No SBOM, no signed images, no reproducible build attestation.** Digest
  pinning is a floor, not a substitute.
- **Console ships no authentication.** It talks to the hub as an observer.
  Anyone who reaches port 8080 sees the mesh.

Each is a real gap. None of them is hidden by the stack above.
