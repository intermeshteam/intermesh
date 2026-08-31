'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  KeyRound,
  ListChecks,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  Terminal,
  Users,
} from 'lucide-react';
import { getHubUrl, openHubSocket } from '@/lib/hub';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import { BORDER, CAPTION, CARD, FIGURE, SURFACE_SUNKEN, TEXT_MUTED, TEXT_SECONDARY, TONE, type Tone } from '@/lib/ui';

/**
 * Overview.
 *
 * Everything rendered here comes from the hub's telemetry stream. The previous
 * version drew hardcoded SVG curves that trended upward regardless of the
 * value beside them — a chart climbing next to "0 agents" — and invented CPU,
 * memory and GPU figures by hashing each agent's name. Both are gone: a
 * console that shows numbers nobody can trace is worse than one that shows
 * fewer numbers.
 *
 * Counters are scoped to the lifetime of this view, and say so. The hub
 * reports current state, not history, so anything cumulative starts at zero
 * when the page opens.
 */

interface Agent {
  id: string;
  name: string;
  org: string;
  roles: string[];
  capabilities: string[];
  connectedAt: number | null;
  messages: number;
  status: string;
}

interface LogEntry {
  id: number;
  time: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  source: string;
  message: string;
}

const SAMPLE_MS = 3000;
const SERIES_LEN = 40;

function relativeTime(epochSeconds: number | null): string {
  if (!epochSeconds) return '—';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d`;
}

/**
 * Sampled series. Draws nothing until it has two real points — a single
 * sample cannot describe a trend, and inventing the rest is what made the
 * old cards untrustworthy.
 */
function Sparkline({ points, live, tone = 'accent' }: { points: number[]; live: boolean; tone?: Tone }) {
  const stroke = { accent: '#22d3ee', info: '#a78bfa', positive: '#34d399', warning: '#fbbf24', danger: '#fb7185', neutral: '#94a3b8' }[tone];
  const gradId = `spark-${tone}`;
  if (points.length < 2) {
    return (
      <div className="flex h-12 items-center text-[10px] font-mono text-slate-400">
        {live ? 'collecting…' : 'no data'}
      </div>
    );
  }

  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = max - min || 1;
  const step = 200 / (points.length - 1);

  const coords = points.map((v, i) => [i * step, 38 - ((v - min) / span) * 34]);
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `0,40 ${line} 200,40`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <div className="space-y-1">
      <svg className="h-12 w-full" viewBox="0 0 200 40" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill={`url(#${gradId})`} />
        <polyline points={line} fill="none" stroke={stroke} strokeWidth="1.75" vectorEffect="non-scaling-stroke" />
        <circle cx={lastX} cy={lastY} r="2.5" fill={stroke} />
      </svg>
      <div className="flex justify-between font-mono text-[9px] text-slate-400">
        <span>{Math.round(min)}</span>
        <span>{(points.length * SAMPLE_MS) / 1000}s window</span>
        <span>{Math.round(max)}</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  note,
  icon: Icon,
  series,
  live,
  tone = 'accent',
}: {
  label: string;
  value: React.ReactNode;
  note: string;
  icon: React.ElementType;
  series: number[];
  live: boolean;
  tone?: Tone;
}) {
  const t = TONE[tone];
  return (
    <div className={`${CARD} group relative overflow-hidden p-5 transition hover:border-white/[0.14]`}>
      {/* A wash of the tone, strongest at the top edge. Enough to tell the
          four cards apart at a glance without turning them into buttons. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />
      <div className="flex items-center justify-between">
        <span className={CAPTION}>{label}</span>
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${t.soft} ${t.text}`}>
          <Icon className="h-3.5 w-3.5 stroke-[1.6]" />
        </span>
      </div>

      <div className="mt-4 flex items-baseline gap-2.5">
        <span className={FIGURE}>{value}</span>
        <span className={`flex items-center gap-1.5 text-[11px] ${live ? t.text : 'text-slate-400'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${live ? t.dot : 'bg-slate-700'}`} />
          {live ? 'live' : 'offline'}
        </span>
      </div>

      <div className={`mt-1 text-[11px] ${TEXT_MUTED}`}>{note}</div>
      <div className="mt-4">
        <Sparkline points={series} live={live} tone={tone} />
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [isLive, setIsLive] = useState(true);
  const [logFilter, setLogFilter] = useState<string>('ALL');
  const [hubConnected, setHubConnected] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [tasksSubmitted, setTasksSubmitted] = useState(0);
  const [tasksCompleted, setTasksCompleted] = useState(0);
  const [events, setEvents] = useState(0);

  const [agentSeries, setAgentSeries] = useState<number[]>([]);
  const [taskSeries, setTaskSeries] = useState<number[]>([]);
  const [doneSeries, setDoneSeries] = useState<number[]>([]);
  const [eventSeries, setEventSeries] = useState<number[]>([]);

  const [generatedLicense, setGeneratedLicense] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);

  const logIdRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const latest = useRef({ agents: 0, tasks: 0, done: 0, events: 0 });

  latest.current = { agents: agents.length, tasks: tasksSubmitted, done: tasksCompleted, events };

  const pushLog = useCallback((level: LogEntry['level'], source: string, message: string) => {
    logIdRef.current += 1;
    setLogs((prev) => [{ id: logIdRef.current, time: new Date().toISOString(), level, source, message }, ...prev].slice(0, 60));
  }, []);

  // A session can reach this page without ever passing through the sign-in
  // form — an OAuth redirect, or a confirmation link. This is the backstop
  // that gives such an account its organization.
  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    import('@/lib/supabase/account').then((m) => m.ensurePendingOrganization());
  }, []);

  /* ---------------- Telemetry ---------------- */

  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (stopped) return;
      const hubUrl = getHubUrl();
      const ws = openHubSocket(hubUrl);
      if (!ws) return; // adresse refusée par le navigateur : voir HubConnection
      wsRef.current = ws;

      ws.onopen = () => {
        setHubConnected(true);
        pushLog('INFO', 'System', `Connected to hub ${hubUrl}`);
        ws.send(
          JSON.stringify({
            id: crypto.randomUUID(),
            version: 'intermesh/v1',
            type: 'register',
            sender: `dashboard_main_${Math.random().toString(36).slice(2, 7)}`,
            content: { name: 'dashboard_main', roles: ['observer', 'admin'] },
          }),
        );
      };

      ws.onmessage = (ev) => {
        if (!isLive) return;
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type !== 'telemetry_event') return;
          const c = msg.content || {};
          setEvents((n) => n + 1);

          if (c.event === 'snapshot') {
            const mapped: Agent[] = (c.agents || [])
              .filter((a: any) => a.online !== false)
              .map((a: any) => ({
                id: a.agent_id || a.name,
                name: a.name,
                org: String(a.name || '').includes('/') ? String(a.name).split('/')[0] : 'default',
                roles: a.roles || [],
                capabilities: a.capabilities || [],
                connectedAt: a.connected_at ?? null,
                messages: a.msg_count ?? 0,
                status: a.status || 'healthy',
              }));
            setAgents(mapped);
            pushLog('INFO', 'Registry', `Snapshot: ${mapped.length} agent(s) online`);
          }

          if (c.event === 'agent_connected' && c.agent) {
            const a = c.agent;
            const name = a.qualified_name || a.name;
            setAgents((prev) => [
              {
                id: a.agent_id || name,
                name,
                org: a.org_id || 'default',
                roles: a.roles || [],
                capabilities: a.capabilities || [],
                connectedAt: Math.floor(Date.now() / 1000),
                messages: 0,
                status: a.status || 'healthy',
              },
              ...prev.filter((p) => p.name !== name),
            ]);
            pushLog('INFO', 'Registry', `Agent registered: ${name}`);
          }

          if (c.event === 'agent_disconnected') {
            setAgents((prev) => prev.filter((p) => p.name !== c.agent_name));
            pushLog('WARN', 'Registry', `Agent disconnected: ${c.agent_name}`);
          }

          if (c.event === 'task_submitted') {
            setTasksSubmitted((n) => n + 1);
            pushLog('DEBUG', 'Tasks', `${c.orchestrator} → ${c.assignee}: ${c.title}`);
          }

          if (c.event === 'task_completed') {
            setTasksCompleted((n) => n + 1);
            pushLog('INFO', 'Tasks', `Task ${String(c.task_id).slice(0, 8)} completed`);
          }

          if (c.event === 'egress_blocked') {
            pushLog('WARN', 'Egress', `Blocked to ${c.target_org} by rule '${c.rule}'`);
          }
        } catch {
          /* a malformed frame is not worth tearing the socket down */
        }
      };

      ws.onclose = () => {
        setHubConnected(false);
        setAgents([]);
        pushLog('ERROR', 'System', 'Hub connection lost — retrying');
        retry = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [pushLog, isLive]);

  /* ---------------- Sampling ---------------- */

  useEffect(() => {
    const iv = setInterval(() => {
      const { agents: a, tasks: t, done: d, events: e } = latest.current;
      setAgentSeries((s) => [...s, a].slice(-SERIES_LEN));
      setTaskSeries((s) => [...s, t].slice(-SERIES_LEN));
      setDoneSeries((s) => [...s, d].slice(-SERIES_LEN));
      setEventSeries((s) => [...s, e].slice(-SERIES_LEN));
    }, SAMPLE_MS);
    return () => clearInterval(iv);
  }, []);

  /* ---------------- Control plane tools ---------------- */

  const handleGenerateLicense = async () => {
    try {
      const res = await fetch('/api/license/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_name: 'acme_corp', plan: 'free', max_agents: 10 }),
      });
      const data = await res.json();
      if (data.success) setGeneratedLicense(data.license_key);
    } catch {
      pushLog('ERROR', 'License', 'Token generation failed');
    }
  };

  const handleSimulateQuota = async () => {
    setSimulating(true);
    setSimResult(null);
    try {
      const res = await fetch('/api/agents/verify-slot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_active_agents: 10, max_allowed: 10 }),
      });
      setSimResult({ status: res.status, data: await res.json() });
    } catch (err: any) {
      setSimResult({ status: 500, error: err.message });
    } finally {
      setSimulating(false);
    }
  };

  const filteredLogs = useMemo(
    () => logs.filter((l) => logFilter === 'ALL' || l.level === logFilter),
    [logs, logFilter],
  );

  const orgs = useMemo(() => new Set(agents.map((a) => a.org)).size, [agents]);

  return (
    <div className="space-y-8 font-sans text-slate-100">
      {/* HEADER */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.07] pb-4">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight text-white">Overview</h1>
          <p className="text-sm text-slate-400">
            Live state reported by the hub this console is connected to.
          </p>
        </div>
        <div
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ${
            hubConnected ? TONE.positive.soft : TONE.danger.soft
          } ${hubConnected ? TONE.positive.text : TONE.danger.text}`}
        >
          <span className="relative flex h-1.5 w-1.5">
            {hubConnected && (
              <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${TONE.positive.dot}`} />
            )}
            <span className={`relative h-1.5 w-1.5 rounded-full ${hubConnected ? TONE.positive.dot : TONE.danger.dot}`} />
          </span>
          {hubConnected ? 'Hub connected' : 'Hub unreachable'}
        </div>
      </div>

      {/* METRICS */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="AGENTS ONLINE"
          value={agents.length}
          note={orgs > 1 ? `across ${orgs} organizations` : 'reported by the hub'}
          icon={Users}
          series={agentSeries}
          live={hubConnected}
        />
        <Metric
          label="TASKS SUBMITTED"
          value={tasksSubmitted}
          note="since this view opened"
          icon={ListChecks}
          tone="info"
          series={taskSeries}
          live={hubConnected}
        />
        <Metric
          label="TASKS COMPLETED"
          value={tasksCompleted}
          note={tasksSubmitted ? `${Math.round((tasksCompleted / tasksSubmitted) * 100)}% of submitted` : 'since this view opened'}
          icon={ArrowUpRight}
          tone="positive"
          series={doneSeries}
          live={hubConnected}
        />
        <Metric
          label="TELEMETRY EVENTS"
          value={events}
          note="received on this connection"
          icon={Activity}
          tone="neutral"
          series={eventSeries}
          live={hubConnected}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        {/* AGENTS */}
        <div className={`space-y-4 p-5 lg:col-span-7 ${CARD}`}>
          <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-white">Connected agents</span>
              <span className="rounded-md bg-white/[0.06] px-2 py-0.5 font-mono text-[10px] text-slate-300 ring-1 ring-white/10">{agents.length}</span>
            </div>
          </div>

          <div className="min-h-[300px] overflow-x-auto">
            {agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-slate-400">
                <Users className="h-8 w-8 stroke-[1]" />
                <p className="text-sm">
                  {hubConnected ? 'No agent is currently registered.' : 'Not connected to a hub.'}
                </p>
                <p className="mt-2 font-mono text-[11px] text-slate-400">
                  {hubConnected ? (
                    <>
                      Try <code className="rounded bg-white/[0.05] px-1 text-slate-400">intermesh serve --name bot --exec ./my-agent</code>
                    </>
                  ) : (
                    <>
                      Start one with <code className="rounded bg-white/[0.05] px-1 text-slate-400">intermesh hub</code>
                    </>
                  )}
                </p>
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/[0.07] text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                  <tr>
                    <th className="pb-3">Agent</th>
                    <th className="pb-3">Roles</th>
                    <th className="pb-3">Capabilities</th>
                    <th className="pb-3 text-right">Messages</th>
                    <th className="pb-3 text-right">Connected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05] text-slate-300">
                  {agents.map((a) => (
                    <tr key={a.id} className="transition hover:bg-white/[0.03]">
                      <td className="py-3">
                        <div className="font-semibold text-white">{a.name}</div>
                        <div className="font-mono text-[10px] text-slate-400">{String(a.id).slice(0, 8)}</div>
                      </td>
                      <td className="py-3 text-slate-400">{a.roles.join(', ') || '—'}</td>
                      <td className="py-3 text-slate-400">
                        {a.capabilities.length ? a.capabilities.join(', ') : <span className="text-slate-400">none declared</span>}
                      </td>
                      <td className="py-3 text-right font-mono text-slate-300">{a.messages}</td>
                      <td className="py-3 text-right font-mono text-slate-400">{relativeTime(a.connectedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* LOGS */}
        <div className={`flex h-[510px] flex-col space-y-4 p-5 lg:col-span-5 ${CARD}`}>
          <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
            <div className="flex items-center gap-2 font-mono text-xs">
              <Terminal className="h-4 w-4 stroke-[1.5] text-white" />
              <span className="font-bold uppercase tracking-wider text-white">Event stream</span>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                className="rounded border border-white/[0.07] bg-white/[0.05] px-2 py-1 font-mono text-[10px] text-slate-300 outline-none"
              >
                {['ALL', 'INFO', 'DEBUG', 'WARN', 'ERROR'].map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
              <button
                onClick={() => setIsLive((v) => !v)}
                title={isLive ? 'Pause the stream' : 'Resume the stream'}
                className="rounded border border-white/[0.07] p-1.5 text-slate-400 transition hover:text-white"
              >
                {isLive ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
              </button>
            </div>
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto font-mono text-[11px]">
            {filteredLogs.length === 0 ? (
              <div className="py-10 text-center text-slate-400">No events yet.</div>
            ) : (
              filteredLogs.map((log) => (
                <div key={log.id} className="flex gap-2">
                  <span className="shrink-0 text-slate-400" suppressHydrationWarning>
                    {log.time.slice(11, 23)}
                  </span>
                  <span
                    className={`shrink-0 font-bold ${
                      log.level === 'ERROR'
                        ? 'text-red-400'
                        : log.level === 'WARN'
                        ? 'text-amber-400'
                        : log.level === 'DEBUG'
                        ? 'text-slate-400'
                        : 'text-cyan-400'
                    }`}
                  >
                    {log.level}
                  </span>
                  <span className="shrink-0 font-semibold text-slate-300">{log.source}</span>
                  <span className="break-all text-slate-400">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* TOOLS */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className={`space-y-4 p-5 ${CARD}`}>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 stroke-[1.5] text-slate-300" />
                <h2 className="text-sm font-bold text-white">Self-hosted license token</h2>
              </div>
              <p className="text-xs leading-relaxed text-slate-400">
                Signs an Ed25519 token a hub can verify offline, without calling back to
                this portal.
              </p>
            </div>
            <button
              onClick={handleGenerateLicense}
              className="flex shrink-0 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:border-cyan-400/40 hover:bg-cyan-500/10 hover:text-white"
            >
              <RefreshCw className="h-3.5 w-3.5 stroke-[1.5] text-slate-400" />
              <span>Generate</span>
            </button>
          </div>

          {generatedLicense && (
            <div className="break-all rounded-lg border border-white/[0.07] bg-[#08080A] p-3 font-mono text-xs">
              <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400">Ed25519 signed token</div>
              <div className="select-all text-slate-100">{generatedLicense}</div>
            </div>
          )}
        </div>

        <div className={`space-y-4 p-5 ${CARD}`}>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 stroke-[1.5] text-slate-300" />
                <h2 className="text-sm font-bold text-white">Quota enforcement check</h2>
              </div>
              <p className="text-xs leading-relaxed text-slate-400">
                Calls the slot endpoint with the free tier already full, to confirm an
                eleventh registration is refused.
              </p>
            </div>
            <button
              onClick={handleSimulateQuota}
              disabled={simulating}
              className="flex shrink-0 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:border-cyan-400/40 hover:bg-cyan-500/10 hover:text-white disabled:opacity-50"
            >
              {simulating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Users className="h-3.5 w-3.5 stroke-[1.5] text-slate-400" />}
              <span>Run check</span>
            </button>
          </div>

          {simResult && (
            <div className={`space-y-1 rounded-lg border bg-[#08080A] p-3 font-mono text-xs ${simResult.status === 403 ? 'border-red-900/60' : 'border-white/[0.07]'}`}>
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-slate-300">HTTP response</span>
                <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${simResult.status === 403 ? 'border border-red-500/20 bg-red-500/10 text-red-400' : 'bg-white/[0.06] text-slate-300'}`}>
                  {simResult.status}
                </span>
              </div>
              <pre className="overflow-x-auto rounded border border-white/[0.07] bg-black/50 p-2.5 text-[11px] text-slate-300">
                {JSON.stringify(simResult.data ?? simResult.error, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
