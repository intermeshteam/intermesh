'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Building2, CheckCircle2, Lock, Play, RotateCcw, XCircle } from 'lucide-react';

/**
 * A client-side replay of examples/negociation_partenariat.py — not a live
 * hub. Standing up a public InterMesh hub for anonymous visitors to hit is a
 * real infrastructure and cost decision (a persistent process, not a
 * serverless function, plus abuse surface from unauthenticated traffic) that
 * deserves being made deliberately, not shipped silently inside a landing
 * page. This delivers the same value — watching the mandate-bounded
 * negotiation actually play out — by porting the exact evaluate() logic to
 * TypeScript and running it in the browser. It says so at the bottom, with a
 * link to the real script, rather than letting anyone assume there is a live
 * backend behind it.
 */

const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const HEADING = 'text-slate-900 dark:text-white';
const BODY = 'text-slate-600 dark:text-slate-400';
const MUTED = 'text-slate-500 dark:text-slate-500';

const MAX_TURNS = 5;
const REVEAL_MS = 650;

interface Offer {
  commission: number;
  duration: number;
  volume: number;
  exclusive: boolean;
}

interface Mandate {
  name: string;
  role: string;
  commissionWanted: number;
  commissionLimit: number;
  durationWanted: number;
  durationFloor: number;
  volumeMin: number;
}

const PRODUCER: Mandate = {
  name: 'Domaine Verdier',
  role: 'Producer',
  commissionWanted: 20,
  commissionLimit: 15,
  durationWanted: 24,
  durationFloor: 24,
  volumeMin: 400,
};

const SCENARIOS: Record<'compatible' | 'strained', { label: string; distributor: Mandate }> = {
  compatible: {
    label: 'Compatible mandates',
    distributor: {
      name: 'TerraSeine',
      role: 'Distributor',
      commissionWanted: 12,
      commissionLimit: 18,
      durationWanted: 36,
      durationFloor: 24,
      volumeMin: 300,
    },
  },
  strained: {
    label: 'Strained mandates',
    distributor: {
      name: 'TerraSeine',
      role: 'Distributor',
      commissionWanted: 12,
      commissionLimit: 14, // same as `--commission-max 14` on the real script
      durationWanted: 36,
      durationFloor: 24,
      volumeMin: 300,
    },
  },
};

function summarize(o: Offer): string {
  return `${o.commission}% · ${o.duration}mo · ${o.volume}u/yr · ${o.exclusive ? 'exclusive' : 'non-exclusive'}`;
}

type Verdict =
  | { status: 'accepted'; offer: Offer }
  | { status: 'broken'; reason: string }
  | { status: 'counter'; offer: Offer; reason: string };

/** Direct port of evaluer() from examples/negociation_partenariat.py. */
function evaluate(mandate: Mandate, offer: Offer, turn: number, isProducerSide: boolean): Verdict {
  const { commission, duration, exclusive, volume } = offer;
  let acceptable: boolean;

  if (isProducerSide) {
    acceptable = commission >= mandate.commissionLimit;
    if (exclusive && volume < mandate.volumeMin) {
      return {
        status: 'counter',
        offer: { ...offer, exclusive: false },
        reason: `exclusivity needs ${mandate.volumeMin}+ units/yr`,
      };
    }
  } else {
    acceptable = commission <= mandate.commissionLimit;
  }

  if (duration < mandate.durationFloor) {
    return { status: 'broken', reason: `duration below ${mandate.durationFloor} months` };
  }
  if (acceptable) {
    return { status: 'accepted', offer };
  }

  const step = (mandate.commissionLimit - commission) / Math.max(1, MAX_TURNS - turn);
  let proposed = Math.round((commission + step) * 10) / 10;
  proposed = isProducerSide ? Math.min(proposed, mandate.commissionLimit) : Math.max(proposed, mandate.commissionLimit);

  if (Math.abs(proposed - commission) < 0.2) {
    return { status: 'broken', reason: 'positions frozen, no room left to concede' };
  }
  return { status: 'counter', offer: { ...offer, commission: proposed }, reason: 'adjusting commission' };
}

interface LogLine {
  turn: number;
  from: string;
  text: string;
  tone: 'neutral' | 'good' | 'bad';
}

interface RunResult {
  lines: LogLine[];
  outcome: 'success' | 'failure';
  finalOffer?: Offer;
  turns: number;
}

/** Direct port of the for-loop in scenario() from the same script. */
function runNegotiation(distributor: Mandate): RunResult {
  const lines: LogLine[] = [];
  let offer: Offer = {
    commission: distributor.commissionWanted,
    duration: distributor.durationWanted,
    volume: distributor.volumeMin,
    exclusive: true,
  };

  for (let turn = 1; turn <= MAX_TURNS; turn++) {
    lines.push({ turn, from: distributor.name, text: `proposes ${summarize(offer)}`, tone: 'neutral' });

    const response = evaluate(PRODUCER, offer, turn, true);

    if (response.status === 'accepted') {
      lines.push({ turn, from: PRODUCER.name, text: `accepts ${summarize(response.offer)}`, tone: 'good' });
      return { lines, outcome: 'success', finalOffer: response.offer, turns: turn };
    }
    if (response.status === 'broken') {
      lines.push({ turn, from: PRODUCER.name, text: `breaks off — ${response.reason}`, tone: 'bad' });
      return { lines, outcome: 'failure', turns: turn };
    }

    lines.push({ turn, from: PRODUCER.name, text: `counters ${summarize(response.offer)} (${response.reason})`, tone: 'neutral' });

    const counter = response.offer;
    const ours = evaluate(distributor, counter, turn, false);

    if (ours.status === 'broken') {
      lines.push({ turn, from: distributor.name, text: `breaks off — ${ours.reason}`, tone: 'bad' });
      return { lines, outcome: 'failure', turns: turn };
    }
    if (ours.status === 'accepted') {
      offer = counter;
      continue;
    }
    offer = ours.offer;
  }

  return { lines, outcome: 'failure', turns: MAX_TURNS };
}

function OrgCard({
  name,
  role,
  tone,
  mandate,
  revealed,
}: {
  name: string;
  role: string;
  tone: 'cyan' | 'violet';
  mandate: { commission: string; duration: string };
  revealed: boolean;
}) {
  const color = tone === 'cyan' ? 'text-cyan-600 dark:text-cyan-400' : 'text-violet-600 dark:text-violet-400';
  return (
    <div className={`rounded-xl border bg-white p-5 dark:bg-white/[0.02] ${HAIRLINE}`}>
      <div className="flex items-center gap-2">
        <Building2 className={`h-4 w-4 stroke-[1.6] ${color}`} />
        <span className={`text-sm font-semibold ${HEADING}`}>{name}</span>
        <span className={`ml-auto text-xs ${MUTED}`}>{role}</span>
      </div>
      <div className={`mt-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-mono transition-opacity duration-500 ${HAIRLINE} ${
        revealed ? BODY : MUTED
      }`}>
        {revealed ? (
          <span>commission ≤ {mandate.commission} · duration ≥ {mandate.duration}mo</span>
        ) : (
          <>
            <Lock className="h-3 w-3 shrink-0" />
            <span>mandate private until the deal closes</span>
          </>
        )}
      </div>
    </div>
  );
}

export default function NegotiationDemo() {
  const [scenario, setScenario] = useState<'compatible' | 'strained'>('compatible');
  const [lines, setLines] = useState<LogLine[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const generation = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [lines]);

  const handleRun = () => {
    const gen = ++generation.current;
    setRunning(true);
    setResult(null);
    setLines([]);

    const full = runNegotiation(SCENARIOS[scenario].distributor);
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) {
      setLines(full.lines);
      setResult(full);
      setRunning(false);
      return;
    }

    full.lines.forEach((line, i) => {
      setTimeout(() => {
        if (generation.current !== gen) return; // a newer run superseded this one
        setLines((prev) => [...prev, line]);
        if (i === full.lines.length - 1) {
          setResult(full);
          setRunning(false);
        }
      }, (i + 1) * REVEAL_MS);
    });
  };

  const distributor = SCENARIOS[scenario].distributor;
  const done = result !== null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(SCENARIOS) as Array<keyof typeof SCENARIOS>).map((key) => (
          <button
            key={key}
            onClick={() => !running && setScenario(key)}
            disabled={running}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
              scenario === key
                ? 'bg-slate-900 text-white dark:bg-white dark:text-[#08080A]'
                : `bg-slate-100 hover:bg-slate-200 dark:bg-white/[0.04] dark:hover:bg-white/[0.08] ${BODY}`
            }`}
          >
            {SCENARIOS[key].label}
          </button>
        ))}
        <button
          onClick={handleRun}
          disabled={running}
          className="ml-auto inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-cyan-500 to-violet-500 px-5 py-2 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60 dark:text-[#08080A]"
        >
          {done ? <RotateCcw className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {running ? 'Negotiating…' : done ? 'Replay' : 'Run negotiation'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <OrgCard
          name={distributor.name}
          role={distributor.role}
          tone="cyan"
          mandate={{ commission: `${distributor.commissionLimit}%`, duration: `${distributor.durationFloor}` }}
          revealed={done}
        />
        <OrgCard
          name={PRODUCER.name}
          role={PRODUCER.role}
          tone="violet"
          mandate={{ commission: `${PRODUCER.commissionLimit}%`, duration: `${PRODUCER.durationFloor}` }}
          revealed={done}
        />
      </div>

      <div
        ref={scrollRef}
        className={`h-64 overflow-y-auto rounded-xl border bg-[#0B0C10] p-4 font-mono text-[13px] leading-relaxed ${HAIRLINE}`}
      >
        {lines.length === 0 && (
          <p className="text-slate-500">Pick a scenario and press Run — each line is a real offer evaluated against a private mandate.</p>
        )}
        {lines.map((line, i) => (
          <div key={i} className="flex gap-2">
            <span className="shrink-0 text-slate-600">[{line.turn}]</span>
            <span
              className={
                line.tone === 'good'
                  ? 'text-emerald-400'
                  : line.tone === 'bad'
                  ? 'text-red-400'
                  : 'text-slate-300'
              }
            >
              <span className="text-slate-500">{line.from}</span> {line.text}
            </span>
          </div>
        ))}
      </div>

      {result && (
        <div
          className={`flex items-start gap-3 rounded-xl border p-4 ${
            result.outcome === 'success'
              ? 'border-emerald-500/30 bg-emerald-500/[0.06]'
              : 'border-red-500/30 bg-red-500/[0.06]'
          }`}
        >
          {result.outcome === 'success' ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
          ) : (
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          )}
          <div>
            <div className={`text-sm font-semibold ${HEADING}`}>
              {result.outcome === 'success'
                ? `Partnership reached in ${result.turns} round${result.turns > 1 ? 's' : ''}`
                : `No agreement after ${result.turns} round${result.turns > 1 ? 's' : ''}`}
            </div>
            <p className={`mt-1 text-sm ${BODY}`}>
              {result.outcome === 'success' && result.finalOffer
                ? `Settled at ${summarize(result.finalOffer)} — neither mandate was breached to get there.`
                : 'Positions never crossed. Each side held its floor rather than closing the deal — the mandate did its job.'}
            </p>
          </div>
        </div>
      )}

      <p className={`text-xs leading-relaxed ${MUTED}`}>
        This runs entirely in your browser — the same mandate-evaluation logic as{' '}
        <a
          href="https://github.com/intermeshteam/intermesh/blob/main/examples/negociation_partenariat.py"
          target="_blank"
          rel="noreferrer"
          className="font-medium text-cyan-600 underline underline-offset-4 dark:text-cyan-300"
        >
          examples/negociation_partenariat.py
        </a>
        , ported to TypeScript. No hub, no network calls — the real script actually runs two hubs and two agent
        processes talking over InterMesh; this replays the same decision rules so you can watch the outcome without
        installing anything.
      </p>
    </div>
  );
}
