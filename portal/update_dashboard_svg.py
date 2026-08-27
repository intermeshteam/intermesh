import os

page_path = os.path.expanduser('~/nexus/portal/src/app/(app)/dashboard/page.tsx')

dashboard_code = """'use client';

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Zap, 
  Cpu, 
  TrendingUp, 
  Terminal, 
  Pause, 
  Play, 
  Lock, 
  Copy, 
  Check, 
  ShieldAlert, 
  RefreshCw,
  ArrowUpRight,
  Key,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

interface AgentRow {
  id: string;
  name: string;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  model: string;
  role: string;
  cpu: number;
  mem: number;
  gpu: number;
  uptime: string;
}

interface LogEntry {
  id: number;
  time: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  source: string;
  message: string;
}

export default function MissionControlDashboard() {
  const [copiedKey, setCopiedKey] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [generatedLicense, setGeneratedLicense] = useState<string>('');

  const [logs, setLogs] = useState<LogEntry[]>([
    { id: 1, time: '2026-08-26T15:42:16.123Z', level: 'INFO', source: 'AgentManager', message: 'Registered agent CodeSage-Alpha (01)' },
    { id: 2, time: '2026-08-26T15:42:15.987Z', level: 'INFO', source: 'JobScheduler', message: 'Job 8f3a2cie-9b7d-4cia queued' },
    { id: 3, time: '2026-08-26T15:42:15.654Z', level: 'DEBUG', source: 'GPUAllocator', message: 'Allocated 1x A100-40GB to ModelTrainer-X (08)' },
    { id: 4, time: '2026-08-26T15:42:15.321Z', level: 'INFO', source: 'MetricsCollector', message: 'GPU Utilization: 78.6%' },
    { id: 5, time: '2026-08-26T15:42:14.876Z', level: 'WARN', source: 'JobRunner', message: 'Job 7c2d4b1a-3e8f-4d2b retrying (attempt 2)' },
    { id: 6, time: '2026-08-26T15:42:14.512Z', level: 'INFO', source: 'AgentHeartbeat', message: 'Heartbeat received from InfraPilot-Prod (03)' },
    { id: 7, time: '2026-08-26T15:42:14.210Z', level: 'DEBUG', source: 'Tokenizer', message: 'Processed 2.84M tokens in 1.00s' },
    { id: 8, time: '2026-08-26T15:42:13.987Z', level: 'INFO', source: 'ModelManager', message: 'Model gpt-4.1 loaded (instance 27)' },
    { id: 9, time: '2026-08-26T15:42:13.654Z', level: 'ERROR', source: 'JobRunner', message: 'Job 9d2f1b7e-6c3a-4b8f failed: TimeoutError' },
  ]);

  const [isLive, setIsLive] = useState(true);
  const [logFilter, setLogFilter] = useState<string>('ALL');

  const agents: AgentRow[] = [
    { id: '01', name: 'CodeSage-Alpha', status: 'ONLINE', model: 'gpt-4.1', role: 'coder', cpu: 12.4, mem: 34.7, gpu: 45.2, uptime: '2d 14h' },
    { id: '02', name: 'DataMiner-Delta', status: 'ONLINE', model: 'claude-3.7', role: 'analyst', cpu: 8.7, mem: 28.1, gpu: 12.3, uptime: '1d 03h' },
    { id: '03', name: 'InfraPilot-Prod', status: 'ONLINE', model: 'gpt-4.1', role: 'devops', cpu: 15.2, mem: 42.9, gpu: 67.8, uptime: '5d 21h' },
    { id: '04', name: 'TestRunner-Pro', status: 'ONLINE', model: 'claude-3.7', role: 'qa', cpu: 6.1, mem: 16.3, gpu: 8.7, uptime: '12h 11m' },
    { id: '05', name: 'DocWriter-Lite', status: 'ONLINE', model: 'gpt-4.1-mini', role: 'writer', cpu: 3.4, mem: 11.8, gpu: 0.0, uptime: '4h 32m' },
    { id: '06', name: 'APIGuard-Sec', status: 'ONLINE', model: 'gpt-4.1', role: 'security', cpu: 9.8, mem: 25.6, gpu: 23.1, uptime: '1d 18h' },
    { id: '07', name: 'UXDesigner-AI', status: 'ONLINE', model: 'claude-3.7', role: 'designer', cpu: 7.2, mem: 21.4, gpu: 18.9, uptime: '20h 45m' },
    { id: '08', name: 'ModelTrainer-X', status: 'ONLINE', model: 'gpt-4.1', role: 'ml-engineer', cpu: 28.7, mem: 63.2, gpu: 89.7, uptime: '3d 07h' },
  ];

  const sampleApiKey = "nx_live_acme_9f8a2c1b4e7d3f6a5b8c9d0e1f2a3b4c";

  const handleCopyKey = () => {
    navigator.clipboard.writeText(sampleApiKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const handleGenerateLicense = async () => {
    try {
      const res = await fetch('/api/license/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_name: 'acme_corp', plan: 'free', max_agents: 10 })
      });
      const data = await res.json();
      if (data.success) setGeneratedLicense(data.license_key);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSimulate11thAgent = async () => {
    setSimulating(true);
    setSimResult(null);
    try {
      const res = await fetch('/api/agents/verify-slot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_active_agents: 10, max_allowed: 10 })
      });
      const data = await res.json();
      setSimResult({ status: res.status, data });
    } catch (err: any) {
      setSimResult({ status: 500, error: err.message });
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(() => {
      const sources = ['AgentManager', 'JobScheduler', 'GPUAllocator', 'MetricsCollector', 'AgentHeartbeat'];
      const levels: ('INFO' | 'DEBUG' | 'WARN')[] = ['INFO', 'DEBUG', 'INFO', 'WARN'];
      const randomSource = sources[Math.floor(Math.random() * sources.length)];
      const randomLevel = levels[Math.floor(Math.random() * levels.length)];
      const now = new Date().toISOString();

      const newLog: LogEntry = {
        id: Date.now(),
        time: now,
        level: randomLevel,
        source: randomSource,
        message: `Processed telemetry pulse from node_${Math.floor(Math.random() * 8) + 1}`
      };

      setLogs(prev => [newLog, ...prev.slice(0, 25)]);
    }, 3000);

    return () => clearInterval(interval);
  }, [isLive]);

  const filteredLogs = logs.filter(log => logFilter === 'ALL' || log.level === logFilter);

  return (
    <div className="space-y-8 font-sans text-slate-100 notranslate" translate="no">
      
      {/* HEADER */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-sans flex items-center space-x-2">
            <span>A1</span>
            <span className="text-zinc-600">/</span>
            <span>MISSION CONTROL — AI INFRASTRUCTURE</span>
          </h1>
        </div>
        <div className="flex items-center space-x-6 text-xs text-zinc-400 font-sans">
          <span>ENVIRONMENT: <strong className="text-white font-semibold">PRODUCTION</strong></span>
          <span>REGION: <strong className="text-white font-semibold">US-EAST-1</strong></span>
        </div>
      </div>

      {/* KPI METRICS GRID (PURE VECTOR SVG ICONS) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* CARD 1 : TOTAL AGENTS */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-sans font-medium">
            <span>TOTAL AGENTS</span>
            <Users className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-white font-sans tracking-tight whitespace-nowrap">512</span>
            <span className="text-xs text-emerald-400 font-sans font-medium whitespace-nowrap">+12.45% vs 24h</span>
          </div>
          <div className="h-8 mt-3">
            <svg className="w-full h-full text-zinc-400 opacity-60" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 25 L15 20 L30 22 L45 15 L60 18 L75 8 L90 12 L100 5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        </div>

        {/* CARD 2 : ACTIVE JOBS */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-sans font-medium">
            <span>ACTIVE JOBS</span>
            <Zap className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-white font-sans tracking-tight whitespace-nowrap">1,237</span>
            <span className="text-xs text-emerald-400 font-sans font-medium whitespace-nowrap">+18.72% vs 24h</span>
          </div>
          <div className="h-8 mt-3">
            <svg className="w-full h-full text-zinc-400 opacity-60" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 20 L15 18 L30 25 L45 12 L60 10 L75 14 L90 5 L100 2" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        </div>

        {/* CARD 3 : GPU UTILIZATION */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-sans font-medium">
            <span>GPU UTILIZATION</span>
            <Cpu className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-white font-sans tracking-tight whitespace-nowrap">78.6%</span>
            <span className="text-xs text-emerald-400 font-sans font-medium whitespace-nowrap">+5.34% vs 24h</span>
          </div>
          <div className="h-8 mt-3">
            <svg className="w-full h-full text-zinc-400 opacity-60" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 15 L15 12 L30 18 L45 10 L60 22 L75 12 L90 15 L100 8" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        </div>

        {/* CARD 4 : TOKENS / SEC */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-sans font-medium">
            <span>TOKENS / SEC</span>
            <TrendingUp className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-white font-sans tracking-tight whitespace-nowrap">2.84M</span>
            <span className="text-xs text-emerald-400 font-sans font-medium whitespace-nowrap">+22.18% vs 24h</span>
          </div>
          <div className="h-8 mt-3">
            <svg className="w-full h-full text-zinc-400 opacity-60" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 22 L15 15 L30 19 L45 8 L60 14 L75 6 L90 10 L100 3" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        </div>

      </div>

      {/* SPLIT CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* CONNECTED AGENTS TABLE */}
        <div className="lg:col-span-7 bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between text-xs border-b border-zinc-800/80 pb-3 font-sans">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-white uppercase tracking-wider">CONNECTED AGENTS</span>
              <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px] font-mono">512 TOTAL</span>
            </div>
            <div className="flex items-center space-x-3 text-zinc-400 text-[11px]">
              <span className="cursor-pointer hover:text-white flex items-center space-x-1">
                <SlidersHorizontal className="w-3 h-3" />
                <span>FILTER</span>
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-sans text-xs">
              <thead className="text-[10px] text-zinc-500 border-b border-zinc-800 uppercase font-semibold">
                <tr>
                  <th className="pb-3">ID</th>
                  <th className="pb-3">NAME</th>
                  <th className="pb-3">STATUS</th>
                  <th className="pb-3">MODEL</th>
                  <th className="pb-3">ROLE</th>
                  <th className="pb-3">CPU%</th>
                  <th className="pb-3">MEM%</th>
                  <th className="pb-3">GPU%</th>
                  <th className="pb-3 text-right">UPTIME</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40 text-zinc-300 text-xs">
                {agents.map((a) => (
                  <tr key={a.id} className="hover:bg-zinc-800/30 transition">
                    <td className="py-3 text-zinc-500 font-mono">{a.id}</td>
                    <td className="py-3 font-semibold text-white">{a.name}</td>
                    <td className="py-3">
                      <span className="inline-flex items-center space-x-1.5 text-emerald-400 text-[10px] font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        <span>ONLINE</span>
                      </span>
                    </td>
                    <td className="py-3 text-zinc-400">{a.model}</td>
                    <td className="py-3 text-zinc-400">{a.role}</td>
                    <td className="py-3 text-zinc-300 font-mono">{a.cpu}</td>
                    <td className="py-3 text-zinc-300 font-mono">{a.mem}</td>
                    <td className="py-3 text-zinc-300 font-mono">{a.gpu}</td>
                    <td className="py-3 text-right text-zinc-500 font-mono">{a.uptime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* REAL-TIME LOGS FEED */}
        <div className="lg:col-span-5 bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4 flex flex-col h-[510px]">
          <div className="flex items-center justify-between text-xs border-b border-zinc-800/80 pb-3 font-sans">
            <div className="flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-white stroke-[1.5]" />
              <span className="font-bold text-white uppercase tracking-wider">REAL-TIME LOGS</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-semibold">LIVE</span>
            </div>
            <div className="flex items-center space-x-2">
              <select 
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                className="bg-black/50 border border-zinc-800 text-zinc-300 text-[10px] rounded px-2 py-1 outline-none font-sans"
              >
                <option value="ALL">LEVEL: ALL</option>
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
                <option value="WARN">WARN</option>
                <option value="ERROR">ERROR</option>
              </select>
              <button 
                onClick={() => setIsLive(!isLive)}
                className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              >
                {isLive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 font-mono text-[10.5px] pr-1">
            {filteredLogs.map((log) => (
              <div key={log.id} className="flex items-start space-x-2 leading-relaxed border-b border-zinc-900/80 pb-1.5">
                <span className="text-zinc-600 shrink-0" suppressHydrationWarning>{log.time.substring(11, 23)}Z</span>
                <span className={`shrink-0 font-bold px-1 rounded text-[9px] ${
                  log.level === 'INFO' ? 'text-zinc-300 bg-zinc-800' :
                  log.level === 'DEBUG' ? 'text-zinc-500 bg-zinc-900' :
                  log.level === 'WARN' ? 'text-amber-400 bg-amber-500/10' :
                  'text-red-400 bg-red-500/10'
                }`}>
                  {log.level}
                </span>
                <span className="text-zinc-300 font-semibold shrink-0">{log.source}</span>
                <span className="text-zinc-400 break-all">{log.message}</span>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* SIMULATION & LICENSE GENERATOR */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* LICENSE GENERATOR */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-3 font-sans">
          <h2 className="text-sm font-bold text-white">Self-Hosted License Key Generator</h2>
          <p className="text-xs text-zinc-400">Generate cryptographically signed tokens for offline Hub quota verification.</p>
          <button 
            onClick={handleGenerateLicense}
            className="py-2 px-4 bg-white hover:bg-zinc-200 text-black text-xs font-semibold rounded-lg transition"
          >
            Generate License Token
          </button>
          {generatedLicense && (
            <div className="bg-[#08080A] border border-zinc-800 rounded-lg p-3 font-mono text-xs text-emerald-400 break-all">
              {generatedLicense}
            </div>
          )}
        </div>

        {/* 11TH AGENT SIMULATOR */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-3 font-sans">
          <h2 className="text-sm font-bold text-white flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Quota Enforcement Simulator (11th Agent)</span>
          </h2>
          <p className="text-xs text-zinc-400">Test how the Control Plane blocks initialization when exceeding 10 agents on Free Tier.</p>
          <button 
            onClick={handleSimulate11thAgent}
            disabled={simulating}
            className="py-2 px-4 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-semibold rounded-lg transition"
          >
            Simulate 11th Agent
          </button>

          {simResult && (
            <div className={`border rounded-lg p-3 font-mono text-xs space-y-1 ${simResult.status === 403 ? 'bg-red-500/5 border-red-500/30 text-red-400' : 'bg-emerald-500/5 border-emerald-500/30 text-emerald-400'}`}>
              <div className="font-bold">HTTP RESPONSE : {simResult.status} {simResult.status === 403 ? 'FORBIDDEN (QUOTA_EXCEEDED)' : 'OK'}</div>
              <pre className="bg-black/60 p-2 rounded text-[10px] overflow-x-auto text-slate-200">
                {JSON.stringify(simResult.data, null, 2)}
              </pre>
            </div>
          )}
        </div>

      </div>

    </div>
  );
}
"""

with open(page_path, 'w', encoding='utf-8') as f:
    f.write(dashboard_code)

print("✅ TOUTES LES ICÔNES DE CARTES KPI ONT ÉTÉ REMPLACÉES PAR DES SVG VECTORIELS PURS (Users, Zap, Cpu, TrendingUp) !")
