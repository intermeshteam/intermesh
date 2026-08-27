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
  KeyRound,
  RefreshCw,
  SlidersHorizontal,
  Users2
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

      {/* KPI METRICS GRID */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* CARD 1 : TOTAL AGENTS */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">TOTAL AGENTS</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Users className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white font-mono tracking-tight">512</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">+12.45% vs 24h</span>
          </div>

          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>600</span>
              <span>400</span>
              <span>200</span>
              <span>0</span>
            </div>
            <div className="h-12 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 200 40" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="gradTotalAgents" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#00D4FF" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <path d="M0 32 Q30 28, 60 22 T120 16 T180 8 L200 5 L200 40 L0 40 Z" fill="url(#gradTotalAgents)" />
                <path d="M0 32 Q30 28, 60 22 T120 16 T180 8 L200 5" fill="none" stroke="#00D4FF" strokeWidth="1.75" />
                <circle cx="200" cy="5" r="3" fill="#00D4FF" />
              </svg>
            </div>
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mt-1">
              <span>-24h</span>
              <span>-18h</span>
              <span>-12h</span>
              <span>-6h</span>
              <span>Now</span>
            </div>
          </div>
        </div>

        {/* CARD 2 : ACTIVE JOBS */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">ACTIVE JOBS</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Zap className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-[#00D4FF] font-mono tracking-tight">1,237</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">+18.72% vs 24h</span>
          </div>

          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>2.0K</span>
              <span>1.5K</span>
              <span>1.0K</span>
              <span>0</span>
            </div>
            <div className="h-12 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 200 40" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="gradActiveJobs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#00D4FF" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <path d="M0 28 Q40 25, 80 18 T140 10 T180 6 L200 3 L200 40 L0 40 Z" fill="url(#gradActiveJobs)" />
                <path d="M0 28 Q40 25, 80 18 T140 10 T180 6 L200 3" fill="none" stroke="#00D4FF" strokeWidth="1.75" />
                <circle cx="200" cy="3" r="3" fill="#00D4FF" />
              </svg>
            </div>
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mt-1">
              <span>-24h</span>
              <span>-18h</span>
              <span>-12h</span>
              <span>-6h</span>
              <span>Now</span>
            </div>
          </div>
        </div>

        {/* CARD 3 : GPU UTILIZATION */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">GPU UTILIZATION</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Cpu className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white font-mono tracking-tight">78.6%</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">+5.34% vs 24h</span>
          </div>

          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>100%</span>
              <span>75%</span>
              <span>50%</span>
              <span>0%</span>
            </div>
            <div className="h-12 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 200 40" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="gradGpuUtil" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#00D4FF" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <path d="M0 22 Q50 18, 100 24 T160 12 L200 10 L200 40 L0 40 Z" fill="url(#gradGpuUtil)" />
                <path d="M0 22 Q50 18, 100 24 T160 12 L200 10" fill="none" stroke="#00D4FF" strokeWidth="1.75" />
                <circle cx="200" cy="10" r="3" fill="#00D4FF" />
              </svg>
            </div>
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mt-1">
              <span>-24h</span>
              <span>-18h</span>
              <span>-12h</span>
              <span>-6h</span>
              <span>Now</span>
            </div>
          </div>
        </div>

        {/* CARD 4 : TOKENS / SEC */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">TOKENS / SEC</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <TrendingUp className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-[#00D4FF] font-mono tracking-tight">2.84M</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">+22.18% vs 24h</span>
          </div>

          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>4.0M</span>
              <span>3.0M</span>
              <span>2.0M</span>
              <span>0</span>
            </div>
            <div className="h-12 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 200 40" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="gradTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00D4FF" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#00D4FF" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <path d="M0 30 Q40 22, 90 15 T150 8 L200 4 L200 40 L0 40 Z" fill="url(#gradTokens)" />
                <path d="M0 30 Q40 22, 90 15 T150 8 L200 4" fill="none" stroke="#00D4FF" strokeWidth="1.75" />
                <circle cx="200" cy="4" r="3" fill="#00D4FF" />
              </svg>
            </div>
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mt-1">
              <span>-24h</span>
              <span>-18h</span>
              <span>-12h</span>
              <span>-6h</span>
              <span>Now</span>
            </div>
          </div>
        </div>

      </div>

      {/* SPLIT CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* CONNECTED AGENTS TABLE */}
        <div className="lg:col-span-7 bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between text-xs border-b border-zinc-800/80 pb-3 font-sans">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-white uppercase tracking-wider font-mono">CONNECTED AGENTS</span>
              <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px] font-mono">512 TOTAL</span>
            </div>
            <div className="flex items-center space-x-3 text-zinc-400 text-[11px] font-mono">
              <span className="cursor-pointer hover:text-white flex items-center space-x-1">
                <SlidersHorizontal className="w-3 h-3" />
                <span>FILTER ▾</span>
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
                    <td className="py-3 font-semibold text-white font-sans">{a.name}</td>
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
            <div className="flex items-center space-x-2 font-mono">
              <Terminal className="w-4 h-4 text-white stroke-[1.5]" />
              <span className="font-bold text-white uppercase tracking-wider">REAL-TIME LOGS</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-semibold">LIVE</span>
            </div>
            <div className="flex items-center space-x-2">
              <select 
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                className="bg-black/50 border border-zinc-800 text-zinc-300 text-[10px] rounded px-2 py-1 outline-none font-mono"
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

      {/* BOTTOM SECTION : DEVELOPER CONTROL PLANE TOOLS (VERCEL / STRIPE STYLE) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-sans">
        
        {/* LICENSE GENERATOR CARD */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <KeyRound className="w-4 h-4 text-zinc-300 stroke-[1.5]" />
                <h2 className="text-sm font-bold text-white">Self-Hosted License Generator</h2>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Generate cryptographically signed Ed25519 tokens for offline Hub quota verification.
              </p>
            </div>
            <button 
              onClick={handleGenerateLicense}
              className="px-3.5 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/80 text-zinc-200 text-xs font-semibold rounded-lg transition shrink-0 flex items-center space-x-2"
            >
              <RefreshCw className="w-3.5 h-3.5 text-zinc-400 stroke-[1.5]" />
              <span>Generate License Token</span>
            </button>
          </div>

          {generatedLicense && (
            <div className="bg-[#08080A] border border-zinc-800 rounded-lg p-3 font-mono text-xs text-zinc-200 break-all">
              <div className="text-[10px] text-zinc-500 uppercase mb-1 tracking-wider">Ed25519 Signed Token</div>
              <div className="text-zinc-100 select-all">{generatedLicense}</div>
            </div>
          )}
        </div>

        {/* 11TH AGENT SIMULATOR CARD */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-zinc-300 stroke-[1.5]" />
                <h2 className="text-sm font-bold text-white">Quota Enforcement Simulator</h2>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Test how the Control Plane blocks registration when exceeding 10 agents on Free Tier.
              </p>
            </div>
            <button 
              onClick={handleSimulate11thAgent}
              disabled={simulating}
              className="px-3.5 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/80 text-zinc-200 text-xs font-semibold rounded-lg transition shrink-0 flex items-center space-x-2"
            >
              {simulating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Users className="w-3.5 h-3.5 text-zinc-400 stroke-[1.5]" />}
              <span>Simulate 11th Agent</span>
            </button>
          </div>

          {simResult && (
            <div className={`border rounded-lg p-3 font-mono text-xs space-y-2 bg-[#08080A] ${simResult.status === 403 ? 'border-red-900/60' : 'border-zinc-800'}`}>
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-zinc-300">HTTP Response</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${simResult.status === 403 ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-400'}`}>
                  {simResult.status} {simResult.status === 403 ? 'FORBIDDEN (QUOTA_EXCEEDED)' : 'OK'}
                </span>
              </div>
              <pre className="bg-black/50 p-2.5 rounded text-[11px] overflow-x-auto text-zinc-300 border border-zinc-900">
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

print("✅ LE BAS DE PAGE A ÉTÉ RECARROSSÉ AU STYLE VERCEL / STRIPE !")
