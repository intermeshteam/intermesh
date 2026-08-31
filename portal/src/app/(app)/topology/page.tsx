'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Filter,
  Pause,
  Play,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { getHubUrl } from '@/lib/hub';

type NodeStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

type TopoNode = {
  id: string;
  label: string;
  sub: string;
  x: number;
  y: number;
  status: NodeStatus;
  kind: 'infra' | 'agent' | 'hub';
  latency: number;
  rps: number;
  real?: boolean;
  roles?: string[];
  capabilities?: string[];
  msg_count?: number;
};

type TopoEdge = { from: string; to: string };
type LogLine = { id: number; ts: string; level: 'INFO' | 'WARN' | 'ERROR'; msg: string };

const W = 1100;
const H = 720;

// The real topology of an InterMesh deployment is a hub and the agents
// registered with it. What used to be drawn here — API Gateway, Auth Service,
// Quota Enforcer, State Cache, Registry, Event Bus — are not components of
// this system. They were nine invented boxes with invented latencies and
// request rates, wired into a diagram that claimed to be live.
const INFRA_NODES: TopoNode[] = [
  // `sub` reste vide ici : l'URL du hub dépend du navigateur (localStorage) et
  // n'est donc pas connue au moment où ce module est évalué. Elle est renseignée
  // à la connexion.
  { id: 'hub', label: 'InterMesh Hub', sub: '', x: 550, y: 150, status: 'healthy', kind: 'hub', latency: 0, rps: 0 },
];

const INFRA_EDGES: TopoEdge[] = [];

function nowTs() {
  return new Date().toLocaleTimeString('en-GB', { hour12: false });
}

function drawRoundRect(c: CanvasRenderingContext2D, x: number, y: number, rw: number, rh: number, r: number) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + rw, y, x + rw, y + rh, r);
  c.arcTo(x + rw, y + rh, x, y + rh, r);
  c.arcTo(x, y + rh, x, y, r);
  c.arcTo(x, y, x + rw, y, r);
  c.closePath();
}

function layoutAgents(agents: any[]): TopoNode[] {
  const n = agents.length || 1;
  const startX = 180;
  const endX = 920;
  return agents.map((a, i) => {
    const t = n === 1 ? 0.5 : i / (n - 1);
    const x = startX + (endX - startX) * t;
    const y = 380 + (i % 2) * 70;
    const online = a.online !== false;
    const status: NodeStatus = !online ? 'unhealthy' : a.status === 'degraded' ? 'degraded' : 'healthy';
    return {
      id: `agent:${a.name}`,
      label: a.name,
      sub: (a.roles || []).join(',') || 'agent',
      x,
      y,
      status,
      kind: 'agent' as const,
      latency: 0, // not measured by the hub
      rps: status === 'unhealthy' ? 0 : a.msg_count || 0,
      real: true,
      roles: a.roles || [],
      capabilities: a.capabilities || [],
      msg_count: a.msg_count || 0,
    };
  });
}

export default function TopologyPage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const [infra] = useState<TopoNode[]>(INFRA_NODES);
  const [realAgents, setRealAgents] = useState<TopoNode[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>('hub');
  const [running, setRunning] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [hubConnected, setHubConnected] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  // Calling nowTs() during the initial render produces one timestamp on the
  // server and another on the client a second later, which is precisely the
  // hydration mismatch React was reporting. The first line is pushed from an
  // effect instead, where only the client runs.
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [filters, setFilters] = useState({ healthy: true, degraded: true, unhealthy: true, unknown: true });
  const bootLogged = useRef(false);
  const [lastUpdate, setLastUpdate] = useState('');
  const dragRef = useRef<{ active: boolean; x: number; y: number }>({ active: false, x: 0, y: 0 });
  /**
   * Per-agent "heat": how much traffic that agent has actually exchanged
   * recently, derived from the hub's own msg_count. It decays on its own, so
   * an idle mesh settles back to still lines instead of animating forever —
   * the flow means work is happening, or it means nothing at all.
   */
  const heatRef = useRef<Map<string, { last: number; heat: number }>>(new Map());

  /**
   * Raises an agent's heat when the hub reports work involving it.
   *
   * The snapshot's msg_count only arrives once, at registration, so a delta
   * against it stays at zero forever and nothing ever flowed. Task events are
   * what actually mark an agent as busy.
   */
  const bumpHeat = useCallback((name?: string, amount = 0.55) => {
    if (!name) return;
    const id = `agent:${name}`;
    const prev = heatRef.current.get(id) ?? { last: 0, heat: 0 };
    heatRef.current.set(id, { last: prev.last, heat: Math.min(1, prev.heat + amount) });
  }, []);
  const logIdRef = useRef(10);
  const wsRef = useRef<WebSocket | null>(null);

  const nodes = useMemo(() => [...infra, ...realAgents], [infra, realAgents]);
  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const edges = useMemo(() => {
    const agentEdges: TopoEdge[] = realAgents.map((a) => ({ from: 'hub', to: a.id }));
    for (let i = 0; i < realAgents.length - 1; i++) {
      agentEdges.push({ from: realAgents[i].id, to: realAgents[i + 1].id });
    }
    return [...INFRA_EDGES, ...agentEdges];
  }, [realAgents]);

  const counts = useMemo(() => {
    const c = { healthy: 0, degraded: 0, unhealthy: 0, unknown: 0, total: nodes.length, real: realAgents.length };
    nodes.forEach((n) => { c[n.status] += 1; });
    return c;
  }, [nodes, realAgents.length]);

  const selected = selectedId ? nodeMap.get(selectedId) || null : null;

  const pushLog = useCallback((level: LogLine['level'], msg: string) => {
    logIdRef.current += 1;
    setLogs((prev) => [{ id: logIdRef.current, ts: nowTs(), level, msg }, ...prev].slice(0, 60));
  }, []);

  useEffect(() => {
    if (bootLogged.current) return;
    bootLogged.current = true;
    pushLog('INFO', 'Topology initialised — waiting for the hub stream.');
  }, [pushLog]);

  const toggleFullscreen = async () => {
    const el = shellRef.current;
    if (!el) return;
    try {
      if (!document.fullscreenElement) {
        await el.requestFullscreen();
        setFullscreen(true);
      } else {
        await document.exitFullscreen();
        setFullscreen(false);
      }
    } catch {
      pushLog('WARN', 'Fullscreen not supported');
    }
  };

  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFs);
    return () => document.removeEventListener('fullscreenchange', onFs);
  }, []);

  // WebSocket Hub connection
  useEffect(() => {
    let stopped = false;
    let retryTimer: any;

    const connect = () => {
      if (stopped) return;
      const hubUrl = getHubUrl();
      const ws = new WebSocket(hubUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setHubConnected(true);
        pushLog('INFO', `Hub connected (${hubUrl})`);
        ws.send(
          JSON.stringify({
            id: crypto.randomUUID(),
            version: 'intermesh/v1',
            type: 'register',
            sender: `topology_observer_${Math.random().toString(36).slice(2, 7)}`,
            content: { name: 'topology_observer', roles: ['observer', 'admin'] },
          })
        );
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'telemetry_event') {
            const c = msg.content || {};
            setLastUpdate(nowTs());

            if (c.event === 'snapshot') {
              const list = (c.agents || []).filter((a: any) => a.online !== false);
              setRealAgents(layoutAgents(list));
              pushLog('INFO', `Snapshot: ${list.length} active agent(s)`);
            }

            if (c.event === 'agent_connected' && c.agent) {
              const a = c.agent;
              setRealAgents((prev) => {
                const others = prev.filter((n) => n.label !== a.name);
                return layoutAgents([
                  ...others.map((n) => ({ name: n.label, roles: n.roles, capabilities: n.capabilities, status: n.status, online: true })),
                  { name: a.name || a.qualified_name, roles: a.roles || [], capabilities: a.capabilities || [], status: 'healthy', online: true },
                ]);
              });
              pushLog('INFO', `Agent connected: ${a.name || a.qualified_name}`);
            }

            if (c.event === 'task_submitted') {
              bumpHeat(c.orchestrator);
              bumpHeat(c.assignee);
              pushLog('INFO', `Task '${c.title}' → ${c.assignee}`);
            }

            if (c.event === 'task_completed') {
              bumpHeat(c.assignee, 0.4);
            }

            if (c.event === 'agent_disconnected') {
              const name = c.agent_name;
              setRealAgents((prev) =>
                prev.map((n) => (n.label === name ? { ...n, status: 'unhealthy', rps: 0, latency: 999 } : n))
              );
              pushLog('ERROR', `Agent disconnected: ${name} [FAILURE DETECTED]`);
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        setHubConnected(false);
        pushLog('WARN', 'Hub connection lost. Reconnecting...');
        setRealAgents((prev) => prev.map((n) => ({ ...n, status: 'unhealthy' as NodeStatus, rps: 0, latency: 999 })));
        retryTimer = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [pushLog]);


  // Canvas render
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let raf = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const parent = canvas.parentElement;
      const pw = parent?.clientWidth || 900;
      const ph = parent?.clientHeight || 640;
      canvas.width = Math.floor(pw * dpr);
      canvas.height = Math.floor(ph * dpr);
      canvas.style.width = `${pw}px`;
      canvas.style.height = `${ph}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const drawNode = (n: TopoNode) => {
      const nw = n.kind === 'hub' ? 130 : 115;
      const nh = 42;
      const x = n.x - nw / 2;
      const y = n.y - nh / 2;
      const isSel = selectedId === n.id;
      const isFailed = n.status === 'unhealthy';

      // Background
      ctx.fillStyle = isFailed ? '#1A0A0A' : '#121215';
      ctx.strokeStyle = isFailed ? '#EF4444' : isSel ? '#FFFFFF' : '#27272A';
      ctx.lineWidth = isFailed || isSel ? 1.5 : 1;

      drawRoundRect(ctx, x, y, nw, nh, 4);
      ctx.fill();
      ctx.stroke();

      // Status indicator dot (6px)
      ctx.beginPath();
      ctx.fillStyle = isFailed ? '#EF4444' : n.status === 'degraded' ? '#F59E0B' : '#10B981';
      ctx.arc(x + 12, y + 14, 3, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.fillStyle = isFailed ? '#FCA5A5' : '#FFFFFF';
      ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.textAlign = 'left';
      const label = n.label.length > 15 ? n.label.slice(0, 14) + '…' : n.label;
      ctx.fillText(label, x + 22, y + 17);

      // Subtitle / IP
      ctx.fillStyle = isFailed ? '#EF4444' : '#71717A';
      ctx.font = '400 9px ui-monospace, SFMono-Regular, Consolas, monospace';
      ctx.fillText(isFailed ? 'FAILED / OFFLINE' : n.sub, x + 22, y + 30);
    };

    /** Cubic bezier between two nodes; horizontal handles give the fanned look. */
    const curve = (a: TopoNode, b: TopoNode) => {
      const dx = Math.abs(b.x - a.x);
      const bend = Math.max(60, dx * 0.45);
      return { c1x: a.x + bend, c1y: a.y, c2x: b.x - bend, c2y: b.y };
    };

    const bezierAt = (t: number, a: TopoNode, b: TopoNode) => {
      const { c1x, c1y, c2x, c2y } = curve(a, b);
      const u = 1 - t;
      const w0 = u * u * u, w1 = 3 * u * u * t, w2 = 3 * u * t * t, w3 = t * t * t;
      return {
        x: w0 * a.x + w1 * c1x + w2 * c2x + w3 * b.x,
        y: w0 * a.y + w1 * c1y + w2 * c2y + w3 * b.y,
      };
    };

    const draw = () => {
      const pw = canvas.clientWidth;
      const ph = canvas.clientHeight;
      ctx.clearRect(0, 0, pw, ph);
      ctx.save();
      ctx.translate(offset.x, offset.y);
      ctx.scale(zoom, zoom);

      const scaleFit = Math.min(pw / W, ph / H) * 0.95;
      ctx.translate((pw / zoom - W * scaleFit) / 2, (ph / zoom - H * scaleFit) / 2);
      ctx.scale(scaleFit, scaleFit);

      const visible = (n: TopoNode) => filters[n.status];

      // Decay every heat reading, then raise the ones whose agent sent
      // messages since the previous frame.
      const now = performance.now();
      heatRef.current.forEach((v, id) => {
        heatRef.current.set(id, { last: v.last, heat: v.heat * 0.99 });
      });

      // Flowing links
      for (const e of edges) {
        const a = nodeMap.get(e.from);
        const b = nodeMap.get(e.to);
        if (!a || !b || !visible(a) || !visible(b)) continue;

        const failed = a.status === 'unhealthy' || b.status === 'unhealthy';
        const heat = Math.max(
          heatRef.current.get(a.id)?.heat ?? 0,
          heatRef.current.get(b.id)?.heat ?? 0,
        );
        const { c1x, c1y, c2x, c2y } = curve(a, b);

        // Resting line. Visible enough to read the shape of the mesh, dim
        // enough that a busy link is unmistakable.
        const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
        if (failed) {
          grad.addColorStop(0, 'rgba(244, 63, 94, 0.35)');
          grad.addColorStop(1, 'rgba(244, 63, 94, 0.10)');
        } else {
          grad.addColorStop(0, `rgba(34, 211, 238, ${0.10 + heat * 0.45})`);
          grad.addColorStop(1, `rgba(167, 139, 250, ${0.10 + heat * 0.45})`);
        }
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1 + heat * 1.6;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.bezierCurveTo(c1x, c1y, c2x, c2y, b.x, b.y);
        ctx.stroke();

        if (!running || failed || heat < 0.02) continue;

        // Comets. Their number and speed follow the traffic, so an idle link
        // carries none at all.
        const count = 1 + Math.round(heat * 5);
        const speed = 0.00018 + heat * 0.00042;
        ctx.lineCap = 'round';
        for (let i = 0; i < count; i++) {
          const t = ((now * speed + i / count) % 1);
          const head = bezierAt(t, a, b);
          const tail = bezierAt(Math.max(0, t - 0.06), a, b);

          const cg = ctx.createLinearGradient(tail.x, tail.y, head.x, head.y);
          cg.addColorStop(0, 'rgba(34, 211, 238, 0)');
          cg.addColorStop(1, `rgba(186, 250, 255, ${0.5 + heat * 0.5})`);
          ctx.strokeStyle = cg;
          ctx.lineWidth = 1.5 + heat * 1.5;
          ctx.beginPath();
          ctx.moveTo(tail.x, tail.y);
          ctx.lineTo(head.x, head.y);
          ctx.stroke();

          ctx.shadowBlur = 10;
          ctx.shadowColor = 'rgba(34, 211, 238, 0.8)';
          ctx.beginPath();
          ctx.fillStyle = `rgba(224, 252, 255, ${0.7 + heat * 0.3})`;
          ctx.arc(head.x, head.y, 1.6 + heat, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        ctx.lineCap = 'butt';
      }

      // Draw nodes
      for (const n of nodes) {
        if (!visible(n)) continue;
        drawNode(n);
      }

      ctx.restore();
      raf = requestAnimationFrame(draw);
    };

    resize();
    raf = requestAnimationFrame(draw);
    window.addEventListener('resize', resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, [nodes, nodeMap, edges, filters, selectedId, running, zoom, offset]);

  const onCanvasClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const pw = rect.width;
    const ph = rect.height;
    const scaleFit = Math.min(pw / W, ph / H) * 0.95;
    const tx = offset.x + (pw - W * scaleFit * zoom) / 2;
    const ty = offset.y + (ph - H * scaleFit * zoom) / 2;
    const x = (mx - tx) / (scaleFit * zoom);
    const y = (my - ty) / (scaleFit * zoom);

    let hit: string | null = null;
    for (const n of nodes) {
      if (!filters[n.status]) continue;
      if (Math.abs(n.x - x) < 60 && Math.abs(n.y - y) < 22) {
        hit = n.id;
        break;
      }
    }
    setSelectedId(hit);
  };

  const markAgent = (id: string, status: NodeStatus) => {
    setRealAgents((prev) =>
      prev.map((n) => (n.id === id ? { ...n, status, latency: status === 'unhealthy' ? 999 : 30 } : n))
    );
    const label = nodeMap.get(id)?.label || id;
    pushLog(status === 'unhealthy' ? 'ERROR' : 'INFO', `${label} status changed to ${status}`);
  };

  return (
    <div
      ref={shellRef}
      className={`${
        fullscreen ? 'fixed inset-0 z-[200] bg-[#000000] p-6' : 'h-[calc(100vh-8rem)] min-h-[650px]'
      } space-y-4 font-sans flex flex-col notranslate`}
      translate="no"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0 border-b border-zinc-800/80 pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold tracking-tight text-white">Live Topology</h1>
            <span className="flex items-center space-x-1.5 text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
              <span className={`w-1.5 h-1.5 rounded-full ${hubConnected ? 'bg-emerald-400' : 'bg-red-500'}`} />
              <span>{hubConnected ? 'HUB CONNECTED' : 'HUB DISCONNECTED'}</span>
            </span>
            <span className="text-[10px] font-mono text-zinc-400 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded">
              REAL AGENTS: {counts.real}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time topology & node health inspection. Disconnected agents fail red automatically.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setRunning((v) => !v)}
            className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-md text-xs font-medium text-zinc-300 transition"
          >
            {running ? <Pause className="w-3.5 h-3.5 inline mr-1" /> : <Play className="w-3.5 h-3.5 inline mr-1" />}
            {running ? 'Pause' : 'Resume'}
          </button>
          <button onClick={() => setZoom((z) => Math.min(1.8, z + 0.1))} className="p-1.5 bg-zinc-900 border border-zinc-800 rounded-md text-zinc-300 hover:bg-zinc-800">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))} className="p-1.5 bg-zinc-900 border border-zinc-800 rounded-md text-zinc-300 hover:bg-zinc-800">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="px-3 py-1.5 bg-white text-black hover:bg-zinc-200 rounded-md text-xs font-semibold transition"
          >
            {fullscreen ? <Minimize2 className="w-3.5 h-3.5 inline mr-1" /> : <Maximize2 className="w-3.5 h-3.5 inline mr-1" />}
            {fullscreen ? 'Exit FS' : 'Fullscreen'}
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-12 gap-4 min-h-0">
        {/* Filters */}
        <aside className="xl:col-span-2 bg-[#0C0C0E] border border-zinc-800/80 rounded-lg p-4 space-y-4 overflow-y-auto">
          <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider font-mono">Filters</div>
          <div className="space-y-2 text-xs">
            {([
              ['healthy', 'Healthy', counts.healthy, 'bg-emerald-400'],
              ['degraded', 'Degraded', counts.degraded, 'bg-amber-400'],
              ['unhealthy', 'Unhealthy', counts.unhealthy, 'bg-red-400'],
              ['unknown', 'Unknown', counts.unknown, 'bg-zinc-500'],
            ] as const).map(([key, label, count, dotBg]) => (
              <label key={key} className="flex items-center justify-between cursor-pointer text-zinc-400 hover:text-white">
                <span className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={filters[key]}
                    onChange={(e) => setFilters((f) => ({ ...f, [key]: e.target.checked }))}
                    className="accent-white rounded"
                  />
                  <span className={`w-2 h-2 rounded-full ${dotBg}`} />
                  <span>{label}</span>
                </span>
                <span className="font-mono text-zinc-500 text-[11px]">{count}</span>
              </label>
            ))}
          </div>

          <div className="pt-4 border-t border-zinc-800/80 space-y-2 text-[11px] font-mono text-zinc-400">
            <div className="flex justify-between"><span>Total Nodes</span><span className="text-white">{counts.total}</span></div>
            <div className="flex justify-between"><span>Real Agents</span><span className="text-white">{counts.real}</span></div>
            <div className="flex justify-between"><span>Hub Status</span><span className={hubConnected ? 'text-emerald-400' : 'text-red-400'}>{hubConnected ? 'ONLINE' : 'OFFLINE'}</span></div>
          </div>
        </aside>

        {/* Canvas */}
        <section className="xl:col-span-7 bg-[#050507] border border-zinc-800/80 rounded-lg overflow-hidden relative min-h-[500px]">
          <canvas
            ref={canvasRef}
            className="w-full h-full cursor-crosshair"
            onClick={onCanvasClick}
            onMouseDown={(e) => {
              dragRef.current = { active: true, x: e.clientX - offset.x, y: e.clientY - offset.y };
            }}
            onMouseMove={(e) => {
              if (!dragRef.current.active) return;
              setOffset({ x: e.clientX - dragRef.current.x, y: e.clientY - dragRef.current.y });
            }}
            onMouseUp={() => { dragRef.current.active = false; }}
            onMouseLeave={() => { dragRef.current.active = false; }}
          />
        </section>

        {/* Inspector & Logs */}
        <aside className="xl:col-span-3 flex flex-col gap-4 min-h-0">
          <div className="bg-[#0C0C0E] border border-zinc-800/80 rounded-lg p-4 space-y-3 shrink-0">
            <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider font-mono">Node Inspector</div>
            {selected ? (
              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-sm font-bold text-white font-mono break-all">{selected.label}</div>
                  <div className="font-mono text-zinc-500 text-[11px] mt-0.5">{selected.sub}</div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${selected.status === 'unhealthy' ? 'bg-red-400' : 'bg-emerald-400'}`} />
                  <span className="capitalize font-mono text-xs">{selected.status}</span>
                </div>
                {selected.real && (
                  <div className="flex items-center space-x-2 pt-2">
                    <button
                      onClick={() => markAgent(selected.id, 'healthy')}
                      className="flex-1 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded text-xs font-medium border border-zinc-700"
                    >
                      Recover
                    </button>
                    <button
                      onClick={() => markAgent(selected.id, 'unhealthy')}
                      className="flex-1 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded text-xs font-medium border border-red-500/30"
                    >
                      Fail Node
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-zinc-500 py-4 text-center">Click any node on the graph to inspect.</p>
            )}
          </div>

          <div className="bg-[#0C0C0E] border border-zinc-800/80 rounded-lg p-4 flex-1 min-h-0 flex flex-col">
            <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider font-mono mb-3 flex items-center justify-between">
              <span>Event Stream</span>
              <span className="text-[10px] text-zinc-500">{logs.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 font-mono text-[10px] pr-1">
              {logs.map((l) => (
                <div key={l.id} className="flex items-start space-x-2 border-b border-zinc-800/40 pb-1.5">
                  <span className="text-zinc-600 shrink-0">{l.ts}</span>
                  <span className={`shrink-0 font-bold ${l.level === 'ERROR' ? 'text-red-400' : 'text-zinc-400'}`}>
                    {l.level}
                  </span>
                  <span className="text-zinc-300 leading-relaxed">{l.msg}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
