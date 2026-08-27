'use client';

import React, { useEffect, useRef } from 'react';

type ServiceNode = {
  id: string;
  label: string;
  sub: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

type Edge = { from: string; to: string };
type Packet = { edgeIndex: number; t: number; speed: number };

const NODES: ServiceNode[] = [
  { id: 'cdn', label: 'CDN Edge', sub: '10.0.0.1', x: 0.06, y: 0.10, w: 100, h: 40 },
  { id: 'waf', label: 'WAF', sub: '10.0.0.3', x: 0.16, y: 0.10, w: 95, h: 40 },
  { id: 'api', label: 'API GW', sub: '10.0.1.5', x: 0.27, y: 0.10, w: 100, h: 40 },
  { id: 'auth', label: 'Auth Svc', sub: '10.1.0.12', x: 0.39, y: 0.10, w: 100, h: 40 },
  { id: 'user', label: 'User Svc', sub: '10.1.0.13', x: 0.51, y: 0.10, w: 100, h: 40 },
  { id: 'billing', label: 'Billing', sub: '10.1.0.14', x: 0.63, y: 0.10, w: 95, h: 40 },
  { id: 'pay', label: 'Pay Svc', sub: '10.1.0.15', x: 0.74, y: 0.10, w: 95, h: 40 },
  { id: 'lb1', label: 'LB-EXT', sub: '10.0.2.15', x: 0.14, y: 0.24, w: 100, h: 40 },
  { id: 'mesh', label: 'Service Mesh', sub: '10.0.2.20', x: 0.40, y: 0.24, w: 115, h: 40 },
  { id: 'gql', label: 'GraphQL', sub: '10.2.0.21', x: 0.54, y: 0.24, w: 100, h: 40 },
  { id: 'orch', label: 'Orchestrator', sub: '10.2.0.22', x: 0.68, y: 0.24, w: 115, h: 40 },
  { id: 'cp', label: 'Control Plane', sub: '10.5.0.1', x: 0.50, y: 0.38, w: 130, h: 46 },
  { id: 'router', label: 'Model Router', sub: '10.3.1.10', x: 0.12, y: 0.52, w: 115, h: 40 },
  { id: 'w1', label: 'Inf Worker 01', sub: '10.3.1.11', x: 0.26, y: 0.52, w: 115, h: 40 },
  { id: 'w2', label: 'Inf Worker 02', sub: '10.3.1.12', x: 0.40, y: 0.52, w: 115, h: 40 },
  { id: 'w3', label: 'Inf Worker 03', sub: '10.3.1.13', x: 0.54, y: 0.52, w: 115, h: 40 },
  { id: 'w4', label: 'Inf Worker 04', sub: '10.3.1.14', x: 0.68, y: 0.52, w: 115, h: 40 },
  { id: 'a1', label: 'Agent Alpha', sub: 'agent-01', x: 0.18, y: 0.64, w: 105, h: 40 },
  { id: 'a2', label: 'Agent Beta', sub: 'agent-02', x: 0.32, y: 0.64, w: 105, h: 40 },
  { id: 'a3', label: 'Agent Gamma', sub: 'agent-03', x: 0.46, y: 0.64, w: 110, h: 40 },
  { id: 'a4', label: 'Agent Delta', sub: 'agent-04', x: 0.60, y: 0.64, w: 110, h: 40 },
  { id: 'feat', label: 'Feature Store', sub: '10.3.3.30', x: 0.20, y: 0.76, w: 115, h: 40 },
  { id: 'mstore', label: 'Model Store', sub: '10.3.3.31', x: 0.36, y: 0.76, w: 110, h: 40 },
  { id: 'vdb', label: 'Vector DB', sub: '10.3.2.21', x: 0.68, y: 0.76, w: 100, h: 40 },
  { id: 'redis', label: 'Redis', sub: '10.4.1.40', x: 0.16, y: 0.90, w: 90, h: 40 },
  { id: 'pg', label: 'PostgreSQL', sub: '10.4.1.41', x: 0.30, y: 0.90, w: 105, h: 40 },
];

const EDGES: Edge[] = [
  { from: 'cdn', to: 'waf' }, { from: 'waf', to: 'api' }, { from: 'api', to: 'auth' },
  { from: 'auth', to: 'user' }, { from: 'user', to: 'billing' }, { from: 'billing', to: 'pay' },
  { from: 'api', to: 'lb1' }, { from: 'lb1', to: 'mesh' }, { from: 'mesh', to: 'gql' },
  { from: 'gql', to: 'orch' }, { from: 'gql', to: 'cp' }, { from: 'orch', to: 'cp' },
  { from: 'cp', to: 'router' }, { from: 'cp', to: 'w1' }, { from: 'cp', to: 'w2' },
  { from: 'router', to: 'w1' }, { from: 'w1', to: 'w2' }, { from: 'w2', to: 'w3' },
  { from: 'w3', to: 'w4' }, { from: 'w1', to: 'a1' }, { from: 'w2', to: 'a2' },
  { from: 'a1', to: 'a2' }, { from: 'a2', to: 'a3' }, { from: 'a3', to: 'a4' },
  { from: 'a1', to: 'feat' }, { from: 'a2', to: 'mstore' }, { from: 'a4', to: 'vdb' },
  { from: 'feat', to: 'redis' }, { from: 'mstore', to: 'pg' },
];

export default function NetworkBackground({ theme = 'dark' }: { theme?: 'dark' | 'light' }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf = 0;
    let w = 0;
    let h = 0;
    let packets: Packet[] = [];
    let t0 = performance.now();
    const nodeMap = new Map(NODES.map((n) => [n.id, n]));

    const isLight = theme === 'light';

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const center = (n: ServiceNode) => ({ x: n.x * w, y: n.y * h });

    const roundRect = (c: CanvasRenderingContext2D, x: number, y: number, rw: number, rh: number, r: number) => {
      c.beginPath();
      c.moveTo(x + r, y);
      c.arcTo(x + rw, y, x + rw, y + rh, r);
      c.arcTo(x + rw, y + rh, x, y + rh, r);
      c.arcTo(x, y + rh, x, y, r);
      c.arcTo(x, y, x + rw, y, r);
      c.closePath();
    };

    const drawArrow = (x1: number, y1: number, x2: number, y2: number) => {
      const ang = Math.atan2(y2 - y1, x2 - x1);
      const head = 5;
      const dx = x2 - x1;
      const dy = y2 - y1;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const sx = x1 + (dx / len) * 22;
      const sy = y1 + (dy / len) * 16;
      const ex = x2 - (dx / len) * 26;
      const ey = y2 - (dy / len) * 22;

      ctx.strokeStyle = isLight ? 'rgba(9, 9, 11, 0.08)' : 'rgba(34, 211, 238, 0.18)';
      ctx.fillStyle = ctx.strokeStyle;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(ex, ey);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - head * Math.cos(ang - 0.4), ey - head * Math.sin(ang - 0.4));
      ctx.lineTo(ex - head * Math.cos(ang + 0.4), ey - head * Math.sin(ang + 0.4));
      ctx.closePath();
      ctx.fill();
    };

    const drawNode = (n: ServiceNode, pulse: number) => {
      const c = center(n);
      const x = c.x - n.w / 2;
      const y = c.y - n.h / 2;

      ctx.fillStyle = isLight ? 'rgba(255, 255, 255, 0.85)' : 'rgba(10, 12, 18, 0.55)';
      ctx.strokeStyle = isLight ? 'rgba(228, 228, 231, 0.9)' : `rgba(148, 163, 184, ${0.18 + pulse * 0.12})`;
      ctx.lineWidth = 1;
      roundRect(ctx, x, y, n.w, n.h, 5);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = isLight ? 'rgba(9, 9, 11, 0.4)' : `rgba(34, 211, 238, ${0.35 + pulse * 0.2})`;
      ctx.fillRect(x + 1, y + 7, 2, n.h - 14);

      ctx.beginPath();
      ctx.fillStyle = isLight ? '#10B981' : `rgba(52, 211, 153, ${0.55 + pulse * 0.25})`;
      ctx.arc(x + 12, y + 13, 1.8, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = isLight ? '#09090B' : 'rgba(226, 232, 240, 0.72)';
      ctx.font = '600 10px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(n.label, x + 20, y + 16);

      ctx.fillStyle = isLight ? '#71717A' : 'rgba(148, 163, 184, 0.55)';
      ctx.font = '500 8px JetBrains Mono, ui-monospace, monospace';
      ctx.fillText(n.sub, x + 20, y + 29);
    };

    const initPackets = () => {
      packets = Array.from({ length: 30 }, () => ({
        edgeIndex: Math.floor(Math.random() * EDGES.length),
        t: Math.random(),
        speed: 0.0025 + Math.random() * 0.006,
      }));
    };

    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      ctx.clearRect(0, 0, w, h);

      for (const e of EDGES) {
        const a = nodeMap.get(e.from);
        const b = nodeMap.get(e.to);
        if (!a || !b) continue;
        const ca = center(a);
        const cb = center(b);
        drawArrow(ca.x, ca.y, cb.x, cb.y);
      }

      for (const p of packets) {
        p.t += p.speed;
        if (p.t >= 1) {
          p.t = 0;
          p.edgeIndex = Math.floor(Math.random() * EDGES.length);
          p.speed = 0.0025 + Math.random() * 0.006;
        }
        const e = EDGES[p.edgeIndex];
        const a = nodeMap.get(e.from);
        const b = nodeMap.get(e.to);
        if (!a || !b) continue;
        const ca = center(a);
        const cb = center(b);
        const x = ca.x + (cb.x - ca.x) * p.t;
        const y = ca.y + (cb.y - ca.y) * p.t;

        ctx.beginPath();
        ctx.fillStyle = isLight ? 'rgba(9, 9, 11, 0.6)' : 'rgba(34, 211, 238, 0.85)';
        ctx.arc(x, y, isLight ? 2 : 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      for (let i = 0; i < NODES.length; i++) {
        const pulse = (Math.sin(t * 1.8 + i * 0.28) + 1) / 2;
        drawNode(NODES[i], pulse * 0.3);
      }

      raf = requestAnimationFrame(draw);
    };

    resize();
    initPackets();
    raf = requestAnimationFrame(draw);
    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 0, opacity: theme === 'light' ? 0.6 : 0.42 }}
      aria-hidden="true"
    />
  );
}
