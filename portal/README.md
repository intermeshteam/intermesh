# InterMesh Portal

Next.js 14 (App Router) + TypeScript + Tailwind. Control-plane interface for a
running InterMesh hub.

## Source of truth

**The `.tsx` and `.ts` files under `src/` are the only source of truth.** Edit
them directly.

Until 0.3.0 this was not the case: sixteen Python scripts (`build_dashboard.py`,
`update_agents_realtime.py`, `apply_stripe_layout.py`, `fix_hydration.py`, …)
generated and then repeatedly patched the React files through string
replacement. They were removed because they had become actively harmful:

- They were **one-shot patches, not generators.** Each applied a specific
  `str.replace` to an expected snippet. Re-running one against already-patched
  code either did nothing or corrupted it, and nothing recorded which had
  already run.
- They **hardcoded absolute paths** (`~/nexus/portal/...`), so they only ever
  worked on one machine, at one location.
- They made the source of truth ambiguous. A fix applied by hand to a `.tsx`
  file was silently reverted by anyone replaying a script.

They remain in the git history if a piece of layout ever needs to be
recovered: `git log --diff-filter=D -- 'portal/*.py'`.

## Running

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build
npx tsc --noEmit # type-check only
```

The portal expects a hub reachable over WebSocket. Start one with:

```bash
intermesh hub --dev-api-keys
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_INTERMESH_HUB_URL` | `ws://localhost:8765` | Hub the portal connects to |

Copy `.env.example` to `.env.local` and adjust. Every page reads the endpoint
from `src/lib/hub.ts`, never inline — a hardcoded URL in a page is a bug.

`NEXT_PUBLIC_` values are inlined into the client bundle at build time, so
changing the hub URL requires `npm run build`, not just a restart. That is
acceptable here because the value is an endpoint, not a secret; never put a
credential behind a `NEXT_PUBLIC_` name.

Use `wss://` whenever the hub is not on the same machine as the browser —
a page served over HTTPS cannot open a plaintext `ws://` socket anyway,
browsers block it as mixed content.

## Layout

```
src/app/
  page.tsx              landing
  auth/  pricing/  docs/  privacy/  terms/
  (app)/                authenticated area, shared layout
    dashboard/          live metrics and event stream
    agents/             connected agents, kill switch
    topology/           mesh graph
    security/           audit chain and guardrail violations
    keys/  billing/  settings/
  api/                  route handlers (license, slot verification)
src/components/         shared components
```

`dashboard`, `agents`, `topology` and `security` subscribe to the hub as
telemetry observers over WebSocket. `keys`, `billing` and `settings` are not
yet wired to live data.

## Known limitations

- `keys`, `billing` and `settings` render their interface without live data,
  although the hub already exposes the matching admin commands
  (`apikey.create`, `apikey.revoke`, `apikeys.list`).
