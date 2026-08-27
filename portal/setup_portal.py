import os

app_dir = os.path.expanduser('~/nexus/portal/src/app')

# 1. globals.css (Fond sombre pur, typographie Inter)
css_content = """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: #08080A;
  color: #FFFFFF;
  letter-spacing: -0.02em;
  -webkit-font-smoothing: antialiased;
}

.font-mono {
  font-family: 'JetBrains Mono', monospace;
}
"""

# 2. layout.tsx (Layout minimaliste)
layout_content = """import './globals.css';
import React from 'react';

export const metadata = {
  title: 'NEXUS — AI Developer Infrastructure Protocol',
  description: 'NEXUS is the open protocol for AI infrastructure.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#08080A] text-white min-h-screen font-sans selection:bg-white selection:text-black">
        {children}
      </body>
    </html>
  );
}
"""

# 3. page.tsx (Landing Page identique à la maquette de ton image)
landing_content = """'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Copy, Check, ChevronDown } from 'lucide-react';

export default function LandingPage() {
  const [copied, setCopied] = useState(false);

  const realNexusCode = `from nexus_sdk import NexusAgent

agent = NexusAgent(
    name="orchestrator",
    capabilities=["translate", "calculate"],
    roles=["admin"],
    encrypt=True
)

@agent.on_task
async def handle_task(input_data, task):
    print(f"Task received: {task.title}")
    return {"status": "COMPLETED", "result": 42}

await agent.connect()
response = await agent.ask(to="translator_french", content="Hello")`;

  const handleCopy = () => {
    navigator.clipboard.writeText(realNexusCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#08080A] text-white flex flex-col justify-between p-8 lg:p-12 max-w-[1500px] mx-auto font-sans">
      
      {/* TOPBAR */}
      <header className="flex items-center justify-between py-2">
        <Link href="/" className="text-xl font-extrabold tracking-widest font-sans hover:opacity-80 transition">
          N E X U S
        </Link>

        <nav className="hidden md:flex items-center space-x-8 text-xs text-slate-400 font-medium">
          <Link href="/dashboard" className="hover:text-white transition">Control Plane</Link>
          <Link href="/docs" className="hover:text-white transition">Docs (RFC-001)</Link>
          <Link href="/pricing" className="hover:text-white transition">Pricing</Link>
          <a href="https://github.com/mrlomemba-cmd/nexus" target="_blank" className="hover:text-white transition">GitHub</a>
        </nav>

        <div className="flex items-center space-x-6 text-xs">
          <Link href="/dashboard" className="text-slate-300 hover:text-white transition font-medium">Log in</Link>
          <Link href="/dashboard" className="px-4 py-2.5 border border-slate-700 hover:border-slate-400 rounded-md font-medium text-white flex items-center space-x-2 transition bg-black/40">
            <span>Start building</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* HERO SECTION */}
      <main className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center my-auto py-12">
        
        <div className="lg:col-span-6 space-y-8">
          <div className="text-[11px] font-mono tracking-widest text-slate-500 uppercase font-semibold">
            AI DEVELOPER INFRASTRUCTURE PROTOCOL
          </div>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.95] text-white uppercase">
            BUILD. SCALE.<br />INTELLIGENCE.
          </h1>

          <p className="text-sm text-slate-400 max-w-md font-normal leading-relaxed">
            NEXUS is the open protocol for AI infrastructure. Connect agents, models, and workflows into a unified, E2E encrypted network.
          </p>

          <div className="pt-2 flex items-center space-x-4">
            <Link href="/dashboard" className="inline-flex items-center space-x-3 px-6 py-3.5 border border-slate-700 hover:border-white rounded-md text-xs font-semibold text-white transition bg-black/50 group">
              <span>Open Control Plane</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link href="/docs" className="inline-flex items-center space-x-2 px-5 py-3.5 text-xs font-medium text-slate-400 hover:text-white transition">
              <span>Read RFC-001 Spec</span>
            </Link>
          </div>
        </div>

        {/* CODE EDITOR */}
        <div className="lg:col-span-6">
          <div className="bg-[#0D0E12] border border-[#1F2028] rounded-xl overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2028] text-xs text-slate-400 font-mono">
              <div className="flex items-center space-x-2">
                <span className="text-slate-500">⚙</span>
                <span className="text-slate-300 font-medium">agent_orchestrator.py</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-emerald-400 text-[10px]">● REAL SDK CODE</span>
                <button onClick={handleCopy} className="hover:text-white transition flex items-center space-x-1">
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <div className="p-5 font-mono text-xs leading-relaxed overflow-x-auto text-slate-300 selection:bg-slate-800">
              <pre suppressHydrationWarning>
                <code>{realNexusCode}</code>
              </pre>
            </div>
          </div>
        </div>

      </main>

      {/* FOOTER */}
      <footer className="grid grid-cols-2 md:grid-cols-4 gap-4 py-6 border-t border-slate-900 text-xs text-slate-500 font-medium">
        <div>Open by design (Apache 2.0)</div>
        <div className="border-l-0 md:border-l border-slate-900 md:pl-6">E2E Encrypted (RSA/AES)</div>
        <div className="border-l-0 md:border-l border-slate-900 md:pl-6">Python & Node.js SDKs</div>
        <div className="border-l-0 md:border-l border-slate-900 md:pl-6">Production Ready</div>
      </footer>

    </div>
  );
}
"""

# 4. dashboard/page.tsx (Control Plane / Quotas épuré)
dashboard_content = """'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Bot, Key, ShieldAlert, Copy, Check, Zap, Plus, Lock, RefreshCw, ArrowUpRight, ArrowLeft } from 'lucide-react';

export default function DashboardPage() {
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
    <div className="min-h-screen bg-[#08080A] text-white p-8 max-w-[1200px] mx-auto font-sans space-y-8">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-6">
        <div>
          <Link href="/" className="inline-flex items-center space-x-2 text-xs text-slate-400 hover:text-white transition mb-2">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Home</span>
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-white">Control Plane — Overview & Quotas</h1>
          <p className="text-xs text-slate-400 mt-1">Manage cryptographic API keys and enforce local agent quota limits.</p>
        </div>
        <div className="text-xs font-mono px-3 py-1 bg-slate-900 border border-slate-800 rounded text-slate-300">
          ORG: ACME_CORP_MAIN
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6">
          <div className="flex justify-between items-center text-slate-400 mb-3 text-xs uppercase tracking-wider font-mono">
            <span>Active Agents Quota</span>
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-extrabold text-white font-mono">{activeAgentsCount}</span>
            <span className="text-lg text-slate-500 font-mono">/ {maxAgentsQuota}</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
            <div className="bg-white h-full rounded-full" style={{ width: `${usagePercentage}%` }}></div>
          </div>
          <p className="text-xs text-slate-500 mt-3">Free Tier limit: 10 concurrent agents.</p>
        </div>

        <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6">
          <div className="flex justify-between items-center text-slate-400 mb-3 text-xs uppercase tracking-wider font-mono">
            <span>API Keys</span>
            <Key className="w-4 h-4 text-white" />
          </div>
          <div className="text-4xl font-extrabold text-white font-mono">2</div>
          <p className="text-xs text-emerald-400 mt-2 font-medium">✓ Live & Test Keys Active</p>
        </div>

        <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2 font-mono">Current Plan</div>
            <div className="text-xl font-bold text-white">Free Developer Tier</div>
          </div>
          <Link href="/pricing" className="mt-4 py-2.5 px-4 rounded-lg bg-white text-black font-semibold text-xs flex items-center justify-center space-x-2 hover:bg-slate-200 transition">
            <span>Upgrade to Pro ($29/mo)</span>
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* API KEYS SECTION */}
      <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 space-y-4">
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

      {/* LICENSE GENERATOR SECTION */}
      <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 space-y-4">
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

      {/* SIMULATOR SECTION */}
      <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 space-y-4">
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

# 5. docs/page.tsx (RFC-001 Documentation)
docs_content = """'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function DocsPage() {
  return (
    <div className="space-y-8 font-sans max-w-4xl mx-auto p-8">
      <Link href="/" className="inline-flex items-center space-x-2 text-xs text-slate-400 hover:text-white transition">
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Home</span>
      </Link>

      <div>
        <span className="text-xs font-mono text-slate-500 uppercase tracking-widest">RFC-001 SPECIFICATION</span>
        <h1 className="text-3xl font-extrabold text-white mt-1">Nexus Core Protocol v1</h1>
        <p className="text-sm text-slate-400 mt-2">Official technical specification for universal AI agent coordination.</p>
      </div>

      <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 space-y-6 font-mono text-xs text-slate-300 leading-relaxed">
        <div>
          <h3 className="text-white font-bold text-sm mb-2 font-sans">1. Nexus Message Envelope (nexus/v1)</h3>
          <pre className="bg-[#08080A] p-4 rounded-lg text-slate-200 overflow-x-auto">
{`{
  "id": "UUID-v4 (Unique message ID)",
  "version": "nexus/v1",
  "type": "register | message | request | response | task_submit | task_assign | task_update",
  "sender": "org_id/agent_name",
  "to": "org_id/target_agent",
  "content": "Ciphertext B64 (RSA-2048 + AES-256-GCM)",
  "timestamp": 1770000000.0,
  "token": "JWT_Signed_Token"
}`}
          </pre>
        </div>

        <div>
          <h3 className="text-white font-bold text-sm mb-2 font-sans">2. Cryptographic Security & E2E Encryption</h3>
          <p className="text-slate-400 font-sans text-xs leading-relaxed">
            All payload content is encrypted client-side using hybrid encryption: RSA-2048-OAEP for key exchange and AES-256-GCM for payload data. The Nexus Hub routes messages without access to plaintext content.
          </p>
        </div>
      </div>
    </div>
  );
}
"""

# 6. pricing/page.tsx (Page Tarification)
pricing_content = """'use client';

import React from 'react';
import Link from 'next/link';
import { Check, ArrowLeft, ArrowRight } from 'lucide-react';

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-[#08080A] text-white p-8 max-w-[1200px] mx-auto font-sans space-y-12">
      <Link href="/" className="inline-flex items-center space-x-2 text-xs text-slate-400 hover:text-white transition">
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Home</span>
      </Link>

      <div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white">Simple, Predictable Pricing</h1>
        <p className="text-sm text-slate-400 mt-2">Start free with self-hosted agents. Upgrade as your agent network grows.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 flex flex-col justify-between space-y-6">
          <div>
            <span className="text-xs font-mono uppercase text-slate-400">Developer</span>
            <div className="text-4xl font-extrabold text-white mt-3">$0 <span className="text-xs font-normal text-slate-500">/ month</span></div>
            <p className="text-xs text-slate-400 mt-2">Perfect for prototyping & personal AI agent projects.</p>
            <ul className="space-y-3 text-xs text-slate-300 mt-6">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Up to 10 Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>E2E Encryption (RSA / AES)</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Self-Hosted Local Hub & CLI</span></li>
            </ul>
          </div>
          <Link href="/dashboard" className="w-full py-2.5 bg-slate-800 text-slate-300 text-xs rounded-lg font-semibold text-center block">Current Plan</Link>
        </div>

        <div className="bg-[#0D0E12] border-2 border-white rounded-xl p-6 flex flex-col justify-between space-y-6 relative">
          <div className="absolute top-3 right-3 bg-white text-black text-[10px] font-bold px-2 py-0.5 rounded uppercase">POPULAR</div>
          <div>
            <span className="text-xs font-mono uppercase text-white">Pro Production</span>
            <div className="text-4xl font-extrabold text-white mt-3">$29 <span className="text-xs font-normal text-slate-500">/ month</span></div>
            <p className="text-xs text-slate-400 mt-2">For growing teams deploying production agent clusters.</p>
            <ul className="space-y-3 text-xs text-slate-200 mt-6">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span className="font-medium">Up to 50 Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span>Managed Cloud Hub Option</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-white" /><span>30-Day Telemetry Logs</span></li>
            </ul>
          </div>
          <Link href="/dashboard" className="w-full py-2.5 bg-white text-black font-bold text-xs rounded-lg flex items-center justify-center space-x-2 hover:bg-slate-200 transition">
            <span>Upgrade to Pro</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 flex flex-col justify-between space-y-6">
          <div>
            <span className="text-xs font-mono uppercase text-slate-400">Enterprise</span>
            <div className="text-4xl font-extrabold text-white mt-3">Custom</div>
            <p className="text-xs text-slate-400 mt-2">For mission-critical infrastructure & compliance.</p>
            <ul className="space-y-3 text-xs text-slate-300 mt-6">
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Unlimited Active Agents</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Hub-to-Hub Federation Peering</span></li>
              <li className="flex items-center space-x-2"><Check className="w-4 h-4 text-emerald-400" /><span>Merkle Audit Log Export</span></li>
            </ul>
          </div>
          <button className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg font-semibold transition">Contact Sales</button>
        </div>
      </div>
    </div>
  );
}
"""

# Ecriture des fichiers
with open(os.path.join(app_dir, 'globals.css'), 'w', encoding='utf-8') as f:
    f.write(css_content)

with open(os.path.join(app_dir, 'layout.tsx'), 'w', encoding='utf-8') as f:
    f.write(layout_content)

with open(os.path.join(app_dir, 'page.tsx'), 'w', encoding='utf-8') as f:
    f.write(landing_content)

os.makedirs(os.path.join(app_dir, 'dashboard'), exist_ok=True)
with open(os.path.join(app_dir, 'dashboard/page.tsx'), 'w', encoding='utf-8') as f:
    f.write(dashboard_content)

os.makedirs(os.path.join(app_dir, 'docs'), exist_ok=True)
with open(os.path.join(app_dir, 'docs/page.tsx'), 'w', encoding='utf-8') as f:
    f.write(docs_content)

os.makedirs(os.path.join(app_dir, 'pricing'), exist_ok=True)
with open(os.path.join(app_dir, 'pricing/page.tsx'), 'w', encoding='utf-8') as f:
    f.write(pricing_content)

print("✅ TOUS LES FICHIERS ET ROUTES ONT ÉTÉ GÉNÉRÉS SANS AUCUNE ERREUR !")
