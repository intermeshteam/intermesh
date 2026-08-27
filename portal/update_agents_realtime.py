import os

page_path = os.path.expanduser('~/nexus/portal/src/app/(app)/agents/page.tsx')

agents_code = """'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Users, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  Power, 
  Search, 
  SlidersHorizontal 
} from 'lucide-react';

interface RealAgent {
  id: string;
  name: string;
  org_id: string;
  roles: string[];
  capabilities: string[];
  status: 'ONLINE' | 'OFFLINE';
  connectedAt: number;
  lastSeen: number;
  msgCount: number;
}

export default function AgentsDirectoryPage() {
  const [agents, setAgents] = useState<RealAgent[]>([]);
  const [hubConnected, setHubConnected] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('ALL');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stopped = false;
    let retryTimer: any;

    const connect = () => {
      if (stopped) return;
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;

      ws.onopen = () => {
        setHubConnected(true);
        ws.send(JSON.stringify({
          id: crypto.randomUUID(),
          version: 'nexus/v1',
          type: 'register',
          sender: `agents_dir_observer_${Math.random().toString(36).slice(2, 7)}`,
          content: { name: 'agents_dir_observer', roles: ['observer', 'admin'] }
        }));
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'telemetry_event') {
            const c = msg.content || {};

            if (c.event === 'snapshot') {
              const list = (c.agents || []).filter((a: any) => a.online !== false);
              const mapped: RealAgent[] = list.map((a: any) => ({
                id: a.agent_id ? a.agent_id.substring(0, 8) : 'active',
                name: a.name || a.qualified_name,
                org_id: a.org_id || 'default',
                roles: a.roles || ['worker'],
                capabilities: a.capabilities || [],
                status: 'ONLINE',
                connectedAt: a.connected_at || Date.now() / 1000,
                lastSeen: Date.now() / 1000,
                msgCount: a.msg_count || 0
              }));
              setAgents(mapped);
            }

            if (c.event === 'agent_connected' && c.agent) {
              const a = c.agent;
              setAgents((prev) => {
                const others = prev.filter((n) => n.name !== (a.name || a.qualified_name));
                return [
                  {
                    id: a.agent_id ? a.agent_id.substring(0, 8) : 'new',
                    name: a.name || a.qualified_name,
                    org_id: a.org_id || 'default',
                    roles: a.roles || ['worker'],
                    capabilities: a.capabilities || [],
                    status: 'ONLINE',
                    connectedAt: a.connected_at || Date.now() / 1000,
                    lastSeen: Date.now() / 1000,
                    msgCount: 0
                  },
                  ...others
                ];
              });
            }

            if (c.event === 'agent_disconnected') {
              const name = c.agent_name;
              setAgents((prev) => prev.map((a) => a.name === name ? { ...a, status: 'OFFLINE' } : a));
            }

            if (c.event === 'agent_activity') {
              setAgents((prev) => prev.map((a) => a.name === c.name ? { ...a, msgCount: c.msg_count || a.msgCount, lastSeen: Date.now() / 1000 } : a));
            }
          }
        } catch {}
      };

      ws.onclose = () => {
        setHubConnected(false);
        setAgents((prev) => prev.map((a) => ({ ...a, status: 'OFFLINE' })));
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
  }, []);

  const formatUptime = (connectedAt: number) => {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - connectedAt));
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hours}h ${remMins}m`;
  };

  const handleDisconnect = (agentName: string) => {
    setAgents((prev) => prev.map((a) => a.name === agentName ? { ...a, status: 'OFFLINE' } : a));
  };

  const filteredAgents = agents.filter((a) => {
    const matchesQuery = a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.capabilities.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesRole = selectedRole === 'ALL' || a.roles.includes(selectedRole);
    return matchesQuery && matchesRole;
  });

  const activeCount = agents.filter(a => a.status === 'ONLINE').length;

  return (
    <div className="space-y-8 font-sans text-slate-100 notranslate" translate="no">
      
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">Connected Agents Directory</h1>
            <span className={`inline-flex items-center space-x-1.5 text-[10px] font-mono px-2 py-0.5 rounded border ${
              hubConnected ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20'
            }`}>
              {hubConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              <span>{hubConnected ? 'HUB ONLINE' : 'HUB OFFLINE'}</span>
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1 font-sans">
            Live view of agents connected to your org hub ({activeCount} / 10 active slots used).
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button 
            onClick={() => window.location.reload()}
            className="py-2 px-3 bg-[#121215] hover:bg-zinc-800 border border-zinc-800 text-zinc-300 text-xs font-semibold rounded-lg flex items-center space-x-2 transition font-sans"
          >
            <RefreshCw className="w-3.5 h-3.5 text-zinc-400 stroke-[1.5]" />
            <span>Refresh List</span>
          </button>
        </div>
      </div>

      {/* FILTER BAR */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-[#121215] border border-zinc-800/80 rounded-xl p-4 font-sans">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search agent name or capability..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#08080A] border border-zinc-800 focus:border-zinc-600 rounded-lg pl-9 pr-3 py-2 text-xs text-white outline-none font-sans placeholder:text-zinc-600"
          />
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto justify-end font-mono text-xs">
          <span className="text-zinc-500 text-[11px]">ROLE:</span>
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="bg-[#08080A] border border-zinc-800 text-zinc-300 text-xs rounded-lg px-3 py-2 outline-none font-mono"
          >
            <option value="ALL">ALL ROLES</option>
            <option value="admin">ADMIN</option>
            <option value="worker">WORKER</option>
            <option value="inspector">INSPECTOR</option>
          </select>
        </div>
      </div>

      {/* AGENTS DIRECTORY TABLE */}
      <div className="bg-[#121215] border border-zinc-800/80 rounded-xl overflow-hidden font-sans">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#18181c] border-b border-zinc-800/80 text-zinc-400 uppercase text-[10px] font-mono tracking-wider">
            <tr>
              <th className="p-4 font-semibold">AGENT NAME</th>
              <th className="p-4 font-semibold">ROLE</th>
              <th className="p-4 font-semibold">CAPABILITIES</th>
              <th className="p-4 font-semibold">UPTIME</th>
              <th className="p-4 font-semibold">STATUS</th>
              <th className="p-4 text-right font-semibold">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
            {filteredAgents.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-12 text-center text-zinc-500 space-y-3">
                  <Users className="w-8 h-8 text-zinc-600 mx-auto stroke-[1]" />
                  <p className="font-sans text-xs">No connected agents matching your filter.</p>
                  <p className="font-mono text-[11px] text-zinc-600">
                    Run an agent in your terminal: <code className="text-zinc-400 bg-black px-1.5 py-0.5 rounded">python examples/agent_b.py</code>
                  </p>
                </td>
              </tr>
            ) : (
              filteredAgents.map((a, i) => (
                <tr key={i} className="hover:bg-zinc-800/30 transition">
                  <td className="p-4 font-semibold text-white flex items-center space-x-2.5">
                    <Users className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                    <span className="font-mono text-xs text-white">{a.name}</span>
                  </td>
                  <td className="p-4 font-mono text-xs">
                    <span className="px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/50 text-zinc-300 text-[11px]">
                      {a.roles.join(', ') || 'standard'}
                    </span>
                  </td>
                  <td className="p-4 text-zinc-400 font-mono text-xs">
                    {a.capabilities.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {a.capabilities.map((c, ci) => (
                          <span key={ci} className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 text-[10px]">
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-zinc-600">none</span>
                    )}
                  </td>
                  <td className="p-4 text-zinc-400 font-mono text-xs">
                    {formatUptime(a.connectedAt)}
                  </td>
                  <td className="p-4 font-mono text-xs">
                    {a.status === 'ONLINE' ? (
                      <span className="inline-flex items-center space-x-1.5 text-emerald-400 font-semibold text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span>ONLINE</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1.5 text-red-400 font-semibold text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                        <span>OFFLINE</span>
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    <button 
                      onClick={() => handleDisconnect(a.name)}
                      className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded transition" 
                      title="Disconnect Agent"
                    >
                      <Power className="w-4 h-4 stroke-[1.5]" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
"""

with open(page_path, 'w', encoding='utf-8') as f:
    f.write(agents_code)

print("✅ PAGE AGENTS MISE À JOUR SANS AUCUNE ERREUR !")
