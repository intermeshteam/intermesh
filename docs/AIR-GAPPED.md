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
| Console | API key required to open it; refused without one |
| Mutual TLS | available (`--tls-client-ca`), off unless you supply a CA |
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

### Opening the console

The console asks for a key before it shows anything, and needs one carrying
`admin:*` — the same JSON in `INTERMESH_API_KEYS`. Give operators a key
distinct from the agents', so revoking human access does not stop the mesh.

Two things worth knowing. The key is held in memory only: it is never written
to `localStorage` or `sessionStorage`, so closing the tab ends the session and
a shared workstation keeps nothing. And the console appears in the mesh
listing under its own name, with roles `admin, observer` — an operator
watching is visible to everyone else watching, which is the intended
behaviour rather than an oversight.

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

## The console is the Control Plane

They used to be two different interfaces. The hosted Control Plane is a
React application; the packaged console was a hand-written page that did
roughly the same job, less well. Maintaining both made them drift, and a
first user reported seeing "the wrong dashboard" — a complaint that made
sense, because there were two.

`intermesh dashboard` now serves a static export of the same React
application, shipped inside the package:

```bash
intermesh dashboard          # http://localhost:8080
```

What the local build changes, and nothing else:

- **No account.** The hosted version signs you in through Supabase. The
  local one connects straight to the hub you point it at, so the account
  pages are not part of this export.
- **System font.** The hosted build downloads Inter from Google at build
  time and self-hosts it afterwards. That still needs a network *while
  building*, which a closed site does not have. The console build uses the
  system stack, so it compiles with no network at all — verified by
  building it offline.
- **No API routes.** Quotes, invitations and licences belong to the hosted
  site.

Rebuild it after changing the portal:

```bash
./scripts/build_console.sh
```

The export is 2.9 MB and ships in the wheel. That is about **9% on top of
an installation that already weighs 33 MB**, most of it `cryptography` —
which is why it is not a separate optional package. The first estimate for
this decision compared the *archive* size, not the installed size, and was
misleading by roughly twenty-fold.

---

## Mutual TLS

The hub could already serve `wss://`, so traffic was encrypted and the agent
checked the hub's certificate. The reverse did not exist: anyone who reached
the port could complete the TLS handshake and then try their luck at
registration.

```bash
python3 server/hub.py \
    --tls-cert hub.crt --tls-key hub.key \
    --tls-client-ca corporate-ca.crt \
    --require-api-key
```

With `--tls-client-ca`, a client without a certificate signed by that
authority is refused **during the TLS handshake** — before the first byte of
protocol, so before any registration, any API key, and any application log.

**It does not replace API keys, and the hub does not let you drop them.** The
certificate attests to the machine; the key says which agent it is and what
roles it holds. A certificate holder with no API key still gets
`SELF_DECLARED_REFUSED` under `--require-api-key`, and there is a test for
exactly that — because "we have mTLS, so we can relax the keys" is the
tempting misreading.

The common name on the client certificate is written to the audit log as
`client_cert_cn` on the registration entry. Otherwise mTLS would refuse
strangers without ever recording who it let through. The name is recorded,
never the certificate — the audit log carries no cryptographic material.

### Losing a hub

Agents carried by a hub that dies re-attach to a sibling on their own. The
hub hands out the addresses of its live siblings when an agent registers, so
nothing has to be enumerated by hand in each agent — a list written once
would not survive adding a hub, which amounts to not having it.

A hub killed outright has no chance to withdraw itself, so the list is read
with a freshness bound: handing out a dead hub's address would send the agent
exactly where it just failed.

### Hub to hub

`--mtls-cert` and `--mtls-key` are the certificate this hub *presents* when
it dials a peer or a cluster sibling that demands one. Setting them is what
lets a hub join a mesh where mutual authentication is mandatory.

Worth knowing: cluster links between sibling hubs previously ran without TLS
at all. They relied on the shared signing key for authentication, which
holds, but the traffic — tokens included — crossed in the clear. They now go
through the same TLS path as peer links, so a `wss://` cluster URL is
encrypted and presents a client certificate when one is configured.

### Generating the certificates

Use your own PKI. If you need to see the shape first, `tests/test_mtls.py`
builds a throwaway CA, a server certificate and a client certificate with the
extensions OpenSSL 3 actually requires — `SubjectKeyIdentifier`,
`AuthorityKeyIdentifier`, `KeyUsage`, and a SAN on the server certificate.
Leaving any of them out fails verification with a message that does not
obviously point at the cause.

---

## What is still missing for a regulated deployment

Named rather than glossed over, because a security review will find them:

- **No LDAP or Active Directory.** Both agents and the console authenticate
  with API keys, which is the right mechanism for programs but a poor one for
  people: a key is shared, not attributable, and revoking it locks out
  everyone holding it. For per-person access tied to your directory, put the
  console behind whatever your organisation already runs.
- **mTLS is available but not switched on by the stack above.** It needs a
  certificate authority you operate, so the compose file cannot supply one.
  See "Mutual TLS" below.
- **No HSM integration.** The signing key is a secret in the environment.
- **No SBOM, no signed images, no reproducible build attestation.** Digest
  pinning is a floor, not a substitute.
- **The console key lives in the operator's head, not on the machine.** It is
  asked for at each session and never written to `localStorage` — closing the
  tab ends the session. That is deliberate, but it means no "stay signed in".

Each is a real gap. None of them is hidden by the stack above.
