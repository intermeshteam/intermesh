'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Pencil, RotateCcw, X } from 'lucide-react';
import {
  DEFAULT_HUB_URL,
  getHubUrl,
  isBlockedByMixedContent,
  isValidHubUrl,
  resetHubUrl,
  setHubUrl,
} from '@/lib/hub';

/**
 * Hub address + live reachability, in the sidebar footer.
 *
 * The Control Plane is a client for a hub the visitor runs themselves, so the
 * address has to be theirs to set — it used to be a build-time constant shared
 * by every visitor of the deployment. Showing whether that address actually
 * answers matters just as much: without it the data pages simply render empty,
 * and nothing on screen distinguishes "no agents yet" from "not connected".
 */

/**
 * `blocked` is deliberately separate from `offline`. A remote ws:// hub is
 * refused by the browser before any packet is sent, so reporting it as
 * unreachable sends someone to inspect a firewall for a connection that was
 * never attempted. The fix is on the hub (serve wss://), not on the network.
 */
type Status = 'checking' | 'online' | 'offline' | 'blocked';

const PROBE_TIMEOUT_MS = 4000;

export default function HubConnection() {
  const [url, setUrl] = useState(DEFAULT_HUB_URL);
  const [status, setStatus] = useState<Status>('checking');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [invalid, setInvalid] = useState(false);
  const probeRef = useRef<WebSocket | null>(null);

  const probe = useCallback((target: string) => {
    probeRef.current?.close();

    // Checked before opening anything: the constructor would throw a
    // SecurityError, which is indistinguishable from a dead host once caught.
    if (isBlockedByMixedContent(target)) {
      setStatus('blocked');
      return;
    }

    setStatus('checking');

    let settled = false;
    const finish = (next: Status) => {
      if (settled) return;
      settled = true;
      setStatus(next);
    };

    try {
      const ws = new WebSocket(target);
      probeRef.current = ws;
      const timer = setTimeout(() => {
        finish('offline');
        ws.close();
      }, PROBE_TIMEOUT_MS);

      ws.onopen = () => {
        clearTimeout(timer);
        finish('online');
        ws.close();
      };
      ws.onerror = () => {
        clearTimeout(timer);
        finish('offline');
      };
      ws.onclose = () => {
        clearTimeout(timer);
        finish('offline');
      };
    } catch {
      finish('offline');
    }
  }, []);

  useEffect(() => {
    const current = getHubUrl();
    setUrl(current);
    probe(current);
    return () => probeRef.current?.close();
  }, [probe]);

  const startEditing = () => {
    setDraft(url);
    setInvalid(false);
    setEditing(true);
  };

  const commit = () => {
    const trimmed = draft.trim();
    if (!isValidHubUrl(trimmed)) {
      setInvalid(true);
      return;
    }
    setHubUrl(trimmed);
    setUrl(trimmed);
    setEditing(false);
    probe(trimmed);
  };

  const restoreDefault = () => {
    resetHubUrl();
    setUrl(DEFAULT_HUB_URL);
    setEditing(false);
    probe(DEFAULT_HUB_URL);
  };

  const dot =
    status === 'online'
      ? 'bg-emerald-400'
      : status === 'offline'
      ? 'bg-red-400'
      : status === 'blocked'
      ? 'bg-amber-400'
      : 'bg-slate-500 animate-pulse';
  const label =
    status === 'online'
      ? 'Connected'
      : status === 'offline'
      ? 'Not reachable'
      : status === 'blocked'
      ? 'Blocked by the browser'
      : 'Checking…';

  if (editing) {
    return (
      <div className="space-y-2">
        <label className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Hub address</label>
        <input
          value={draft}
          autoFocus
          onChange={(e) => {
            setDraft(e.target.value);
            setInvalid(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') setEditing(false);
          }}
          placeholder="ws://localhost:8765"
          className={`w-full rounded border bg-white/[0.04] px-2 py-1.5 font-mono text-[11px] text-slate-100 outline-none focus:border-cyan-500/50 ${
            invalid ? 'border-red-500/50' : 'border-white/[0.1]'
          }`}
        />
        {invalid && <p className="text-[10px] text-red-400">Must start with ws:// or wss://</p>}
        <div className="flex items-center gap-1.5">
          <button
            onClick={commit}
            className="inline-flex items-center gap-1 rounded bg-white/10 px-2 py-1 text-[10px] font-medium text-slate-100 transition hover:bg-white/[0.16]"
          >
            <Check className="h-3 w-3" /> Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] text-slate-400 transition hover:text-slate-100"
          >
            <X className="h-3 w-3" /> Cancel
          </button>
          <button
            onClick={restoreDefault}
            title={`Reset to ${DEFAULT_HUB_URL}`}
            className="ml-auto inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] text-slate-500 transition hover:text-slate-300"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Hub</span>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} aria-hidden />
        <span className="text-[10px] text-slate-400">{label}</span>
        <button
          onClick={startEditing}
          title="Change hub address"
          className="ml-auto text-slate-500 transition hover:text-slate-200"
          aria-label="Change hub address"
        >
          <Pencil className="h-3 w-3" />
        </button>
      </div>

      <div className="truncate font-mono text-[11px] text-slate-400" title={url}>
        {url.replace(/^wss?:\/\//, '')}
      </div>

      {status === 'offline' && (
        <p className="text-[10px] leading-relaxed text-slate-500">
          Start one with{' '}
          <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-slate-300">intermesh hub</code>, then
          refresh.
        </p>
      )}

      {status === 'blocked' && (
        <p className="text-[10px] leading-relaxed text-amber-400/80">
          This page is served over HTTPS, so it cannot open a plain{' '}
          <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono">ws://</code> socket to another machine — the
          browser refuses before connecting. A remote hub has to serve{' '}
          <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono">wss://</code> (
          <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono">--tls-cert</code> /{' '}
          <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono">--tls-key</code>). Only localhost is exempt.
        </p>
      )}
    </div>
  );
}
