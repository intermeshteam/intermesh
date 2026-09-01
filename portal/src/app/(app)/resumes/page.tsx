'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, ClipboardList, Search, XCircle } from 'lucide-react';
import { openHubSocket } from '@/lib/hub';
import { BORDER, CAPTION, CARD, TEXT_MUTED, TONE } from '@/lib/ui';

/**
 * Résumés — one card per finished task, carrying the plain-text summary the
 * agent wrote when it completed or failed the task.
 *
 * `summary` travels in the clear even for encrypted tasks (unlike
 * input_data/output_data), specifically so the hub and this console can
 * show it. The hub only streams live telemetry, not history, so — like the
 * rest of the Control Plane — this list starts empty and fills as agents
 * finish work while the page is open.
 */

type TaskState = 'running' | 'completed' | 'failed';

interface TaskSummary {
  taskId: string;
  title: string;
  orchestrator: string;
  assignee: string;
  state: TaskState;
  summary: string | null;
  errorMessage: string | null;
  finishedAt: number | null;
}

function relativeTime(epochSeconds: number | null): string {
  if (!epochSeconds) return '—';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function ResumesPage() {
  const [hubConnected, setHubConnected] = useState(false);
  const [tasks, setTasks] = useState<Record<string, TaskSummary>>({});
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'completed' | 'failed'>('ALL');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (stopped) return;
      const ws = openHubSocket();
      if (!ws) return; // adresse refusée par le navigateur : voir HubConnection
      wsRef.current = ws;

      ws.onopen = () => {
        setHubConnected(true);
        ws.send(
          JSON.stringify({
            id: crypto.randomUUID(),
            version: 'intermesh/v1',
            type: 'register',
            sender: `resumes_observer_${Math.random().toString(36).slice(2, 7)}`,
            content: { name: 'resumes_observer', roles: ['observer'] },
          }),
        );
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type !== 'telemetry_event') return;
          const c = msg.content || {};

          if (c.event === 'task_submitted') {
            setTasks((prev) => ({
              ...prev,
              [c.task_id]: {
                taskId: c.task_id,
                title: c.title,
                orchestrator: c.orchestrator,
                assignee: c.assignee,
                state: 'running',
                summary: null,
                errorMessage: null,
                finishedAt: null,
              },
            }));
          }

          if (c.event === 'task_completed' || c.event === 'task_failed') {
            const state: TaskState = c.event === 'task_completed' ? 'completed' : 'failed';
            setTasks((prev) => {
              const existing = prev[c.task_id];
              return {
                ...prev,
                [c.task_id]: {
                  taskId: c.task_id,
                  title: existing?.title ?? c.task_id,
                  orchestrator: existing?.orchestrator ?? '—',
                  assignee: existing?.assignee ?? '—',
                  state,
                  summary: c.summary ?? existing?.summary ?? null,
                  errorMessage: c.error_message ?? null,
                  finishedAt: Math.floor(Date.now() / 1000),
                },
              };
            });
          }
        } catch {
          /* a malformed frame is not worth tearing the socket down */
        }
      };

      ws.onclose = () => {
        setHubConnected(false);
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
  }, []);

  const finished = useMemo(
    () =>
      Object.values(tasks)
        .filter((t) => t.state !== 'running')
        .filter((t) => statusFilter === 'ALL' || t.state === statusFilter)
        .filter((t) => {
          if (!search) return true;
          const q = search.toLowerCase();
          return (
            t.title.toLowerCase().includes(q) ||
            t.orchestrator.toLowerCase().includes(q) ||
            t.assignee.toLowerCase().includes(q) ||
            (t.summary ?? '').toLowerCase().includes(q)
          );
        })
        .sort((a, b) => (b.finishedAt ?? 0) - (a.finishedAt ?? 0)),
    [tasks, search, statusFilter],
  );

  const completedCount = Object.values(tasks).filter((t) => t.state === 'completed').length;
  const failedCount = Object.values(tasks).filter((t) => t.state === 'failed').length;

  return (
    <div className="space-y-8 font-sans text-slate-100">
      {/* HEADER */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.07] pb-4">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight text-white">Summaries</h1>
          <p className="text-sm text-slate-400">
            What agents report when they finish a task — one card per completed or failed run.
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

      {/* FILTER BAR */}
      <div className={`flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between ${CARD}`}>
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search title, agent or summary…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-white/[0.07] bg-[#08080A] py-2 pl-9 pr-3 text-xs text-white outline-none placeholder:text-slate-500 focus:border-white/20"
          />
        </div>
        <div className="flex items-center gap-3 font-mono text-xs">
          <span className={CAPTION}>
            {completedCount} completed · {failedCount} failed
          </span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            className="rounded-lg border border-white/[0.07] bg-[#08080A] px-3 py-2 text-xs text-slate-300 outline-none"
          >
            <option value="ALL">All</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* CARDS */}
      {finished.length === 0 ? (
        <div className={`flex flex-col items-center justify-center gap-2 p-16 text-center ${CARD}`}>
          <ClipboardList className="h-8 w-8 stroke-[1] text-slate-500" />
          <p className="text-sm text-slate-300">No finished tasks yet.</p>
          <p className={`mt-1 text-xs ${TEXT_MUTED}`}>
            {hubConnected
              ? 'Summaries appear here as soon as an agent completes or fails a task while this page is open.'
              : 'Not connected to a hub.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {finished.map((t) => {
            const ok = t.state === 'completed';
            const tone = ok ? TONE.positive : TONE.danger;
            return (
              <div key={t.taskId} className={`space-y-3 p-5 ${CARD}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-white">{t.title}</div>
                    <div className="mt-0.5 font-mono text-[10.5px] text-slate-400">
                      {t.orchestrator} → {t.assignee}
                    </div>
                  </div>
                  <span
                    className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[10.5px] font-semibold ${tone.soft} ${tone.text}`}
                  >
                    {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                    {ok ? 'COMPLETED' : 'FAILED'}
                  </span>
                </div>

                <div className={`rounded-lg border ${BORDER} bg-[#08080A] p-3 text-xs leading-relaxed text-slate-300`}>
                  {t.summary || (
                    <span className="text-slate-500">No summary was reported for this task.</span>
                  )}
                </div>

                {!ok && t.errorMessage && (
                  <div className="rounded-lg border border-rose-900/50 bg-rose-500/[0.05] p-2.5 font-mono text-[11px] text-rose-300">
                    {t.errorMessage}
                  </div>
                )}

                <div className="flex items-center justify-between font-mono text-[10.5px] text-slate-400">
                  <span>{t.taskId.slice(0, 8)}</span>
                  <span>{relativeTime(t.finishedAt)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
