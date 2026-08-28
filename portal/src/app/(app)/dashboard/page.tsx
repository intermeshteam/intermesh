'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
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
} from 'lucide-react';

interface RealAgent {
  id: string;
  name: string;
  status: string;
  roles: string[];
  capabilities: string[];
  uptime: string;
  hardware: { cpu: string; mem: string; gpu: string };
}

interface LogEntry {
  id: number;
  time: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR';
  source: string;
  message: string;
}

function nowTs() {
  return new Date().toISOString();
}

// Génère des fausses stats matérielles stables basées sur le nom de l'agent pour le tableau
function generateHardwareStats(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const seed = Math.abs(hash);
  return {
    cpu: (10 + (seed % 30) + (seed % 10) / 10).toFixed(1),
    mem: (20 + (seed % 40) + (seed % 10) / 10).toFixed(1),
    gpu: (seed % 2 === 0 ? (30 + (seed % 50)).toFixed(1) : '0.0'),
  };
}

export default function MissionControlDashboard() {
  const [copiedKey, setCopiedKey] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [generatedLicense, setGeneratedLicense] = useState<string>('');

  // --- REAL-TIME STATE ---
  const [isLive, setIsLive] = useState(true);
  const [logFilter, setLogFilter] = useState<string>('ALL');
  const [hubConnected, setHubConnected] = useState(false);
  const [agents, setAgents] = useState<RealAgent[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [taskCount, setTaskCount] = useState(0);
  const [msgCount, setMsgCount] = useState(0);
  
  const logIdRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);

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

  const pushLog = useCallback((level: LogEntry['level'], source: string, message: string) => {
    logIdRef.current += 1;
    const newLog: LogEntry = {
      id: logIdRef.current,
      time: nowTs(),
      level,
      source,
      message,
    };
    setLogs((prev) => [newLog, ...prev].slice(0, 50));
  }, []);

  // --- WEBSOCKET CONNECTION TO HUB ---
  useEffect(() => {
    let stopped = false;
    let retryTimer: any;

    const connect = () => {
      if (stopped) return;
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;

      ws.onopen = () => {
        setHubConnected(true);
        pushLog('INFO', 'System', 'Control Plane connected to InterMesh Hub (ws://localhost:8765)');
        ws.send(JSON.stringify({
          id: crypto.randomUUID(),
          version: 'intermesh/v1',
          type: 'register',
          sender: `dashboard_main_${Math.random().toString(36).slice(2, 7)}`,
          content: { name: 'dashboard_main', roles: ['observer', 'admin'] },
        }));
      };

      ws.onmessage = (ev) => {
        if (!isLive) return; // Si en pause, on ignore l'affichage
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'telemetry_event') {
            const c = msg.content || {};
            setMsgCount(m => m + 1);

            if (c.event === 'snapshot') {
              const list = (c.agents || []).filter((a: any) => a.online !== false);
              const mapped = list.map((a: any) => ({
                id: a.agent_id ? a.agent_id.substring(0, 8) : 'unknown',
                name: a.name || a.qualified_name,
                status: 'ONLINE',
                roles: a.roles || ['worker'],
                capabilities: a.capabilities || [],
                uptime: '0m',
                hardware: generateHardwareStats(a.name || 'agent')
              }));
              setAgents(mapped);
              pushLog('INFO', 'Registry', `Snapshot loaded: ${list.length} active agent(s)`);
            }

            if (c.event === 'agent_connected' && c.agent) {
              const a = c.agent;
              setAgents((prev) => {
                const others = prev.filter((n) => n.name !== a.name);
                return [
                  {
                    id: a.agent_id ? a.agent_id.substring(0, 8) : 'new',
                    name: a.name || a.qualified_name,
                    status: 'ONLINE',
                    roles: a.roles || ['worker'],
                    capabilities: a.capabilities || [],
                    uptime: '0m',
                    hardware: generateHardwareStats(a.name || 'agent')
                  },
                  ...others
                ];
              });
              pushLog('INFO', 'AgentManager', `Agent connected: ${a.name || a.qualified_name}`);
            }

            if (c.event === 'agent_disconnected') {
              const name = c.agent_name;
              setAgents((prev) => prev.filter((n) => n.name !== name));
              pushLog('WARN', 'AgentManager', `Agent disconnected: ${name}`);
            }

            if (c.event === 'task_submitted') {
              setTaskCount(t => t + 1);
              pushLog('DEBUG', 'Orchestrator', `Task '${c.title}' delegated to ${c.assignee}`);
            }

            if (c.event === 'task_completed') {
              pushLog('INFO', 'Worker', `Task ${c.task_id.substring(0,8)} completed successfully`);
            }
            
            if (c.event === 'message_routed') {
               // pushLog('DEBUG', 'Router', \`Message routed: \${c.sender} -> \${c.to}\`);
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        setHubConnected(false);
        setAgents([]);
        pushLog('ERROR', 'System', 'Hub connection lost. Retrying...');
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
  }, [pushLog, isLive]);

  const filteredLogs = logs.filter(log => logFilter === 'ALL' || log.level === logFilter);

  // Update dynamic uptime locally
  useEffect(() => {
    const iv = setInterval(() => {
      setAgents(prev => prev.map(a => {
        let mins = parseInt(a.uptime) || 0;
        return { ...a, uptime: `${mins + 1}m` };
      }));
    }, 60000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="space-y-8 font-sans text-slate-100 notranslate" translate="no">
      
      {/* HEADER */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-sans flex items-center space-x-2">
            <span className="text-[#00D4FF]">A1</span>
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
        
        {/* CARD 1 : TOTAL AGENTS (REAL-TIME) */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">TOTAL AGENTS</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Users className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white font-mono tracking-tight">{agents.length}</span>
            <span className={`text-[11px] font-mono font-medium ${hubConnected ? 'text-emerald-400' : 'text-red-400'}`}>
              {hubConnected ? 'LIVE SYNC' : 'OFFLINE'}
            </span>
          </div>
          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>10</span><span>5</span><span>0</span>
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
          </div>
        </div>

        {/* CARD 2 : ACTIVE JOBS (REAL-TIME) */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">ACTIVE JOBS</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Zap className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-[#00D4FF] font-mono tracking-tight">{taskCount}</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">REAL-TIME</span>
          </div>
          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>High</span><span>Med</span><span>Low</span>
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
          </div>
        </div>

        {/* CARD 3 : SYSTEM HEALTH */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">SYSTEM HEALTH</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <Cpu className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white font-mono tracking-tight">{hubConnected ? '100%' : '0%'}</span>
            <span className={`text-[11px] font-mono font-medium ${hubConnected ? 'text-emerald-400' : 'text-red-400'}`}>
              {hubConnected ? 'STABLE' : 'DOWN'}
            </span>
          </div>
          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>100%</span><span>50%</span><span>0%</span>
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
          </div>
        </div>

        {/* CARD 4 : MESSAGES / SEC */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden">
          <div className="flex justify-between items-center text-[11px] text-zinc-400 font-mono">
            <span className="font-semibold tracking-wider">MESSAGES / SEC</span>
            <div className="w-5 h-5 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center text-zinc-400">
              <TrendingUp className="w-3 h-3 stroke-[1.5]" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-[#00D4FF] font-mono tracking-tight">{msgCount}</span>
            <span className="text-[11px] text-emerald-400 font-mono font-medium">ROUTED</span>
          </div>
          <div className="mt-3 relative">
            <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
              <span>High</span><span>Med</span><span>Low</span>
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
          </div>
        </div>

      </div>

      {/* SPLIT CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* LEFT PANEL : CONNECTED AGENTS TABLE (REAL-TIME) */}
        <div className="lg:col-span-7 bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between text-xs border-b border-zinc-800/80 pb-3 font-sans">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-white uppercase tracking-wider font-mono">CONNECTED AGENTS</span>
              <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px] font-mono">{agents.length} TOTAL</span>
            </div>
            <div className="flex items-center space-x-3 text-zinc-400 text-[11px] font-mono">
              <span className="cursor-pointer hover:text-white flex items-center space-x-1">
                <SlidersHorizontal className="w-3 h-3" />
                <span>FILTER ▾</span>
              </span>
            </div>
          </div>

          <div className="overflow-x-auto min-h-[300px]">
            {agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-16 text-zinc-500 space-y-2">
                <Users className="w-8 h-8 stroke-[1]" />
                <p>Waiting for real agents to connect...</p>
                <p className="text-[10px] font-mono mt-2">Run <code className="text-zinc-400 bg-zinc-900 px-1 rounded">python examples/agent_b.py</code></p>
              </div>
            ) : (
              <table className="w-full text-left font-sans text-xs">
                <thead className="text-[10px] text-zinc-500 border-b border-zinc-800 uppercase font-semibold">
                  <tr>
                    <th className="pb-3">ID</th>
                    <th className="pb-3">NAME</th>
                    <th className="pb-3">STATUS</th>
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
                      <td className="py-3 font-semibold text-white font-sans">{a.name.split('/')[1] || a.name}</td>
                      <td className="py-3">
                        <span className="inline-flex items-center space-x-1.5 text-emerald-400 text-[10px] font-semibold">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                          <span>ONLINE</span>
                        </span>
                      </td>
                      <td className="py-3 text-zinc-400">{a.roles[0]}</td>
                      <td className="py-3 text-zinc-300 font-mono">{a.hardware.cpu}</td>
                      <td className="py-3 text-zinc-300 font-mono">{a.hardware.mem}</td>
                      <td className="py-3 text-zinc-300 font-mono">{a.hardware.gpu}</td>
                      <td className="py-3 text-right text-zinc-500 font-mono">{a.uptime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* RIGHT PANEL : REAL-TIME LOGS FEED */}
        <div className="lg:col-span-5 bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-4 flex flex-col h-[510px]">
          <div className="flex items-center justify-between text-xs border-b border-zinc-800/80 pb-3 font-sans">
            <div className="flex items-center space-x-2 font-mono">
              <Terminal className="w-4 h-4 text-white stroke-[1.5]" />
              <span className="font-bold text-white uppercase tracking-wider">REAL-TIME LOGS</span>
              <span className={`px-2 py-0.5 rounded border text-[10px] font-semibold ${hubConnected ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
                {hubConnected ? 'LIVE' : 'OFFLINE'}
              </span>
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
                className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
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

      {/* BOTTOM SECTION : CONTROL PLANE TOOLS */}
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
            <div className={`border rounded-lg p-3 font-mono text-xs space-y-1 bg-[#08080A] ${simResult.status === 403 ? 'border-red-900/60' : 'border-zinc-800'}`}>
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
