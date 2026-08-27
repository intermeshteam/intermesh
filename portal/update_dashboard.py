import os

page_path = os.path.expanduser('~/nexus/portal/src/app/(app)/dashboard/page.tsx')

dashboard_code = """'use client';

import React, { useState, useEffect } from 'react';
import { 
  Bot, 
  Cpu, 
  Zap, 
  Activity, 
  Terminal, 
  Filter, 
  Pause, 
  Play, 
  Trash2, 
  AlertTriangle, 
  ChevronLeft, 
  ChevronRight,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2
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
    { id: 10, time: '2026-08-26T15:42:13.321Z', level: 'INFO', source: 'AutoScaler', message: 'Scaled up: added 4 GPU nodes (us-east-1c)' },
    { id: 11, time: '2026-08-26T15:42:12.876Z', level: 'DEBUG', source: 'CacheManager', message: 'Cache hit ratio: 92.7%' },
    { id: 12, time: '2026-08-26T15:42:12.543Z', level: 'INFO', source: 'AgentHeartbeat', message: 'Heartbeat received from DataMiner-Delta (02)' },
    { id: 13, time: '2026-08-26T15:42:12.210Z', level: 'INFO', source: 'JobScheduler', message: 'Scheduled batch of 32 requests' },
    { id: 14, time: '2026-08-26T15:42:11.987Z', level: 'WARN', source: 'RateLimiter', message: 'Rate limit approaching for key org_12345' },
    { id: 15, time: '2026-08-26T15:42:11.654Z', level: 'DEBUG', source: 'MemoryManager', message: 'Memory usage: 42.3%' },
    { id: 16, time: '2026-08-26T15:42:11.321Z', level: 'INFO', source: 'SecurityScanner', message: 'Scan completed: 0 vulnerabilities' },
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
    { id: '09', name: 'LogWatcher-Edge', status: 'ONLINE', model: 'gpt-4.1-mini', role: 'monitor', cpu: 4.3, mem: 9.7, gpu: 0.0, uptime: '6h 22m' },
    { id: '10', name: 'BatchOrchestrator', status: 'ONLINE', model: 'claude-3.7', role: 'orchestrator', cpu: 11.6, mem: 31.5, gpu: 39.2, uptime: '2d 02h' },
    { id: '11', name: 'ReportGen-View', status: 'ONLINE', model: 'gpt-4.1-mini', role: 'reporter', cpu: 2.9, mem: 8.3, gpu: 0.0, uptime: '3h 14m' },
    { id: '12', name: 'SearchIndexer-AI', status: 'ONLINE', model: 'gpt-4.1', role: 'indexer', cpu: 13.1, mem: 37.6, gpu: 14.6, uptime: '1d 09h' },
    { id: '13', name: 'CacheOptimizer', status: 'ONLINE', model: 'claude-3.7', role: 'optimizer', cpu: 6.8, mem: 19.4, gpu: 9.3, uptime: '15h 33m' },
    { id: '14', name: 'DataSynth-Core', status: 'ONLINE', model: 'gpt-4.1', role: 'synthetic', cpu: 17.3, mem: 48.1, gpu: 71.4, uptime: '2d 11h' },
    { id: '15', name: 'PromptEngineer', status: 'ONLINE', model: 'claude-3.7', role: 'prompt-eng', cpu: 5.7, mem: 14.2, gpu: 5.1, uptime: '8h 47m' },
    { id: '16', name: 'EdgeDeploy-Agent', status: 'ONLINE', model: 'gpt-4.1-mini', role: 'deployer', cpu: 10.2, mem: 27.3, gpu: 31.8, uptime: '1d 22h' },
  ];

  // Simulation de flux de logs en direct
  useEffect(() => {
    if (!isLive) return;
    const interval = setInterval(() => {
      const sources = ['AgentManager', 'JobScheduler', 'GPUAllocator', 'MetricsCollector', 'AgentHeartbeat', 'Tokenizer', 'CacheManager', 'SecurityScanner'];
      const levels: ('INFO' | 'DEBUG' | 'WARN')[] = ['INFO', 'DEBUG', 'INFO', 'INFO', 'WARN'];
      const randomSource = sources[Math.floor(Math.random() * sources.length)];
      const randomLevel = levels[Math.floor(Math.random() * levels.length)];
      const now = new Date().toISOString();

      const newLog: LogEntry = {
        id: Date.now(),
        time: now,
        level: randomLevel,
        source: randomSource,
        message: `Processed telemetry pulse from cluster node_${Math.floor(Math.random() * 8) + 1}`
      };

      setLogs(prev => [newLog, ...prev.slice(0, 30)]);
    }, 2500);

    return () => clearInterval(interval);
  }, [isLive]);

  const filteredLogs = logs.filter(log => logFilter === 'ALL' || log.level === logFilter);

  return (
    <div className="space-y-6 font-sans text-slate-100 selection:bg-white selection:text-black">
      
      {/* HEADER TITLE */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-mono flex items-center space-x-3">
            <span className="text-[#00D4FF]">A1</span>
            <span className="text-zinc-600">/</span>
            <span>MISSION CONTROL — AI INFRASTRUCTURE</span>
          </h1>
        </div>
        <div className="flex items-center space-x-4 text-xs font-mono">
          <span className="text-zinc-500">ENVIRONMENT: <span className="text-cyan-400 font-semibold">PRODUCTION</span></span>
          <span className="text-zinc-500">REGION: <span className="text-slate-200 font-semibold">US-EAST-1</span></span>
        </div>
      </div>

      {/* TOP METRICS GRID (4 CARDS WITH SPARK LINES) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* CARD 1 : TOTAL AGENTS */}
        <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-mono">
            <span>TOTAL AGENTS</span>
            <Bot className="w-3.5 h-3.5 text-zinc-500" />
          </div>
          <div className="flex items-baseline space-x-3 mt-2">
            <span className="text-3xl font-extrabold text-white font-mono">512</span>
            <span className="text-xs text-emerald-400 font-mono font-medium">+12.45% vs 24h</span>
          </div>
          {/* Sparkline SVG */}
          <div className="h-10 mt-2">
            <svg class="w-full h-full text-cyan-400" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 25 L15 20 L30 22 L45 15 L60 18 L75 8 L90 12 L100 5" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>
        </div>

        {/* CARD 2 : ACTIVE JOBS */}
        <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-mono">
            <span>ACTIVE JOBS</span>
            <Zap className="w-3.5 h-3.5 text-zinc-500" />
          </div>
          <div className="flex items-baseline space-x-3 mt-2">
            <span className="text-3xl font-extrabold text-cyan-400 font-mono">1,237</span>
            <span className="text-xs text-emerald-400 font-mono font-medium">+18.72% vs 24h</span>
          </div>
          <div className="h-10 mt-2">
            <svg class="w-full h-full text-cyan-400" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 20 L15 18 L30 25 L45 12 L60 10 L75 14 L90 5 L100 2" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>
        </div>

        {/* CARD 3 : GPU UTILIZATION */}
        <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-mono">
            <span>GPU UTILIZATION</span>
            <Cpu className="w-3.5 h-3.5 text-zinc-500" />
          </div>
          <div className="flex items-baseline space-x-3 mt-2">
            <span className="text-3xl font-extrabold text-white font-mono">78.6%</span>
            <span className="text-xs text-emerald-400 font-mono font-medium">+5.34% vs 24h</span>
          </div>
          <div className="h-10 mt-2">
            <svg class="w-full h-full text-cyan-400" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 15 L15 12 L30 18 L45 10 L60 22 L75 12 L90 15 L100 8" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>
        </div>

        {/* CARD 4 : TOKENS / SEC */}
        <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs text-zinc-400 font-mono">
            <span>TOKENS / SEC</span>
            <Activity className="w-3.5 h-3.5 text-zinc-500" />
          </div>
          <div className="flex items-baseline space-x-3 mt-2">
            <span className="text-3xl font-extrabold text-cyan-400 font-mono">2.84M</span>
            <span className="text-xs text-emerald-400 font-mono font-medium">+22.18% vs 24h</span>
          </div>
          <div className="h-10 mt-2">
            <svg class="w-full h-full text-cyan-400" viewBox="0 0 100 30" preserveAspectRatio="none">
              <path d="M0 22 L15 15 L30 19 L45 8 L60 14 L75 6 L90 10 L100 3" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>
        </div>

      </div>

      {/* MAIN CONTENT SPLIT : LEFT TABLE (CONNECTED AGENTS) & RIGHT REAL-TIME LOGS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* LEFT PANEL : CONNECTED AGENTS TABLE (7 COLS) */}
        <div className="lg:col-span-7 bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between text-xs font-mono border-b border-zinc-800/80 pb-3">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-white uppercase tracking-wider">CONNECTED AGENTS</span>
              <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px]">512 TOTAL</span>
            </div>
            <div className="flex items-center space-x-3 text-zinc-400">
              <span className="cursor-pointer hover:text-white">FILTER ▾</span>
              <span className="cursor-pointer hover:text-white">STATUS ▾</span>
            </div>
          </div>

          {/* HIGH DENSITY AGENTS TABLE */}
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="text-[10px] text-zinc-500 border-b border-zinc-800 uppercase">
                <tr>
                  <th className="pb-2.5 font-medium">ID</th>
                  <th className="pb-2.5 font-medium">NAME</th>
                  <th className="pb-2.5 font-medium">STATUS</th>
                  <th className="pb-2.5 font-medium">MODEL</th>
                  <th className="pb-2.5 font-medium">ROLE</th>
                  <th className="pb-2.5 font-medium">CPU%</th>
                  <th className="pb-2.5 font-medium">MEM%</th>
                  <th className="pb-2.5 font-medium">GPU%</th>
                  <th className="pb-2.5 font-medium text-right">UPTIME</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40 text-zinc-300 text-[11px]">
                {agents.map((a) => (
                  <tr key={a.id} className="hover:bg-zinc-800/30 transition">
                    <td className="py-2.5 text-zinc-500">{a.id}</td>
                    <td className="py-2.5 font-medium text-cyan-400">{a.name}</td>
                    <td className="py-2.5">
                      <span className="inline-flex items-center space-x-1 text-emerald-400 text-[10px] font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span>ONLINE</span>
                      </span>
                    </td>
                    <td className="py-2.5 text-zinc-400">{a.model}</td>
                    <td className="py-2.5 text-zinc-400">{a.role}</td>
                    <td className="py-2.5 text-zinc-300">{a.cpu}</td>
                    <td className="py-2.5 text-zinc-300">{a.mem}</td>
                    <td className="py-2.5 text-zinc-300">{a.gpu}</td>
                    <td className="py-2.5 text-right text-zinc-500">{a.uptime}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* PAGINATION FOOTER */}
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 pt-2 border-t border-zinc-800/80">
            <span>Showing 1-16 of 512 agents</span>
            <div className="flex items-center space-x-1">
              <button className="p-1 rounded hover:bg-zinc-800 text-zinc-400"><ChevronLeft className="w-3.5 h-3.5" /></button>
              <span className="px-2 py-0.5 rounded bg-zinc-800 text-white font-bold">1</span>
              <span className="px-2 py-0.5 rounded hover:bg-zinc-800 cursor-pointer">2</span>
              <span className="px-2 py-0.5 rounded hover:bg-zinc-800 cursor-pointer">3</span>
              <span className="px-1 text-zinc-600">...</span>
              <span className="px-2 py-0.5 rounded hover:bg-zinc-800 cursor-pointer">32</span>
              <button className="p-1 rounded hover:bg-zinc-800 text-zinc-400"><ChevronRight className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL : REAL-TIME LOGS STREAM (5 COLS) */}
        <div className="lg:col-span-5 bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-5 space-y-4 flex flex-col h-[540px]">
          <div className="flex items-center justify-between text-xs font-mono border-b border-zinc-800/80 pb-3">
            <div className="flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
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
                title={isLive ? 'Pause Stream' : 'Resume Stream'}
              >
                {isLive ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* LOGS SCROLLABLE FEED */}
          <div className="flex-1 overflow-y-auto space-y-2 font-mono text-[10.5px] pr-2">
            {filteredLogs.map((log) => (
              <div key={log.id} className="flex items-start space-x-2 leading-relaxed border-b border-zinc-900/60 pb-1.5">
                <span className="text-zinc-600 shrink-0">{log.time.substring(0, 23)}Z</span>
                <span className={`shrink-0 font-bold px-1 rounded text-[9px] ${
                  log.level === 'INFO' ? 'bg-cyan-500/10 text-cyan-400' :
                  log.level === 'DEBUG' ? 'bg-zinc-800 text-zinc-400' :
                  log.level === 'WARN' ? 'bg-amber-500/10 text-amber-400' :
                  'bg-red-500/10 text-red-400'
                }`}>
                  {log.level}
                </span>
                <span className="text-slate-300 font-semibold shrink-0">{log.source}</span>
                <span className="text-zinc-400 break-all">{log.message}</span>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* BOTTOM STATUS BAR (SYSTEM HEALTH, ALERTS, PENDING JOBS) */}
      <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs items-center">
        <div className="flex items-center space-x-2">
          <span className="text-zinc-500">SYSTEM STATUS:</span>
          <span className="flex items-center space-x-1.5 text-emerald-400 font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>OPERATIONAL</span>
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-zinc-500">CLUSTER HEALTH:</span>
          <span className="text-white font-bold">98.7%</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-zinc-500">ACTIVE ALERTS:</span>
          <span className="text-amber-400 font-bold">3</span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-zinc-500">PENDING JOBS:</span>
            <span className="text-cyan-400 font-bold">47</span>
          </div>
          <a href="#" className="text-[#00D4FF] hover:underline text-[11px] flex items-center space-x-1">
            <span>VIEW ALL ALERTS</span>
            <ArrowUpRight className="w-3 h-3" />
          </a>
        </div>
      </div>

    </div>
  );
}
"""

with open(page_path, 'w', encoding='utf-8') as f:
    f.write(dashboard_code)

print("✅ LA PAGE MISSION CONTROL DE LA MAQUETTE A ÉTÉ APPLIQUÉE AVEC SUCCÈS !")
