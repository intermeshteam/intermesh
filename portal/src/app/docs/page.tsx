'use client';

import BrandName from '@/components/BrandName';
import React from 'react';
import Link from 'next/link';
import { ArrowLeft, BookOpen, Github, Terminal } from 'lucide-react';
import InterMeshLogo from '@/components/InterMeshLogo';
import ThemeToggle from '@/components/ThemeToggle';

/**
 * Documentation page.
 *
 * This page used to be forty-seven lines: a JSON envelope and one paragraph
 * on encryption. That is a fragment of a specification, not something a
 * newcomer can start from — and it was hardcoded to the dark palette with no
 * `dark:` variants, so a visitor who had chosen the light theme anywhere else
 * arrived to a white `h1` on a white background. The title was invisible.
 * That is the same defect LegalShell fixed for /terms and /privacy.
 *
 * What replaces it is a progression: what the thing is, how to run it in
 * three minutes, the four concepts everything else rests on, and only then
 * the security model and the production concerns. The deep reference stays
 * in the repository, which is the only copy that cannot drift from the code.
 */

const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const ALT_SURFACE = 'bg-slate-50 dark:bg-white/[0.015]';
const HEADING = 'text-slate-900 dark:text-white';
const BODY = 'text-slate-600 dark:text-slate-400';
const MUTED = 'text-slate-500 dark:text-slate-500';
const ACCENT = 'text-cyan-600 dark:text-cyan-400';

const SECTIONS = [
  { id: 'what', label: 'What it is' },
  { id: 'quickstart', label: 'Quick start' },
  { id: 'concepts', label: 'Core concepts' },
  { id: 'any-language', label: 'Any language' },
  { id: 'frameworks', label: 'Existing agents' },
  { id: 'security', label: 'Security model' },
  { id: 'production', label: 'Going to production' },
  { id: 'reference', label: 'Full reference' },
];

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className={`overflow-x-auto rounded-lg border p-4 font-mono text-[12.5px] leading-relaxed ${HAIRLINE} bg-slate-50 text-slate-800 dark:bg-[#0C0D12] dark:text-slate-200`}>
      {children}
    </pre>
  );
}

function Inline({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[12.5px] text-cyan-700 dark:bg-white/[0.06] dark:text-cyan-300">
      {children}
    </code>
  );
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className={`scroll-mt-24 space-y-4 border-t pt-10 ${HAIRLINE}`}>
      <div>
        <div className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${ACCENT}`}>{eyebrow}</div>
        <h2 className={`mt-1 text-2xl font-bold tracking-[-0.01em] ${HEADING}`}>{title}</h2>
      </div>
      {children}
    </section>
  );
}

export default function DocsPage() {
  return (
    <div
      className="min-h-screen bg-white font-sans text-slate-900 dark:bg-[#08080A] dark:text-slate-50"
      suppressHydrationWarning
    >
      <header className={`sticky top-0 z-50 border-b bg-white/80 backdrop-blur-xl dark:bg-[#08080A]/80 ${HAIRLINE}`}>
        <div className="mx-auto flex max-w-[1040px] items-center justify-between px-6 py-4">
          <Link
            href="/"
            className={`flex items-center gap-2.5 text-base font-bold tracking-[0.18em] transition hover:opacity-80 notranslate ${HEADING}`}
            translate="no"
          >
            <InterMeshLogo className="h-4 w-4 shrink-0" />
            <BrandName />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <div className="mx-auto max-w-[1040px] px-6 py-12">
        <Link
          href="/"
          className={`inline-flex items-center gap-2 text-xs transition hover:text-slate-900 dark:hover:text-white ${MUTED}`}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to home</span>
        </Link>

        <div className="mt-8 space-y-4">
          <h1 className={`text-[2.4rem] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[3rem] ${HEADING}`}>
            Documentation
          </h1>
          <p className={`max-w-2xl text-lg leading-relaxed ${BODY}`}>
            Everything you need to run a hub, connect an agent, and put the two
            into production. Start at the top if the project is new to you —
            each section assumes only the ones before it.
          </p>
        </div>

        <div className="mt-12 flex gap-12">
          {/* -------------------------------------------------- navigation */}
          <nav className="hidden w-44 shrink-0 lg:block">
            <div className="sticky top-24 space-y-1">
              <div className={`mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] ${MUTED}`}>
                On this page
              </div>
              {SECTIONS.map((section) => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className={`block rounded-md px-2 py-1.5 text-[13px] transition hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-white/[0.05] dark:hover:text-white ${BODY}`}
                >
                  {section.label}
                </a>
              ))}
            </div>
          </nav>

          {/* ----------------------------------------------------- content */}
          <div className="min-w-0 flex-1 space-y-12">

            {/* ============================================= what it is */}
            <section id="what" className="scroll-mt-24 space-y-4">
              <div>
                <div className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${ACCENT}`}>Start here</div>
                <h2 className={`mt-1 text-2xl font-bold tracking-[-0.01em] ${HEADING}`}>What InterMesh is</h2>
              </div>

              <p className={`leading-relaxed ${BODY}`}>
                InterMesh is an open protocol that lets AI agents find each other,
                talk securely, and delegate work — whatever language, framework or
                vendor produced them. The important word is <strong className={HEADING}>protocol</strong>,
                not product: it replaces the bespoke integration you would otherwise
                write for every new pair of agents.
              </p>

              <p className={`leading-relaxed ${BODY}`}>
                A central server, the <strong className={HEADING}>hub</strong>, routes messages between
                agents. When end-to-end encryption is on — it is by default — the
                hub routes ciphertext it cannot read.
              </p>

              <div className={`rounded-xl border p-5 ${HAIRLINE} ${ALT_SURFACE}`}>
                <div className={`mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] ${MUTED}`}>
                  What it is not
                </div>
                <p className={`text-sm leading-relaxed ${BODY}`}>
                  Not a replacement for LangChain, CrewAI or AutoGen. It is the layer
                  that lets agents built with those — or with nothing at all — discover
                  one another and collaborate, including across organizations that
                  share no infrastructure.
                </p>
              </div>
            </section>

            {/* ============================================= quick start */}
            <Section id="quickstart" eyebrow="Three minutes" title="Quick start">
              <p className={`leading-relaxed ${BODY}`}>
                Install, start a hub, write an agent, delegate work to it. Nothing
                below needs an account or a network connection beyond the install.
              </p>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>1. Install</h3>
              <Code>{`pip install intermesh      # Python SDK + the intermesh CLI
npm install intermesh      # JavaScript / TypeScript SDK`}</Code>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>2. Start the hub</h3>
              <Code>{`intermesh hub`}</Code>
              <p className={`text-sm leading-relaxed ${BODY}`}>
                Listens on <Inline>ws://localhost:8765</Inline>, keeps its state in{' '}
                <Inline>~/.intermesh/</Inline>, and prints the configuration it
                actually resolved — the first thing to read when something behaves
                unexpectedly.
              </p>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>3. Write a worker agent</h3>
              <Code>{`from intermesh import InterMeshAgent

agent = InterMeshAgent(name="calc_bot", capabilities=["calculate"], roles=["worker"])

@agent.on_task
async def run(input_data, task):
    return {"result": input_data["a"] + input_data["b"]}

agent.run()          # connects, then stays in service`}</Code>

              <div className={`rounded-xl border-l-2 border-amber-500 bg-amber-50 p-4 dark:bg-amber-500/[0.07]`}>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-400">
                  Common Python pitfall
                </div>
                <p className={`text-sm leading-relaxed ${BODY}`}>
                  <Inline>await agent.connect()</Inline> is not valid at module level
                  in Python — it is a <em>SyntaxError</em>, so it fails before anything
                  runs and nothing hints at the cause. Use <Inline>agent.run()</Inline>{' '}
                  for a service agent, or wrap the code in{' '}
                  <Inline>async def main()</Inline> called by{' '}
                  <Inline>asyncio.run(main())</Inline>. In JavaScript, top-level{' '}
                  <Inline>await</Inline> <em>is</em> valid in an ES module.
                </p>
              </div>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>4. Delegate work</h3>
              <Code>{`intermesh task calc_bot "Add two numbers" '{"a": 20, "b": 22}'

{
  "result": 42
}`}</Code>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>5. Watch it happen</h3>
              <Code>{`intermesh dashboard          # http://localhost:8080`}</Code>
              <p className={`text-sm leading-relaxed ${BODY}`}>
                A console shipped inside the package — no CDN, no external service,
                no account. It works on a closed network, pointed at whichever hub
                you give it.
              </p>
            </Section>

            {/* ============================================= concepts */}
            <Section id="concepts" eyebrow="Foundations" title="Four concepts">
              <p className={`leading-relaxed ${BODY}`}>
                Everything else in the protocol rests on these four. They are worth
                reading once, slowly.
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  {
                    t: 'Hub',
                    d: 'The meeting point. Holds the registry of connected agents, routes messages, enforces authentication, rate limits and the audit log. Cannot read encrypted content.',
                  },
                  {
                    t: 'Agent',
                    d: 'Any program that connects and registers with a name and capabilities. A Python script, a Go binary, an HTTP service already online — the SDK is optional.',
                  },
                  {
                    t: 'Capability',
                    d: 'A free-form label describing what an agent can do. Lets others find it by what it does rather than by name, which is what makes a mesh composable.',
                  },
                  {
                    t: 'Task',
                    d: 'A unit of delegated work with a lifecycle: pending → running → completed or failed. Resumed automatically if the hub or the executor restarts.',
                  },
                ].map((c) => (
                  <div key={c.t} className={`rounded-xl border p-5 ${HAIRLINE}`}>
                    <div className={`text-sm font-semibold ${HEADING}`}>{c.t}</div>
                    <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>{c.d}</p>
                  </div>
                ))}
              </div>

              <div className={`rounded-xl border-l-2 border-amber-500 bg-amber-50 p-4 dark:bg-amber-500/[0.07]`}>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-400">
                  Worth knowing early
                </div>
                <p className={`text-sm leading-relaxed ${BODY}`}>
                  A task interrupted mid-flight goes back to <Inline>pending</Inline>{' '}
                  before being reissued — the work already done is lost, not resumed
                  where it stopped. <strong className={HEADING}>Executors must be idempotent</strong>:
                  running one twice has to be safe.
                </p>
              </div>
            </Section>

            {/* ============================================= any language */}
            <Section id="any-language" eyebrow="No SDK required" title="An agent in any language">
              <p className={`leading-relaxed ${BODY}`}>
                Your program reads JSON on standard input and writes JSON on standard
                output. That is the entire contract.
              </p>

              <Code>{`intermesh serve --name pricing --exec "./pricing-engine" --capability pricing`}</Code>

              <p className={`text-sm leading-relaxed ${BODY}`}>
                Works for a Go or Rust binary, a Node or Ruby script, even a shell
                one-liner. Output that is not valid JSON is wrapped as{' '}
                <Inline>{`{"output": "..."}`}</Inline>, so an <Inline>echo</Inline> is a
                valid agent — useful for a first test.
              </p>

              <p className={`leading-relaxed ${BODY}`}>Already have an HTTP service? Point at it instead — nothing to restart.</p>
              <Code>{`intermesh serve --name scoring --http http://localhost:9000/task`}</Code>
            </Section>

            {/* ============================================= frameworks */}
            <Section id="frameworks" eyebrow="Bring what you have" title="Agents you already wrote">
              <p className={`leading-relaxed ${BODY}`}>
                A LangChain, CrewAI, AutoGen or LlamaIndex agent joins the mesh
                without changing a line of its own code. No adapter imports the
                framework it bridges, so installing the SDK never drags LangChain
                and its transitive dependencies in with it.
              </p>

              <Code>{`from intermesh import from_langchain

agent = from_langchain(my_chain, name="analyst", capabilities=["market_analysis"])
agent.run()`}</Code>

              <p className={`text-sm leading-relaxed ${BODY}`}>
                Anything else goes through <Inline>from_callable</Inline>, where you
                write the small adapting function yourself — a CrewAI crew, an AutoGen
                agent, or a plain function.
              </p>

              <div className={`rounded-xl border-l-2 border-rose-500 bg-rose-50 p-4 dark:bg-rose-500/[0.07]`}>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-rose-700 dark:text-rose-400">
                  Blocking calls freeze the agent
                </div>
                <p className={`text-sm leading-relaxed ${BODY}`}>
                  <Inline>from_callable</Inline> runs your function as given. A
                  synchronous one executes <em>inside</em> the event loop and freezes
                  the agent for its whole duration — no tasks received, no messages
                  routed. An LLM call blocks for seconds: wrap it in{' '}
                  <Inline>asyncio.to_thread(...)</Inline>.
                </p>
              </div>
            </Section>

            {/* ============================================= security */}
            <Section id="security" eyebrow="What protects what" title="Security model">
              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  {
                    t: 'End-to-end encryption',
                    d: 'RSA-2048-OAEP for key exchange, AES-256-GCM for the payload. The hub routes ciphertext it holds no key for.',
                  },
                  {
                    t: 'Verifiable identity',
                    d: 'A SHA-256 fingerprint over roles, permissions and capabilities. Tampering with them locally is rejected at registration.',
                  },
                  {
                    t: 'JWT authentication',
                    d: "Every message after registration carries a token signed with the hub's Ed25519 key. Peers verify with the published public key — no shared secret.",
                  },
                  {
                    t: 'Merkle audit log',
                    d: 'Chained events. Any retroactive edit breaks the chain, and the hub says so at startup rather than pretending the log is intact.',
                  },
                ].map((c) => (
                  <div key={c.t} className={`rounded-xl border p-5 ${HAIRLINE}`}>
                    <div className={`text-sm font-semibold ${HEADING}`}>{c.t}</div>
                    <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>{c.d}</p>
                  </div>
                ))}
              </div>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>What encryption does not cover</h3>
              <p className={`leading-relaxed ${BODY}`}>
                End-to-end encryption protects the <strong className={HEADING}>content</strong>, not the{' '}
                <strong className={HEADING}>metadata</strong>. The hub still knows who talked to whom
                and when. Put it behind TLS if that matters — see below.
              </p>

              <h3 className={`pt-2 text-base font-semibold ${HEADING}`}>Who may declare their own roles</h3>
              <p className={`leading-relaxed ${BODY}`}>
                Without an API key, a registering agent chooses its own organization,
                roles and permissions. That is a local development convenience; from a
                remote address it would let anyone claim to be an admin. The hub
                decides <strong className={HEADING}>per connection</strong>:
              </p>

              <div className={`overflow-x-auto rounded-xl border ${HAIRLINE}`}>
                <table className="w-full text-sm">
                  <thead>
                    <tr className={`${ALT_SURFACE} ${HEADING}`}>
                      <th className="px-4 py-2.5 text-left font-semibold">Connection</th>
                      <th className="px-4 py-2.5 text-left font-semibold">No API key</th>
                      <th className="px-4 py-2.5 text-left font-semibold">Valid API key</th>
                    </tr>
                  </thead>
                  <tbody className={BODY}>
                    <tr className={`border-t ${HAIRLINE}`}>
                      <td className="px-4 py-2.5">From localhost</td>
                      <td className="px-4 py-2.5">Allowed</td>
                      <td className="px-4 py-2.5">Allowed</td>
                    </tr>
                    <tr className={`border-t ${HAIRLINE}`}>
                      <td className="px-4 py-2.5">From anywhere else</td>
                      <td className={`px-4 py-2.5 font-semibold ${HEADING}`}>Refused</td>
                      <td className="px-4 py-2.5">Allowed</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className={`text-sm leading-relaxed ${MUTED}`}>
                This is the default — nothing to enable. <Inline>--require-api-key</Inline>{' '}
                demands a key everywhere, including from localhost.
              </p>
            </Section>

            {/* ============================================= production */}
            <Section id="production" eyebrow="Beyond localhost" title="Going to production">

              <h3 className={`text-base font-semibold ${HEADING}`}>A hub others can reach</h3>
              <div className={`rounded-xl border-l-2 border-rose-500 bg-rose-50 p-4 dark:bg-rose-500/[0.07]`}>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-rose-700 dark:text-rose-400">
                  One rule decides everything
                </div>
                <p className={`text-sm leading-relaxed ${BODY}`}>
                  A remote hub must serve <Inline>wss://</Inline>, never{' '}
                  <Inline>ws://</Inline>. A page served over HTTPS cannot open a plain
                  WebSocket to another machine — the browser refuses in the constructor
                  itself, before a single packet is sent. No firewall rule or server
                  change can work around it. <Inline>localhost</Inline> is the one
                  exception.
                </p>
              </div>

              <Code>{`intermesh hub --port 8765 --org your-org \\
  --tls-cert /etc/letsencrypt/live/hub.example.com/fullchain.pem \\
  --tls-key  /etc/letsencrypt/live/hub.example.com/privkey.pem`}</Code>

              <p className={`text-sm leading-relaxed ${BODY}`}>
                Behind a reverse proxy instead? Then every connection looks local to
                the hub, and the origin check protects nothing —{' '}
                <Inline>--require-api-key</Inline> is the only setting that holds.
              </p>

              <h3 className={`pt-4 text-base font-semibold ${HEADING}`}>Federation across organizations</h3>
              <p className={`leading-relaxed ${BODY}`}>
                Each organization runs its own hub; a peering link lets their agents
                address each other. Hubs exchange <strong className={HEADING}>public keys</strong> at
                the handshake, never a shared secret — a peer can verify the origin of
                a relayed message but can never forge one on another organization's
                behalf.
              </p>
              <Code>{`intermesh hub --port 8765 --org acme --peer globex=wss://hub.globex.com:8766`}</Code>

              <h3 className={`pt-4 text-base font-semibold ${HEADING}`}>Capacity, measured</h3>
              <div className={`overflow-x-auto rounded-xl border ${HAIRLINE}`}>
                <table className="w-full text-sm">
                  <tbody className={BODY}>
                    <tr className={`border-b ${HAIRLINE}`}>
                      <td className="px-4 py-2.5">Sustained tasks, one hub</td>
                      <td className={`px-4 py-2.5 text-right font-semibold ${HEADING}`}>≈ 11 /s</td>
                    </tr>
                    <tr className={`border-b ${HAIRLINE}`}>
                      <td className="px-4 py-2.5">Healthy zone, encrypted</td>
                      <td className={`px-4 py-2.5 text-right font-semibold ${HEADING}`}>≤ 8 /s</td>
                    </tr>
                    <tr className={`border-b ${HAIRLINE}`}>
                      <td className="px-4 py-2.5">Requests (<Inline>ask</Inline>), far cheaper</td>
                      <td className={`px-4 py-2.5 text-right font-semibold ${HEADING}`}>≈ 1 500 /s</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2.5">Cross-hub requests, 1 000 agents on 5 hubs</td>
                      <td className={`px-4 py-2.5 text-right font-semibold ${HEADING}`}>1 503 /s</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className={`text-sm leading-relaxed ${BODY}`}>
                The useful part: <strong className={HEADING}>the hub is the bound, not the number of
                agents</strong> — 78 agents and 234 agents hit the same ceiling. Adding agents
                does not add task throughput; adding hubs does. Past its budget the hub{' '}
                <strong className={HEADING}>refuses</strong> a task rather than queueing it silently,
                and says how long to wait before retrying.
              </p>

              <h3 className={`pt-4 text-base font-semibold ${HEADING}`}>Closed networks</h3>
              <p className={`leading-relaxed ${BODY}`}>
                No licence check, no telemetry, no analytics, no crash reporting —
                there is no code that calls out. A hub cut off from the internet
                behaves exactly like a connected one. Three Python dependencies, all
                installable from an internal mirror.
              </p>
            </Section>

            {/* ============================================= reference */}
            <Section id="reference" eyebrow="Go deeper" title="Full reference">
              <p className={`leading-relaxed ${BODY}`}>
                This page is the introduction. The complete documentation lives in the
                repository, which is the only copy that cannot drift from the code.
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                <a
                  href="https://github.com/intermeshteam/intermesh/blob/main/docs/formation/InterMesh-Formation-Junior-a-Expert.pdf"
                  target="_blank"
                  rel="noreferrer"
                  className={`group rounded-xl border p-5 transition hover:border-cyan-500/60 ${HAIRLINE}`}
                >
                  <div className="flex items-center gap-2">
                    <BookOpen className={`h-4 w-4 ${ACCENT}`} />
                    <span className={`text-sm font-semibold ${HEADING}`}>Formation complète (français)</span>
                  </div>
                  <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>
                    63 pages, du niveau junior au niveau expert — installation, SDK,
                    orchestration, fédération, production. PDF.
                  </p>
                </a>

                <a
                  href="https://github.com/intermeshteam/intermesh"
                  target="_blank"
                  rel="noreferrer"
                  className={`group rounded-xl border p-5 transition hover:border-cyan-500/60 ${HAIRLINE}`}
                >
                  <div className="flex items-center gap-2">
                    <Github className={`h-4 w-4 ${ACCENT}`} />
                    <span className={`text-sm font-semibold ${HEADING}`}>Source repository</span>
                  </div>
                  <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>
                    The hub, both SDKs, the tests, and every guide referenced below.
                    Apache 2.0.
                  </p>
                </a>
              </div>

              <div className={`rounded-xl border p-5 ${HAIRLINE} ${ALT_SURFACE}`}>
                <div className={`mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] ${MUTED}`}>
                  Guides in the repository
                </div>
                <ul className={`space-y-2 text-sm ${BODY}`}>
                  {[
                    ['RFC-001-CORE-PROTOCOL.md', 'The protocol specification itself'],
                    ['SECURITY-AND-ENCRYPTION.md', 'Cryptography, key handling, audit log, admin authorization'],
                    ['AGENT-INTEGRATION.md', 'Adapters and orchestration — pipelines and fan-out'],
                    ['REMOTE-HUB.md', 'TLS, identity, PostgreSQL state, running several hubs'],
                    ['CAPACITY.md', 'Measured ceiling, backpressure settings, anti-patterns'],
                    ['AIR-GAPPED.md', 'Hardened Docker stack and closed-network deployment'],
                    ['BENCHMARKS.md', 'How the numbers above were measured, and what bounds them'],
                  ].map(([file, desc]) => (
                    <li key={file} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                      <a
                        href={`https://github.com/intermeshteam/intermesh/blob/main/docs/${file}`}
                        target="_blank"
                        rel="noreferrer"
                        className={`shrink-0 font-mono text-[12.5px] underline underline-offset-4 ${ACCENT}`}
                      >
                        {file}
                      </a>
                      <span className={MUTED}>{desc}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className={`rounded-xl border p-5 ${HAIRLINE}`}>
                <div className="flex items-center gap-2">
                  <Terminal className={`h-4 w-4 ${ACCENT}`} />
                  <span className={`text-sm font-semibold ${HEADING}`}>Offline, from your terminal</span>
                </div>
                <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>
                  Every subcommand documents itself, and that output is the most
                  current reference there is — the CLI moves faster than any page.
                </p>
                <div className="mt-3">
                  <Code>{`intermesh --help
intermesh hub --help
intermesh docs`}</Code>
                </div>
              </div>
            </Section>

            <div className={`border-t pt-8 ${HAIRLINE}`}>
              <p className={`text-sm leading-relaxed ${MUTED}`}>
                Something unclear, or missing?{' '}
                <a
                  href="https://github.com/intermeshteam/intermesh/issues"
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-cyan-600 underline underline-offset-4 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200"
                >
                  Open an issue on GitHub
                </a>
                . If you are evaluating this for a company,{' '}
                <Link
                  href="/pricing#enterprise"
                  className="font-medium text-cyan-600 underline underline-offset-4 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200"
                >
                  request a quote
                </Link>
                .
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
