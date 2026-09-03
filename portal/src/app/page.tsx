'use client';

import BrandName from '@/components/BrandName';
import React, { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Copy,
  Check,
  Terminal,
  ShieldCheck,
  Globe,
  Lock,
  Layers,
  Network,
  ShieldAlert,
  Building2,
  ArrowLeftRight,
  FileSearch,
  Headphones,
  Search,
  KeyRound,
  Send,
  ScrollText,
  Fingerprint,
  Filter,
  Unplug,
  Workflow,
  ChevronDown,
} from 'lucide-react';
import NetworkBackground from '@/components/NetworkBackground';
import CodeShowcase from '@/components/CodeShowcase';
import InterMeshLogo from '@/components/InterMeshLogo';
import AngledBand from '@/components/AngledBand';
import ThemeToggle from '@/components/ThemeToggle';
import NegotiationDemo from '@/components/NegotiationDemo';

/* ------------------------------------------------------------------ */
/* Primitives                                                          */
/* ------------------------------------------------------------------ */

/**
 * Shared surface tokens.
 *
 * Kept in one place rather than repeated inline: a light theme goes wrong the
 * moment one card keeps a hardcoded dark border, and that is impossible to
 * spot by eye across a page this long.
 */
const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const ALT_SURFACE = 'bg-slate-50 dark:bg-white/[0.015]';
const HEADING = 'text-slate-900 dark:text-white';
const BODY = 'text-slate-600 dark:text-slate-400';
const MUTED = 'text-slate-500 dark:text-slate-500';

/** Small uppercase label above a heading, in the brand gradient. */
function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-gradient-to-r from-cyan-600 to-violet-600 bg-clip-text text-xs font-semibold uppercase tracking-[0.18em] text-transparent dark:from-cyan-300 dark:to-violet-300">
      {children}
    </span>
  );
}

function SectionHead({
  eyebrow,
  title,
  lead,
}: {
  eyebrow: string;
  title: string;
  lead?: string;
}) {
  return (
    <div className="max-w-2xl space-y-4">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 className={`text-[2rem] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[2.6rem] ${HEADING}`}>
        {title}
      </h2>
      {lead && <p className={`text-base leading-relaxed ${BODY}`}>{lead}</p>}
    </div>
  );
}

/** Flat card that lifts on hover. Shadow in light, border glow in dark. */
function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border bg-white p-6 transition duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg hover:shadow-slate-900/[0.06] dark:bg-white/[0.02] dark:hover:border-white/[0.14] dark:hover:bg-white/[0.04] dark:hover:shadow-none ${HAIRLINE} ${className}`}
    >
      {children}
    </div>
  );
}

function IconChip({ icon: Icon, tone = 'cyan' }: { icon: React.ElementType; tone?: 'cyan' | 'violet' }) {
  const tones = {
    cyan: 'from-cyan-500/15 to-cyan-500/5 text-cyan-600 ring-cyan-500/20 dark:text-cyan-300 dark:ring-cyan-400/20',
    violet: 'from-violet-500/15 to-violet-500/5 text-violet-600 ring-violet-500/20 dark:text-violet-300 dark:ring-violet-400/20',
  };
  return (
    <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ring-1 ${tones[tone]}`}>
      <Icon className="h-[18px] w-[18px] stroke-[1.6]" />
    </div>
  );
}

function PrimaryButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-cyan-500 to-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-[0_8px_30px_-10px_rgba(0,212,255,0.6)] transition hover:brightness-110 dark:from-cyan-400 dark:to-violet-400 dark:text-[#08080A]"
    >
      {children}
      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

function TextLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="group inline-flex items-center gap-1.5 text-sm font-semibold text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200"
    >
      {children}
      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Content                                                             */
/* ------------------------------------------------------------------ */

const PROOF = [
  { value: '231', label: 'tests, zero failures' },
  { value: 'Ed25519', label: 'federated identity' },
  { value: 'RSA + AES', label: 'end-to-end encryption' },
  { value: 'Apache-2.0', label: 'fully open source' },
];

const LANGUAGES = [
  {
    id: 'go',
    label: 'Go',
    command: 'intermesh serve --name pricing --exec ./pricing-engine',
    code: `// pricing-engine — no InterMesh SDK
func main() {
    var in map[string]any
    json.NewDecoder(os.Stdin).Decode(&in)

    out := map[string]any{
        "total": in["quantity"].(float64) * in["unit_price"].(float64),
    }
    json.NewEncoder(os.Stdout).Encode(out)
}`,
  },
  {
    id: 'node',
    label: 'Node.js',
    command: 'intermesh serve --name pricing --exec "node agent.js"',
    code: `// agent.js — no InterMesh SDK
let data = '';
process.stdin.on('data', c => data += c);
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  process.stdout.write(JSON.stringify({
    total: input.quantity * input.unit_price,
  }));
});`,
  },
  {
    id: 'shell',
    label: 'Shell',
    command: 'intermesh serve --name echo --exec ./agent.sh',
    code: `#!/bin/bash
# Non-JSON stdout is wrapped as {"output": "..."}
# An echo is enough to make an agent.
read -r payload
echo "{\\"received\\": $payload}"`,
  },
  {
    id: 'http',
    label: 'HTTP service',
    command: 'intermesh serve --name scoring --http http://localhost:9000/task',
    code: `# Nothing to rewrite, nothing to restart.
# The task arrives as a JSON POST on your endpoint,
# the JSON reply goes back into the mesh.

POST /task  { "quantity": 1000, "unit_price": 115 }
200 OK      { "total": 115000 }`,
  },
];

const STEPS = [
  { icon: KeyRound, n: '01', title: 'Signed identity', body: 'An agent declares its capabilities. The hub returns a token carrying a SHA-256 fingerprint of its roles and permissions — tampering with either breaks the other.' },
  { icon: Search, n: '02', title: 'Discovery by capability', body: 'Agents are found by what they do, not by a hardcoded address that breaks the moment something moves.' },
  { icon: Send, n: '03', title: 'Sealed delegation', body: "The payload is encrypted with a single-use AES-256-GCM key, sealed with the recipient's RSA-2048 public key. The hub routes ciphertext." },
  { icon: ScrollText, n: '04', title: 'Everything chains in', body: 'Registration, delegation and completion append to a Merkle-chained log. Edit one entry in the database and the chain breaks, loudly.' },
];

const FEATURES = [
  { icon: Lock, tone: 'cyan' as const, title: 'End-to-end encryption', body: 'RSA-2048-OAEP and AES-256-GCM, client side. The hub routes without ever reading a plaintext payload.' },
  { icon: Globe, tone: 'violet' as const, title: 'Cross-language mesh', body: 'Native Python and Node.js SDKs, plus a universal bridge for everything else. A Python agent delegates to a Go binary transparently.' },
  { icon: ShieldCheck, tone: 'cyan' as const, title: 'Immutable Merkle audit', body: 'A SHA-256 chained event log, replayed and verified at startup: an entry edited directly in the database is detected.' },
  { icon: Network, tone: 'violet' as const, title: 'Hub-to-hub federation', body: 'Cross-organization peering with automatic reconnection, Ed25519 identity and verified TLS transport.' },
  { icon: ShieldAlert, tone: 'cyan' as const, title: 'Runaway guardrails', body: 'Capped delegation depth, per-agent rate limiting, and a circuit breaker that isolates an agent after repeated violations.' },
  { icon: Layers, tone: 'violet' as const, title: 'Orchestration', body: 'Pipelines chaining steps by capability, parallel fan-out, payment escrow, and encrypted state snapshots.' },
];

const LIMITS = [
  { title: 'Peering is manual', body: 'Each organization declares its peers by hand. There is no directory: ten partners means forty-five links to maintain.' },
  { title: 'No shared memory', body: 'Every task is an isolated request/response. Context travels only through the payloads you pass explicitly.' },
  { title: 'Egress filtering has a limit', body: 'It addresses leaks by negligence, not deliberate exfiltration. An insider agent that encrypts before sending gets through.' },
  { title: 'Resumed tasks can run twice', body: 'A task interrupted by a restart is reassigned on reconnect. Your executors must be idempotent.' },
];

/**
 * The page used to go straight from the headline to Ed25519 and Merkle
 * chains. That is proof for someone who already knows the field, and noise
 * for everyone else. These three blocks are the on-ramp: the problem in plain
 * words, the vocabulary the rest of the page relies on, and the questions a
 * reader would otherwise leave with.
 */
const WITHOUT = [
  'An agent can call tools, but it cannot find another agent. You hardcode an address, and it breaks the day something moves.',
  'Two teams wire their agents together with their own glue. Six months later nobody can say who asked for what, or prove it.',
  'Across two companies it stops entirely. Neither side hands over an API key that opens everything, so the work goes back to email.',
];

const WITH = [
  'Agents announce what they can do. Others address them by capability, not by a machine that may have moved.',
  'Registration, delegation and completion append to a chained log. Replay it and you have the whole history, or you find out it was edited.',
  'Two companies peer their hubs. Each keeps its own signing key, so either side can authenticate the other and neither can sign in its name.',
];

const GLOSSARY = [
  { term: 'Agent', body: 'Any program that does one job and can be asked to do it — a Python function, a Go binary, an HTTP endpoint. It does not have to involve a model.' },
  { term: 'Hub', body: 'The router the agents of one organization connect to. It knows who is online and where to send a message. It cannot read the message.' },
  { term: 'Capability', body: 'A label an agent declares about itself, such as pricing or translation. You address work to a capability; the hub picks who answers.' },
  { term: 'Delegation', body: 'One agent handing a task to another and waiting for the result. The chain of who delegated to whom is recorded.' },
  { term: 'Peering', body: 'A declared link between the hubs of two different organizations. Nothing crosses between two organizations that have not peered.' },
  { term: 'Egress policy', body: 'Your rule for what may leave: drop a field, redact a pattern, or block the payload. It applies to outbound traffic only.' },
  { term: 'Escrow', body: 'Payment held aside when a paid task starts, released to the provider only once the task completes.' },
  { term: 'Mesh', body: 'The whole set — your agents, your hub, and the peered hubs you have chosen to reach.' },
];

const FAQ = [
  {
    q: 'Do I have to rewrite my agents?',
    a: 'No. If your program reads JSON on stdin and writes JSON on stdout, one command puts it on the mesh. If it is already an HTTP service, point InterMesh at its URL and change nothing at all. The native Python and Node.js SDKs exist for agents you are writing from scratch, not as a requirement.',
  },
  {
    q: 'Does this replace LangChain, CrewAI or MCP?',
    a: 'No, and it is not trying to. Those help you build a single agent and connect it to tools and data. InterMesh starts after that: it connects agents that already work to each other, especially across a company boundary where neither side can be given the other’s credentials.',
  },
  {
    q: 'Can the hub read what my agents send?',
    a: 'Not the payload. It is encrypted on the sending agent with a single-use AES key sealed to the recipient’s public key, and the hub only routes ciphertext. The hub does see routing metadata — who talked to whom, when, and how large the message was — because it cannot deliver anything without it.',
  },
  {
    q: 'What happens if the hub goes down?',
    a: 'Agents reconnect on their own and state is restored from an encrypted snapshot, so work resumes. A task interrupted mid-flight is reassigned, which means your executors must be idempotent — running one twice must be safe. And a single hub is still a single point of failure today; that is on the roadmap, not in the box.',
  },
  {
    q: 'Do the agents have to be AI?',
    a: 'No. A shell script that echoes its input is a valid agent. The protocol cares about identity, routing and accountability, not about what runs behind the endpoint.',
  },
  {
    q: 'Is it ready for production?',
    a: 'The mechanisms described on this page exist and are covered by tests. The limitations further down are the ones that would bite you, and they are listed rather than hidden. Read them before deciding, and read RFC-001 before building on it.',
  },
];

/* ------------------------------------------------------------------ */

export default function LandingPage() {
  const installCommand = 'pip install intermesh';
  const [copied, setCopied] = useState(false);
  const [lang, setLang] = useState(LANGUAGES[0].id);

  const active = LANGUAGES.find((l) => l.id === lang) ?? LANGUAGES[0];

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="relative min-h-screen bg-white font-sans text-slate-900 selection:bg-cyan-500/25 dark:bg-[#08080A] dark:text-slate-50 " suppressHydrationWarning>
      {/* ================= NAV ================= */}
      <header className={`sticky top-0 z-50 border-b bg-white/80 backdrop-blur-xl dark:bg-[#08080A]/80 ${HAIRLINE}`}>
        <div className="mx-auto flex max-w-[1180px] items-center justify-between px-6 py-4">
          <Link href="/" className={`flex items-center gap-2.5 text-lg font-bold tracking-[0.18em] transition hover:opacity-80 notranslate ${HEADING}`} translate="no">
            <InterMeshLogo className="h-5 w-5 shrink-0" />
            <BrandName />
          </Link>

          <nav className={`hidden items-center gap-8 text-sm font-medium md:flex ${BODY}`}>
            <Link href="/dashboard" className="transition hover:text-slate-900 dark:hover:text-white">Control Plane</Link>
            <Link href="/docs" className="transition hover:text-slate-900 dark:hover:text-white">Docs</Link>
            <Link href="/pricing" className="transition hover:text-slate-900 dark:hover:text-white">Pricing</Link>
            <a href="https://github.com/intermeshteam/intermesh" target="_blank" rel="noreferrer" className="transition hover:text-slate-900 dark:hover:text-white">GitHub</a>
          </nav>

          <div className="flex items-center gap-3 text-sm">
            <ThemeToggle />
            <Link href="/auth" className={`hidden font-medium transition hover:text-slate-900 sm:block dark:hover:text-white ${BODY}`}>Log in</Link>
            <Link href="/signup" className="group inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 dark:bg-white dark:text-[#08080A] dark:hover:bg-slate-200">
              Start building
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ================= HERO ================= */}
      <section className="relative overflow-hidden">
        {/* The particle field only reads on a dark backdrop; on light it is
            noise over white, so it is hidden rather than dimmed. */}
        <div className="absolute inset-0 hidden opacity-50 dark:block">
          <NetworkBackground />
        </div>
        <AngledBand variant="bottom-right" />

        <div className="relative mx-auto grid max-w-[1180px] grid-cols-1 items-center gap-14 px-6 pb-28 pt-20 lg:grid-cols-2 lg:pb-36 lg:pt-28">
          <div className="space-y-8">
            <Eyebrow>The coordination protocol for AI agents</Eyebrow>

            <h1 className={`text-[3.1rem] font-bold leading-[1.02] tracking-[-0.045em] sm:text-[3.9rem] lg:text-[4.3rem] ${HEADING}`}>
              Agents that
              <br />
              <span className="bg-gradient-to-r from-cyan-600 via-cyan-500 to-violet-600 bg-clip-text text-transparent dark:from-cyan-300 dark:via-cyan-400 dark:to-violet-400">
                work together.
              </span>
            </h1>

            <p className={`max-w-lg text-lg leading-relaxed ${BODY}`}>
              Let AI agents discover each other, talk, and delegate work — across
              teams inside one company, and across the boundary between two
              organizations that do not trust each other.
            </p>

            <div className={`flex max-w-md items-center justify-between rounded-xl border bg-slate-50 px-4 py-3 font-mono text-sm dark:bg-white/[0.03] ${HAIRLINE}`}>
              <div className="flex items-center gap-2.5">
                <Terminal className="h-4 w-4 stroke-[1.6] text-cyan-600 dark:text-cyan-400" />
                <span className={MUTED}>$</span>
                <span className={`font-semibold ${HEADING}`}>{installCommand}</span>
              </div>
              <button
                onClick={handleCopyCmd}
                className={`rounded-md p-1.5 transition hover:bg-slate-900/[0.06] hover:text-slate-900 dark:hover:bg-white/5 dark:hover:text-white ${MUTED}`}
                aria-label="Copy install command"
              >
                {copied ? <Check className="h-4 w-4 text-cyan-600 dark:text-cyan-400" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-6 pt-1">
              <PrimaryButton href="/signup">Open Control Plane</PrimaryButton>
              <TextLink href="/docs">Read RFC-001</TextLink>
            </div>
          </div>

          <div className="lg:pl-4">
            <CodeShowcase />
          </div>
        </div>
      </section>

      {/* ================= PROOF ================= */}
      <section className={`relative border-y ${HAIRLINE} ${ALT_SURFACE}`}>
        <div className="mx-auto grid max-w-[1180px] grid-cols-2 px-6 lg:grid-cols-4">
          {PROOF.map((s, i) => (
            <div
              key={s.label}
              className={`py-9 pl-6 lg:pl-8 ${i % 2 === 1 ? `border-l ${HAIRLINE}` : ''} ${i >= 2 ? `border-t lg:border-t-0 ${HAIRLINE}` : ''} ${i > 0 ? `lg:border-l ${HAIRLINE}` : ''}`}
            >
              <div className="bg-gradient-to-r from-cyan-600 to-violet-600 bg-clip-text font-mono text-xl font-bold text-transparent dark:from-cyan-300 dark:to-violet-300">
                {s.value}
              </div>
              <div className={`mt-1.5 text-sm ${BODY}`}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ================= THE PROBLEM ================= */}
      <section className="relative py-24">
        <div className="mx-auto max-w-[1180px] space-y-14 px-6">
          <SectionHead
            eyebrow="Why this exists"
            title="Every agent is an island."
            lead="Building one capable agent is close to a solved problem. Getting two of them to work together — especially when they belong to different teams, or different companies — is still done by hand, one integration at a time."
          />

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card>
              <IconChip icon={Unplug} tone="violet" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>Without a protocol</h3>
              <ul className="mt-4 space-y-4">
                {WITHOUT.map((line) => (
                  <li key={line} className={`flex gap-3 text-sm leading-relaxed ${BODY}`}>
                    <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400 dark:bg-slate-600" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <IconChip icon={Workflow} tone="cyan" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>With InterMesh</h3>
              <ul className="mt-4 space-y-4">
                {WITH.map((line) => (
                  <li key={line} className={`flex gap-3 text-sm leading-relaxed ${BODY}`}>
                    <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-cyan-400 to-violet-400" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      </section>

      {/* ================= GLOSSARY ================= */}
      <section className={`relative border-t py-24 ${HAIRLINE} ${ALT_SURFACE}`}>
        <div className="mx-auto max-w-[1180px] space-y-12 px-6">
          <SectionHead
            eyebrow="Vocabulary"
            title="The words used on this page"
            lead="Eight terms carry most of the meaning here. They are worth two minutes, because everything below assumes them."
          />

          <dl className="grid grid-cols-1 gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {GLOSSARY.map((g) => (
              <div key={g.term} className="border-t pt-4 border-slate-200 dark:border-white/[0.07]">
                <dt className={`text-sm font-semibold ${HEADING}`}>{g.term}</dt>
                <dd className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>{g.body}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ================= ANY LANGUAGE ================= */}
      <section className="relative overflow-hidden py-24">
        <AngledBand variant="bottom-left" opacity={0.07} />

        <div className="relative mx-auto max-w-[1180px] space-y-12 px-6">
          <div className="grid grid-cols-1 items-end gap-8 lg:grid-cols-[1fr_auto]">
            <SectionHead
              eyebrow="One-line integration"
              title="Your agent already exists. Plug it in."
              lead="No SDK to learn on the foreign side. Your program reads JSON on stdin and writes JSON on stdout — that is the entire contract. A Go binary, a Node script, a shell one-liner, or an HTTP service already running."
            />
            <div className="flex flex-wrap gap-2 lg:justify-end">
              {LANGUAGES.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setLang(l.id)}
                  className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                    lang === l.id
                      ? 'bg-slate-900 text-white dark:bg-white dark:text-[#08080A]'
                      : `bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] dark:hover:text-white ${BODY}`
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Code stays dark in both themes: a terminal that turns white reads
              as a document, and syntax colours stop working. */}
          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0B0C10] dark:border-white/[0.08]">
            <div className="flex items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-5 py-3.5 font-mono text-sm">
              <span className="text-cyan-400">$</span>
              <span className="overflow-x-auto whitespace-nowrap text-slate-200">{active.command}</span>
            </div>
            <pre className="overflow-x-auto p-6 font-mono text-[12.5px] leading-relaxed text-slate-300">
              {active.code}
            </pre>
          </div>

          <p className={`max-w-2xl text-sm leading-relaxed ${MUTED}`}>
            The agent inherits end-to-end encryption, capability discovery and the
            audit log without a line of integration code. A program that overruns its
            timeout is killed along with its children.
          </p>
        </div>
      </section>

      {/* ================= CROSS-ORG ================= */}
      <section className={`relative border-t py-24 ${HAIRLINE} ${ALT_SURFACE}`}>
        <div className="mx-auto max-w-[1180px] space-y-14 px-6">
          <SectionHead
            eyebrow="Cross-organization federation"
            title="Two companies. No mutual trust required."
            lead="Each organization keeps its own hub. Peering opens a verifiable link between them, without ever sharing a signing secret."
          />

          <div className="grid grid-cols-1 items-stretch gap-5 lg:grid-cols-[1fr_auto_1fr]">
            <Card>
              <div className={`flex items-center gap-2 border-b pb-3 ${HAIRLINE}`}>
                <Building2 className="h-4 w-4 stroke-[1.6] text-cyan-600 dark:text-cyan-400" />
                <span className={`text-sm font-semibold ${HEADING}`}>Acme Corp</span>
                <span className="ml-auto font-mono text-xs text-cyan-600/80 dark:text-cyan-400/80">acme/hub</span>
              </div>
              <p className={`mt-4 text-sm leading-relaxed ${BODY}`}>
                Its procurement agent addresses <code className="text-cyan-600 dark:text-cyan-300">globex/pricing_engine</code>{' '}
                as if it were local. The hub relays; the answer comes back.
              </p>
              <div className={`mt-5 space-y-1.5 font-mono text-xs ${MUTED}`}>
                <div>acme/procurement_lead</div>
                <div>acme/finance_approver</div>
                <div>acme/legal_auditor</div>
              </div>
            </Card>

            <div className="flex items-center justify-center py-2 lg:flex-col lg:py-0">
              <div className="hidden w-px flex-1 bg-gradient-to-b from-transparent to-cyan-500/40 lg:block" />
              <div className={`flex items-center gap-2 rounded-full border bg-white px-3.5 py-1.5 font-mono text-xs text-violet-600 dark:bg-[#0B0C10] dark:text-violet-300 ${HAIRLINE}`}>
                <Lock className="h-3 w-3" />
                wss:// + Ed25519
              </div>
              <div className="hidden w-px flex-1 bg-gradient-to-b from-violet-500/40 to-transparent lg:block" />
            </div>

            <Card>
              <div className={`flex items-center gap-2 border-b pb-3 ${HAIRLINE}`}>
                <Building2 className="h-4 w-4 stroke-[1.6] text-violet-600 dark:text-violet-400" />
                <span className={`text-sm font-semibold ${HEADING}`}>Globex Inc.</span>
                <span className="ml-auto font-mono text-xs text-violet-600/80 dark:text-violet-400/80">globex/hub</span>
              </div>
              <p className={`mt-4 text-sm leading-relaxed ${BODY}`}>
                Verifies every relayed message against the public key Acme published.
                It can authenticate, never impersonate.
              </p>
              <div className={`mt-5 space-y-1.5 font-mono text-xs ${MUTED}`}>
                <div>globex/sales_director</div>
                <div>globex/pricing_engine</div>
                <div>globex/contract_signer</div>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <Card>
              <IconChip icon={Fingerprint} tone="cyan" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>Verifiable, unforgeable identity</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                Tokens are signed with an Ed25519 private key that never leaves its
                hub. Peers exchange public keys, never a shared secret — otherwise
                either side could sign in the other&apos;s name.
              </p>
            </Card>
            <Card>
              <IconChip icon={Lock} tone="violet" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>The link itself is protected</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                Plaintext peering to a remote host is refused: the handshake carries
                the public keys, so an in-path attacker could swap them. TLS with
                certificate and hostname verification, always on.
              </p>
            </Card>
            <Card>
              <IconChip icon={Filter} tone="cyan" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>You decide what leaves</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                An egress policy drops a field, redacts a pattern, or blocks the
                payload. Enforced by the agent before encryption, and by the hub at
                relay time. Internal exchanges are never filtered.
              </p>
            </Card>
          </div>
        </div>
      </section>

      {/* ================= NEGOTIATION DEMO ================= */}
      <section className={`relative border-t py-24 ${HAIRLINE}`}>
        <div className="mx-auto max-w-[1180px] space-y-10 px-6">
          <SectionHead
            eyebrow="See it work"
            title="Watch two mandates negotiate."
            lead="A distributor and a producer, each with a private mandate — what they want, what they will never cross. No human types the offers. Run it, or try the mandate that does not converge."
          />
          <NegotiationDemo />
        </div>
      </section>

      {/* ================= HOW IT WORKS ================= */}
      <section className="relative overflow-hidden py-24">
        <div className="mx-auto max-w-[1180px] space-y-14 px-6">
          <SectionHead
            eyebrow="How it works"
            title="Four steps, from two scripts to a mesh"
            lead="InterMesh is the layer underneath your framework of choice, not a replacement for it. A central hub routes messages between agents — it never reads their contents."
          />

          <div className="grid grid-cols-1 gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.n} className="space-y-4">
                <div className="flex items-center gap-3">
                  <IconChip icon={s.icon} tone="cyan" />
                  <span className={`font-mono text-xs ${MUTED}`}>{s.n}</span>
                </div>
                <h3 className={`text-base font-semibold ${HEADING}`}>{s.title}</h3>
                <p className={`text-sm leading-relaxed ${BODY}`}>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= USE CASES ================= */}
      <section className={`relative overflow-hidden border-t py-24 ${HAIRLINE}`}>
        <AngledBand variant="bottom-right" opacity={0.06} />

        <div className="relative mx-auto max-w-[1180px] space-y-14 px-6">
          <SectionHead
            eyebrow="What it unlocks"
            title="Three scenarios, available today"
            lead="Not projections: each rests on mechanisms that exist in the repository and are covered by tests."
          />

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <Card>
              <IconChip icon={ArrowLeftRight} tone="cyan" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>B2B supply chain</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                A factory agent detects a stock shortage and negotiates directly with
                the supplier&apos;s agent: offer, counter-offer, internal budget
                approval, signature. Payment is held in escrow and released on
                completion.
              </p>
              <div className={`mt-5 border-t pt-4 font-mono text-xs ${HAIRLINE} ${MUTED}`}>
                6 agents · 2 hubs · tested end to end
              </div>
            </Card>

            <Card>
              <IconChip icon={FileSearch} tone="violet" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>Due diligence and audit</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                The buyer requests documents; the seller&apos;s agent answers with real
                margin and bank details stripped out before transfer. The approved
                figures pass, the rest never crosses the boundary.
              </p>
              <div className={`mt-5 border-t pt-4 font-mono text-xs ${HAIRLINE} ${MUTED}`}>
                filtering active under E2E encryption
              </div>
            </Card>

            <Card>
              <IconChip icon={Headphones} tone="cyan" />
              <h3 className={`mt-5 text-base font-semibold ${HEADING}`}>Single point of contact</h3>
              <p className={`mt-2 text-sm leading-relaxed ${BODY}`}>
                A refund request pulls in support, finance and logistics in parallel.
                The pipeline resolves each agent by capability, so replacing one does
                not break the flow.
              </p>
              <div className={`mt-5 border-t pt-4 font-mono text-xs ${HAIRLINE} ${MUTED}`}>
                pipeline + fan-out, resolved at run time
              </div>
            </Card>
          </div>
        </div>
      </section>

      {/* ================= POSITIONING ================= */}
      <section className={`relative border-t py-24 ${HAIRLINE} ${ALT_SURFACE}`}>
        <div className="mx-auto max-w-[1180px] space-y-12 px-6">
          <SectionHead
            eyebrow="Where InterMesh sits"
            title="Complementary, not competing"
            lead="The landscape is crowded, and honesty serves better than a rigged comparison. Here is what each piece actually solves."
          />

          <div className={`overflow-x-auto rounded-xl border bg-white dark:bg-transparent ${HAIRLINE}`}>
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className={`border-b text-xs uppercase tracking-wider ${HAIRLINE} ${MUTED}`}>
                <tr>
                  <th className="px-6 py-4 font-semibold">Layer</th>
                  <th className="px-6 py-4 font-semibold">Connects</th>
                  <th className="px-6 py-4 font-semibold">Brings</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-white/[0.06]">
                <tr>
                  <td className={`px-6 py-5 font-semibold ${HEADING}`}>MCP</td>
                  <td className={`px-6 py-5 ${BODY}`}>An agent to tools and data</td>
                  <td className={`px-6 py-5 ${BODY}`}>Standardized tool access. A client/server relationship — asymmetric by design.</td>
                </tr>
                <tr>
                  <td className={`px-6 py-5 font-semibold ${HEADING}`}>A2A</td>
                  <td className={`px-6 py-5 ${BODY}`}>Agents to each other</td>
                  <td className={`px-6 py-5 ${BODY}`}>A peer-to-peer exchange format, backed by a broad coalition.</td>
                </tr>
                <tr className="bg-gradient-to-r from-cyan-500/[0.07] to-violet-500/[0.05]">
                  <td className="px-6 py-5 font-semibold text-cyan-700 dark:text-cyan-300 notranslate" translate="no">InterMesh</td>
                  <td className={`px-6 py-5 ${HEADING}`}>Organizations to each other</td>
                  <td className={`px-6 py-5 ${HEADING}`}>
                    The hub, end-to-end encryption, verifiable federated identity,
                    control over what leaves, and payment escrow.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className={`max-w-2xl text-sm leading-relaxed ${MUTED}`}>
            Transport and message format are the easy part — they have been solved
            several times over. What was missing is identity between organizations,
            governance of outbound data, and accountability for payment. That is where
            InterMesh works.
          </p>
        </div>
      </section>

      {/* ================= FEATURES ================= */}
      <section className="relative py-24">
        <div className="mx-auto max-w-[1180px] space-y-14 px-6">
          <SectionHead eyebrow="Built for production" title="What is in the box" />

          <div className="grid grid-cols-1 gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="space-y-4">
                <IconChip icon={f.icon} tone={f.tone} />
                <h3 className={`text-base font-semibold ${HEADING}`}>{f.title}</h3>
                <p className={`text-sm leading-relaxed ${BODY}`}>{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= LIMITATIONS ================= */}
      <section className={`relative border-t py-24 ${HAIRLINE} ${ALT_SURFACE}`}>
        <div className="mx-auto max-w-[1180px] space-y-12 px-6">
          <SectionHead
            eyebrow="What we are not claiming"
            title="RFC-001 is real, and it is not finished"
            lead="A page that only lists strengths is not trustworthy. Here is what to know before relying on this in production."
          />

          <div className="grid grid-cols-1 gap-x-10 gap-y-9 sm:grid-cols-2">
            {LIMITS.map((l) => (
              <div key={l.title} className="border-l-2 border-slate-300 pl-5 dark:border-white/10">
                <h3 className={`text-sm font-semibold ${HEADING}`}>{l.title}</h3>
                <p className={`mt-1.5 text-sm leading-relaxed ${BODY}`}>{l.body}</p>
              </div>
            ))}
          </div>

          <p className={`text-sm leading-relaxed ${MUTED}`}>
            The spec is public precisely so it can be argued with.{' '}
            <Link href="/docs" className="font-medium text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200">
              Read RFC-001
            </Link>{' '}
            and tell us where it is wrong.
          </p>
        </div>
      </section>

      {/* ================= FAQ ================= */}
      <section className="relative py-24">
        <div className="mx-auto max-w-[1180px] px-6">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,380px)_1fr]">
            <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
              <Eyebrow>Questions</Eyebrow>
              <h2 className={`text-[2rem] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[2.6rem] ${HEADING}`}>
                The ones you would ask.
              </h2>
              <p className={`text-base leading-relaxed ${BODY}`}>
                Answered straight, including where the answer is not flattering.
              </p>
            </div>

            {/* Native <details>: collapsing keeps the page readable, and it stays
                keyboard-operable and findable by in-page search without any JS. */}
            <div className={`divide-y border-y divide-slate-200 dark:divide-white/[0.07] ${HAIRLINE}`}>
              {FAQ.map((item) => (
                <details key={item.q} className="group">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-5 text-left [&::-webkit-details-marker]:hidden">
                    <span className={`text-base font-semibold ${HEADING}`}>{item.q}</span>
                    <ChevronDown
                      aria-hidden
                      className={`h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180 ${MUTED}`}
                    />
                  </summary>
                  <p className={`max-w-2xl pb-6 pr-10 text-sm leading-relaxed ${BODY}`}>{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ================= CTA ================= */}
      <section className={`relative overflow-hidden border-t py-28 ${HAIRLINE}`}>
        <AngledBand variant="both" opacity={0.14} />

        <div className="relative mx-auto max-w-[1180px] px-6">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
            <div className="space-y-6">
              <h2 className={`text-[2rem] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[2.6rem] ${HEADING}`}>
                Three commands, and your
                <br />
                <span className="bg-gradient-to-r from-cyan-600 to-violet-600 bg-clip-text text-transparent dark:from-cyan-300 dark:to-violet-300">
                  agents are talking.
                </span>
              </h2>
              <p className={`max-w-md text-base leading-relaxed ${BODY}`}>
                Open source under Apache-2.0. Free self-hosted tier up to 10 active
                agents, no account required to try it.
              </p>
              <div className="flex flex-wrap items-center gap-6 pt-1">
                <PrimaryButton href="/signup">Open Control Plane</PrimaryButton>
                <TextLink href="/docs">Read the spec</TextLink>
              </div>
            </div>

            <div className="space-y-2 rounded-xl border border-slate-800 bg-[#0B0C10] p-6 font-mono text-sm dark:border-white/10">
              <div><span className="text-cyan-400">$</span> <span className="text-slate-200">pip install intermesh</span></div>
              <div><span className="text-cyan-400">$</span> <span className="text-slate-200">intermesh hub</span></div>
              <div><span className="text-cyan-400">$</span> <span className="text-slate-200">intermesh serve --name bot --exec ./my-agent</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* ================= FOOTER ================= */}
      <footer className={`border-t py-12 ${HAIRLINE}`}>
        <div className={`mx-auto flex max-w-[1180px] flex-col items-center justify-between gap-4 px-6 text-sm md:flex-row ${MUTED}`}>
          <div className="flex items-center gap-2 font-medium">
            <InterMeshLogo className="h-4 w-4 shrink-0" />
            <span>InterMesh Protocol © 2026 · Apache 2.0</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="transition hover:text-slate-900 dark:hover:text-slate-300">Terms</Link>
            <Link href="/privacy" className="transition hover:text-slate-900 dark:hover:text-slate-300">Privacy</Link>
            <Link href="/docs" className="transition hover:text-slate-900 dark:hover:text-slate-300">Docs</Link>
            <a href="https://github.com/intermeshteam/intermesh" target="_blank" rel="noreferrer" className="transition hover:text-slate-900 dark:hover:text-slate-300">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
