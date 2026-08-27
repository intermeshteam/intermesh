import os
import shutil

base_dir = os.path.expanduser('~/nexus/portal/src/app')

# 1. Nettoyer les anciennes routes conflictuelles
for folder in ['dashboard', 'agents', 'keys', 'security', 'billing']:
    target = os.path.join(base_dir, folder)
    if os.path.exists(target):
        shutil.rmtree(target)

# 2. Créer le groupe de routes (dashboard)
dash_group_dir = os.path.join(base_dir, '(dashboard)')
os.makedirs(dash_group_dir, exist_ok=True)

# -----------------------------------------------------------------------------
# LAYOUT PRINCIPAL DU DASHBOARD (Sidebar Stripe-Style + Topbar)
# -----------------------------------------------------------------------------
layout_code = """import React from 'react';
import Link from 'next/link';
import { 
  LayoutDashboard, Bot, Key, ShieldCheck, CreditCard, Settings, 
  Search, Bell, HelpCircle, ChevronDown, Activity, BookOpen
} from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#09090b] text-white font-sans flex selection:bg-white selection:text-black">
      
      {/* SIDEBAR STRIPE / VERCEL STYLE */}
      <aside className="w-[240px] border-r border-white/10 bg-[#09090b] flex flex-col justify-between p-4 hidden md:flex fixed h-full z-20 shrink-0">
        <div className="space-y-6">
          
          {/* LOGO */}
          <Link href="/" className="flex items-center space-x-2.5 px-2 py-1 hover:opacity-80 transition">
            <div className="w-6 h-6 rounded bg-white text-black font-extrabold flex items-center justify-center text-xs font-mono">
              ⬡
            </div>
            <span className="font-extrabold tracking-widest text-white text-sm">N E X U S</span>
          </Link>

          {/* ORG SELECTOR */}
          <div className="bg-[#121214] border border-white/10 rounded-lg p-2.5 flex items-center justify-between text-xs cursor-pointer hover:border-slate-700 transition">
            <div className="flex items-center space-x-2">
              <div className="w-5 h-5 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-[10px] font-mono">A</div>
              <span className="font-medium text-slate-200">Acme Corp</span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          </div>

          {/* NAVIGATION */}
          <nav className="space-y-1 text-xs font-medium">
            <div className="text-[10px] font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2">Core</div>
            
            <Link href="/dashboard" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-300 hover:text-white hover:bg-white/5 transition">
              <LayoutDashboard className="w-4 h-4 text-slate-400" />
              <span>Overview & Quotas</span>
            </Link>
            
            <Link href="/agents" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-300 hover:text-white hover:bg-white/5 transition">
              <Bot className="w-4 h-4 text-slate-400" />
              <span>Agents Directory (4/10)</span>
            </Link>

            <div className="text-[10px] font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2 pt-4">Developers</div>
            
            <Link href="/keys" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-300 hover:text-white hover:bg-white/5 transition">
              <Key className="w-4 h-4 text-slate-400" />
              <span>API Keys & Licenses</span>
            </Link>
            
            <Link href="/security" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-300 hover:text-white hover:bg-white/5 transition">
              <ShieldCheck className="w-4 h-4 text-slate-400" />
              <span>Audit Log & RBAC</span>
            </Link>

            <div className="text-[10px] font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2 pt-4">Organization</div>
            
            <Link href="/billing" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-300 hover:text-white hover:bg-white/5 transition">
              <CreditCard className="w-4 h-4 text-slate-400" />
              <span>Billing & Plans</span>
            </Link>
            
            <a href="#" className="flex items-center space-x-3 px-3 py-2 rounded-md text-slate-600 cursor-not-allowed">
              <Settings className="w-4 h-4 text-slate-600" />
              <span>Settings</span>
            </a>
          </nav>
        </div>

        {/* FOOTER */}
        <div className="space-y-3 pt-4 border-t border-white/10 text-xs text-slate-500 font-mono">
          <Link href="/docs" className="flex items-center space-x-2 text-slate-400 hover:text-white transition">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Docs (RFC-001)</span>
          </Link>
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>STATUS</span>
            <span className="flex items-center space-x-1.5 text-emerald-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>LIVE</span>
            </span>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT WRAPPER */}
      <div className="flex-1 md:ml-[240px] flex flex-col min-h-screen">
        
        {/* TOPBAR */}
        <header className="h-14 border-b border-white/10 bg-[#09090b]/80 backdrop-blur px-6 md:px-8 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center space-x-3 text-xs">
            <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono font-medium text-[10px] uppercase">
              LIVE MODE
            </span>
            <span className="text-slate-600">/</span>
            <span className="text-slate-300 font-medium">ACME_CORP_MAIN</span>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center bg-[#121214] border border-white/10 rounded-md px-3 py-1 text-xs text-slate-400 w-60">
              <Search className="w-3.5 h-3.5 mr-2 text-slate-500" />
              <span className="flex-1 text-slate-500">Search agents, keys...</span>
              <span className="text-[10px] font-mono border border-white/20 rounded px-1 text-slate-400">⌘K</span>
            </div>
            <button className="text-slate-400 hover:text-white transition">
              <HelpCircle className="w-4 h-4" />
            </button>
            <button className="text-slate-400 hover:text-white transition">
              <Bell className="w-4 h-4" />
            </button>
            <div className="w-7 h-7 rounded-full bg-white/10 border border-white/20 text-white font-mono font-bold text-xs flex items-center justify-center">
              AC
            </div>
          </div>
        </header>

        {/* PAGE CONTENT */}
        <main className="flex-1 p-6 md:p-10 max-w-6xl w-full mx-auto">
          {children}
        </main>
      </div>

    </div>
  );
}
"""

# -----------------------------------------------------------------------------
# PAGE OVERVIEW (/dashboard)
# -----------------------------------------------------------------------------
overview_dir = os.path.join(dash_group_dir, 'dashboard')
os.makedirs(overview_dir, exist_ok=True)
overview_code = """'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Bot, Key, Activity, ArrowUpRight, Copy, Check, Lock, RefreshCw, ShieldAlert } from 'lucide-react';

export default function DashboardOverview() {
  const [copiedKey, setCopiedKey] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);
  const [generatedLicense, setGeneratedLicense] = useState<string>('');

  const activeAgentsCount = 4;
  const maxAgentsQuota = 10;
  const usagePercentage = (activeAgentsCount / maxAgentsQuota) * 100;
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Overview & Agent Quotas</h1>
        <p className="text-sm text-slate-400 mt-1">Monitor active connected agents, manage API keys, and enforce quotas.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[#121214] border border-white/10 rounded-xl p-6">
          <div className="flex justify-between items-center text-slate-400 mb-3 text-xs uppercase tracking-wider font-mono">
            <span>Active Agents Quota</span>
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-extrabold text-white font-mono">{activeAgentsCount}</span>
            <span className="text-lg text-slate-500 font-mono">/ {maxAgentsQuota}</span>
            <span className="text-xs text-emerald-400 font-mono ml-auto">6 slots free</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
            <div className="bg-white h-full rounded-full" style={{ width: `${usagePercentage}%` }}></div>
          </div>
          <p className="text-xs text-slate-500 mt-3">Free Tier limit: 10 concurrent active agents.</p>
        </div>

        <div className="bg-[#121214] border border-white/10 rounded-xl p-6">
          <div className="flex justify-between items-center text-slate-400 mb-3 text-xs uppercase tracking-wider font-mono">
            <span>Active API Keys</span>
            <Key className="w-4 h-4 text-white" />
          </div>
          <div className="text-4xl font-extrabold text-white font-mono">2</div>
          <p className="text-xs text-emerald-400 mt-2 font-medium">✓ Live & Test Keys Active</p>
          <p className="text-xs text-slate-500 mt-1">Authenticated via HMAC-SHA256 & JWT.</p>
        </div>

        <div className="bg-[#121214] border border-white/10 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2 font-mono">Current Plan</div>
            <div className="text-xl font-bold text-white">Free Developer Tier</div>
            <p className="text-xs text-slate-400 mt-1">Self-hosted, E2E Encryption, up to 10 agents.</p>
          </div>
          <Link href="/billing" className="mt-4 py-2 px-4 rounded-lg bg-white text-black font-semibold text-xs flex items-center justify-center space-x-2 hover:bg-slate-200 transition">
            <span>Upgrade to Pro ($29/mo)</span>
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      <div className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white">API Key Credentials</h2>
        <div className="bg-[#08080A] border border-slate-800 rounded-lg p-3 flex items-center justify-between font-mono text-xs">
          <div className="flex items-center space-x-3">
            <Lock className="w-4 h-4 text-slate-400" />
            <span className="text-slate-300">{sampleApiKey.substring(0, 16)}****************</span>
          </div>
          <button onClick={handleCopyKey} className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center space-x-1.5 transition font-sans font-medium">
            {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedKey ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      <div className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white">Self-Hosted Signed License Key</h2>
        <button onClick={handleGenerateLicense} className="py-2 px-4 border border-slate-700 hover:border-white text-white text-xs font-semibold rounded-lg flex items-center space-x-2 transition bg-black/40">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Generate Signed License Token</span>
        </button>
        {generatedLicense && (
          <div className="bg-[#08080A] border border-slate-800 rounded-lg p-3 font-mono text-xs text-slate-300 break-all">
            <div className="text-[10px] text-slate-500 uppercase mb-1">Token Ed25519 :</div>
            <div className="text-emerald-400">{generatedLicense}</div>
          </div>
        )}
      </div>

      <div className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <ShieldAlert className="w-5 h-5 text-amber-400" />
          <span>Quota Enforcement Simulator (11th Agent Test)</span>
        </h2>
        <button onClick={handleSimulate11thAgent} disabled={simulating} className="py-2.5 px-4 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 text-red-400 text-xs font-semibold rounded-lg flex items-center space-x-2 transition">
          {simulating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
          <span>Simulate Connecting 11th Agent</span>
        </button>

        {simResult && (
          <div className={`border rounded-lg p-4 font-mono text-xs space-y-2 ${simResult.status === 403 ? 'bg-red-500/5 border-red-500/30 text-red-400' : 'bg-emerald-500/5 border-emerald-500/30 text-emerald-400'}`}>
            <div className="font-bold">HTTP RESPONSE : {simResult.status} {simResult.status === 403 ? 'FORBIDDEN (QUOTA_EXCEEDED)' : 'OK'}</div>
            <pre className="bg-black/60 p-3 rounded text-[11px] overflow-x-auto text-slate-200">
              {JSON.stringify(simResult.data, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
"""

# -----------------------------------------------------------------------------
# PAGE AGENTS (/agents)
# -----------------------------------------------------------------------------
agents_dir = os.path.join(dash_group_dir, 'agents')
os.makedirs(agents_dir, exist_ok=True)
agents_code = """'use client';

import React from 'react';
import { Bot, RefreshCw, Power } from 'lucide-react';

export default function AgentsPage() {
  const agents = [
    { name: 'acme/lead_orchestrator', role: 'admin', caps: 'orchestration', status: 'ONLINE', uptime: '3d 12h' },
    { name: 'acme/translator_french', role: 'worker', caps: 'translate', status: 'ONLINE', uptime: '1d 04h' },
    { name: 'acme/financial_engine', role: 'worker', caps: 'calculate, analyze', status: 'ONLINE', uptime: '5d 20h' },
    { name: 'acme/security_auditor', role: 'inspector', caps: 'audit_read', status: 'ONLINE', uptime: '12h 30m' },
  ];

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Connected Agents Directory</h1>
          <p className="text-xs text-slate-400 mt-1">Live view of agents connected to your org hub (4 / 10 active slots used).</p>
        </div>
        <button className="py-2 px-3 bg-white/5 border border-white/10 hover:bg-white/10 text-slate-200 text-xs font-semibold rounded-lg flex items-center space-x-2 transition">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh List</span>
        </button>
      </div>

      <div className="bg-[#121214] border border-white/10 rounded-xl overflow-hidden">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-[#18181b]/50 border-b border-white/10 text-slate-400 uppercase text-[11px]">
            <tr>
              <th className="p-4">Agent Name</th>
              <th className="p-4">Role</th>
              <th className="p-4">Capabilities</th>
              <th className="p-4">Uptime</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300">
            {agents.map((a, i) => (
              <tr key={i} className="hover:bg-white/[0.02] transition">
                <td className="p-4 font-semibold text-white flex items-center space-x-2">
                  <Bot className="w-4 h-4 text-slate-400" />
                  <span>{a.name}</span>
                </td>
                <td className="p-4"><span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300">{a.role}</span></td>
                <td className="p-4 text-slate-400">{a.caps}</td>
                <td className="p-4 text-slate-400">{a.uptime}</td>
                <td className="p-4">
                  <span className="inline-flex items-center space-x-1.5 text-emerald-400 font-semibold text-[11px]">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>{a.status}</span>
                  </span>
                </td>
                <td className="p-4 text-right">
                  <button className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition" title="Disconnect Agent">
                    <Power className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
"""

# -----------------------------------------------------------------------------
# PAGE KEYS (/keys)
# -----------------------------------------------------------------------------
keys_dir = os.path.join(dash_group_dir, 'keys')
os.makedirs(keys_dir, exist_ok=True)
keys_code = """'use client';

import React, { useState } from 'react';
import { Plus, Copy, Check, Trash2, Lock } from 'lucide-react';

export default function KeysPage() {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const keys = [
    { name: 'Production Backend Primary', key: 'nx_live_acme_super_secret_key_123', created: '2026-02-10', role: 'admin' },
    { name: 'Staging Environment Worker', key: 'nx_live_acme_staging_key_998877', created: '2026-03-01', role: 'worker' },
  ];

  const handleCopy = (keyText: string, index: number) => {
    navigator.clipboard.writeText(keyText);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">API Keys & License Credentials</h1>
          <p className="text-xs text-slate-400 mt-1">Manage cryptographic service account keys for production clusters.</p>
        </div>
        <button className="py-2 px-4 bg-white text-black hover:bg-slate-200 font-semibold text-xs rounded-lg flex items-center space-x-2 transition">
          <Plus className="w-4 h-4" />
          <span>Create New API Key</span>
        </button>
      </div>

      <div className="space-y-4">
        {keys.map((k, i) => (
          <div key={i} className="bg-[#121214] border border-white/10 rounded-xl p-5 space-y-3">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-white font-mono">{k.name}</h3>
                <span className="text-[11px] text-slate-500 font-mono">Created on {k.created} • Role: {k.role}</span>
              </div>
              <button className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-[#08080A] border border-slate-800 rounded-lg p-3 flex items-center justify-between font-mono text-xs">
              <div className="flex items-center space-x-3">
                <Lock className="w-4 h-4 text-slate-400" />
                <span className="text-slate-300">{k.key.substring(0, 16)}****************</span>
              </div>
              <button 
                onClick={() => handleCopy(k.key, i)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center space-x-1.5 transition font-sans"
              >
                {copiedIndex === i ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedIndex === i ? 'Copied' : 'Copy Key'}</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
"""

# -----------------------------------------------------------------------------
# PAGE SECURITY (/security)
# -----------------------------------------------------------------------------
security_dir = os.path.join(dash_group_dir, 'security')
os.makedirs(security_dir, exist_ok=True)
security_code = """'use client';

import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function SecurityPage() {
  const auditLogs = [
    { index: 142, event: 'AGENT_REGISTERED', sender: 'acme/lead_orchestrator', target: 'Hub_Acme', hash: '8f3a1b2c4d5e...', status: 'VERIFIED' },
    { index: 143, event: 'TASK_SUBMITTED', sender: 'acme/lead_orchestrator', target: 'globex/financial_engine', hash: 'e2f3a4b5c6d7...', status: 'VERIFIED' },
    { index: 144, event: 'TASK_COMPLETED', sender: 'globex/financial_engine', target: 'acme/lead_orchestrator', hash: '1a2b3c4d5e6f...', status: 'VERIFIED' },
    { index: 145, event: 'QUOTA_REJECTED', sender: 'unauthorized_bot', target: 'Hub_Acme', hash: '7e8f9a0b1c2d...', status: 'BLOCKED' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Immutable Audit Log & RBAC</h1>
        <p className="text-xs text-slate-400 mt-1">Cryptographically chained Merkle log for SOC2 & HIPAA compliance auditability.</p>
      </div>

      <div className="bg-[#121214] border border-emerald-500/30 bg-emerald-500/5 rounded-xl p-5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ShieldCheck className="w-6 h-6 text-emerald-400" />
          <div>
            <h3 className="text-sm font-bold text-white font-mono">Merkle Audit Log Integrity : 100% VALID</h3>
            <p className="text-xs text-slate-400">All 145 chain blocks cryptographically verified with SHA-256 hashes.</p>
          </div>
        </div>
        <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 font-mono text-xs rounded-full font-semibold">CHAIN SECURE</span>
      </div>

      <div className="bg-[#121214] border border-white/10 rounded-xl overflow-hidden">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-[#18181b]/50 border-b border-white/10 text-slate-400 uppercase text-[11px]">
            <tr>
              <th className="p-4">Block #</th>
              <th className="p-4">Event Type</th>
              <th className="p-4">Sender</th>
              <th className="p-4">Target</th>
              <th className="p-4">SHA-256 Hash</th>
              <th className="p-4 text-right">Integrity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300">
            {auditLogs.map((log, i) => (
              <tr key={i} className="hover:bg-white/[0.02] transition">
                <td className="p-4 text-slate-500">#{log.index}</td>
                <td className="p-4 font-semibold text-white">{log.event}</td>
                <td className="p-4">{log.sender}</td>
                <td className="p-4 text-slate-400">{log.target}</td>
                <td className="p-4 text-slate-500 text-[10px]">{log.hash}</td>
                <td className="p-4 text-right">
                  <span className={`px-2 py-0.5 rounded text-[10px] ${log.status === 'VERIFIED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                    {log.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
"""

# -----------------------------------------------------------------------------
# PAGE BILLING (/billing)
# -----------------------------------------------------------------------------
billing_dir = os.path.join(dash_group_dir, 'billing')
os.makedirs(billing_dir, exist_ok=True)
billing_code = """'use client';

import React from 'react';
import { Check, ArrowUpRight } from 'lucide-react';

export default function BillingPage() {
  return (
    <div className="space-y-8 font-sans">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Subscription Plans & Billing</h1>
        <p className="text-sm text-slate-400 mt-1">Scale your agent infrastructure smoothly from Developer to Enterprise.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[#121214] border border-white/10 rounded-xl p-6 flex flex-col justify-between space-y-6">
          <div>
            <span className="text-xs font-mono uppercase text-slate-400">Developer</span>
            <div className="text-4xl font-extrabold text-white mt-3">$0 <span className="text-xs font-normal text-slate-500">/ month</span></div>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">Perfect for prototyping & personal AI agent projects.</p>

            <ul className="space-y-3 text-xs text-slate-300 mt-6 font-mono">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Up to 10 Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>E2E Encryption (RSA / AES)</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Self-Hosted Local Hub & CLI</span></li>
            </ul>
          </div>

          <button className="w-full py-2.5 bg-white/5 border border-white/10 text-slate-300 text-xs rounded-lg font-semibold cursor-default">
            Current Plan
          </button>
        </div>

        <div className="bg-[#121214] border-2 border-white rounded-xl p-6 flex flex-col justify-between space-y-6 relative">
          <div className="absolute top-3.5 right-3.5 bg-white text-black text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full">
            POPULAR
          </div>

          <div>
            <span className="text-xs font-mono uppercase text-white">Pro Production</span>
            <div className="text-4xl font-extrabold text-white mt-3">$29 <span className="text-xs font-normal text-slate-500">/ month</span></div>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">For growing teams deploying production agent clusters.</p>

            <ul className="space-y-3 text-xs text-slate-200 mt-6 font-mono">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span className="font-medium">Up to 50 Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span>Managed Cloud Hub Option</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span>30-Day Telemetry Logs</span></li>
            </ul>
          </div>

          <button className="w-full py-2.5 bg-white text-black font-bold text-xs rounded-lg flex items-center justify-center space-x-2 hover:bg-slate-200 transition">
            <span>Upgrade to Pro Plan</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>
        </div>

        <div className="bg-[#121214] border border-white/10 rounded-xl p-6 flex flex-col justify-between space-y-6">
          <div>
            <span className="text-xs font-mono uppercase text-slate-400">Enterprise</span>
            <div className="text-4xl font-extrabold text-white mt-3">Custom</div>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">For mission-critical infrastructure & compliance.</p>

            <ul className="space-y-3 text-xs text-slate-300 mt-6 font-mono">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Unlimited Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Hub-to-Hub Federation Peering</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Merkle Audit Log Export</span></li>
            </ul>
          </div>

          <button className="w-full py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 text-xs rounded-lg font-semibold transition">
            Contact Enterprise Sales
          </button>
        </div>
      </div>
    </div>
  );
}
"""

# Ecriture des fichiers
with open(os.path.join(dash_group_dir, 'layout.tsx'), 'w', encoding='utf-8') as f: f.write(layout_code)
with open(os.path.join(overview_dir, 'page.tsx'), 'w', encoding='utf-8') as f: f.write(overview_code)
with open(os.path.join(keys_dir, 'page.tsx'), 'w', encoding='utf-8') as f: f.write(keys_code)
with open(os.path.join(agents_dir, 'page.tsx'), 'w', encoding='utf-8') as f: f.write(agents_code)
with open(os.path.join(security_dir, 'page.tsx'), 'w', encoding='utf-8') as f: f.write(security_code)
with open(os.path.join(billing_dir, 'page.tsx'), 'w', encoding='utf-8') as f: f.write(billing_code)

print("STRUCTURE DASHBOARD GENEREE AVEC SUCCES")
