'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { 
  ArrowRight, 
  Copy, 
  Check, 
  Terminal, 
  Zap, 
  ShieldCheck, 
  Globe, 
  BookOpen, 
  Lock,
  Layers,
  Network,
  Cpu,
  GitBranch,
  ShieldAlert,
  CheckCircle2,
  Building2,
  ArrowLeftRight,
  Printer,
  FileText,
  Clock
} from 'lucide-react';
import NetworkBackground from '@/components/NetworkBackground';
import AnimatedCodeEditor from '@/components/AnimatedCodeEditor';
import InterMeshLogo from '@/components/InterMeshLogo';

export default function LandingPage() {
  const installCommand = "pip install intermesh-sdk";

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(installCommand);
  };

  return (
    <div className="relative min-h-screen bg-[#08080A] text-slate-50 font-sans selection:bg-zinc-800 selection:text-white notranslate" translate="no" suppressHydrationWarning>
      
      {/* Background Effect */}
      <NetworkBackground />

      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            'radial-gradient(ellipse 80% 70% at 50% 45%, rgba(8,8,10,0.55) 0%, rgba(8,8,10,0.78) 55%, rgba(8,8,10,0.92) 100%)',
        }}
      />

      <div className="relative z-10 min-h-screen flex flex-col justify-between p-6 sm:p-8 lg:p-12 max-w-[1500px] mx-auto font-sans space-y-20">
        
        {/* TOPBAR NAVIGATION */}
        <header className="flex items-center justify-between py-2">
          <Link
            href="/"
            className="flex items-center space-x-3 text-xl font-extrabold tracking-widest hover:opacity-80 transition notranslate font-sans"
            translate="no"
          >
            <InterMeshLogo className="w-6 h-6 shrink-0" />
            <span>N E X U S</span>
          </Link>

          <nav className="hidden md:flex items-center space-x-8 text-xs text-slate-400 font-medium">
            <Link href="/dashboard" className="hover:text-white transition">Control Plane</Link>
            <Link href="/docs" className="hover:text-white transition">Docs (RFC-001)</Link>
            <Link href="/pricing" className="hover:text-white transition">Pricing</Link>
            <a href="https://github.com/intermeshteam/intermesh" target="_blank" className="hover:text-white transition">GitHub</a>
          </nav>

          <div className="flex items-center space-x-6 text-xs">
            <Link href="/auth" className="text-slate-200 hover:text-white transition font-medium">Log in</Link>
            <Link href="/auth" className="px-4 py-2.5 border border-slate-600 hover:border-white rounded-md font-medium text-white flex items-center space-x-2 transition bg-black/70 backdrop-blur-sm">
              <span>Start building</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </header>

        {/* HERO SECTION */}
        <main className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center py-6">
          
          <div className="lg:col-span-6 space-y-8">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded bg-white/5 border border-white/10 text-[11px] font-mono text-zinc-300">
              <Clock className="w-3.5 h-3.5 text-zinc-300 stroke-[1.5]" />
              <span>24/7 AUTONOMOUS INTERNAL WORKFLOWS READY</span>
            </div>

            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.95] text-white uppercase">
              BUILD. SCALE.<br />INTELLIGENCE.
            </h1>

            <p className="text-sm text-slate-200 max-w-md leading-relaxed">
              INTERMESH is the open protocol for AI infrastructure. Connect internal workers like <strong>Data Intake & Print Fulfillment agents</strong> to automate 24/7 workflows seamlessly.
            </p>

            {/* QUICK INSTALL COMMAND BAR */}
            <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-lg p-3 flex items-center justify-between font-mono text-xs max-w-md">
              <div className="flex items-center space-x-2 text-zinc-300">
                <Terminal className="w-4 h-4 text-zinc-500 stroke-[1.5]" />
                <span className="text-zinc-500">$</span>
                <span className="text-white font-bold">{installCommand}</span>
              </div>
              <button 
                onClick={handleCopyCmd}
                className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-[11px] flex items-center space-x-1 transition font-sans"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </button>
            </div>

            <div className="pt-2 flex items-center space-x-4">
              <Link href="/auth" className="inline-flex items-center space-x-3 px-6 py-3.5 border border-slate-500 hover:border-white rounded-md text-xs font-semibold text-white transition bg-black/75 backdrop-blur-sm group">
                <span>Open Control Plane</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link href="/docs" className="inline-flex items-center space-x-2 px-5 py-3.5 text-xs font-medium text-slate-200 hover:text-white transition">
                <span>Read RFC-001 Spec</span>
              </Link>
            </div>
          </div>

          {/* RIGHT: ANIMATED CODE EDITOR */}
          <div className="lg:col-span-6">
            <AnimatedCodeEditor />
          </div>

        </main>

        {/* SECTION 24/7 INTERNAL AUTOMATION (SAISIE ➜ IMPRESSION) */}
        <section className="relative z-10 border-t border-zinc-900 bg-[#0A0A0C] py-20 px-6">
          <div className="max-w-6xl mx-auto space-y-12">
            
            <div className="text-center space-y-3 max-w-3xl mx-auto">
              <span className="text-xs font-mono uppercase tracking-widest text-zinc-400 font-semibold flex items-center justify-center space-x-2">
                <Clock className="w-4 h-4 stroke-[1.5]" />
                <span>24/7 AUTONOMOUS INTERNAL OPERATIONS</span>
              </span>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                How Internal Agents Work Together Non-Stop
              </h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                Connect specialized internal daemons like Data Intake & Print Fulfillment agents to automate corporate operations 24 hours a day, 7 days a week.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-left">
              
              {/* AGENT 1 : SAISIE (DATA INTAKE) */}
              <div className="bg-[#0D0E12] border border-zinc-800 rounded-2xl p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 font-sans text-xs">
                  <span className="text-white font-bold flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
                    <span>AGENT 1: DATA INTAKE (SAISIE 24/7)</span>
                  </span>
                  <span className="text-cyan-400 font-mono text-[10px]">acme/data_intake</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  Captures incoming invoice documents 24/7 and delegates print fulfillment tasks.
                </p>
                <pre className="bg-[#050507] p-4 rounded-xl font-mono text-[11px] text-slate-300 border border-zinc-800/80 overflow-x-auto">
{`from intermesh import InterMeshAgent

# 24/7 Data Intake Daemon
intake_agent = InterMeshAgent(name="data_intake", org_id="acme")
await intake_agent.connect()

# Delegate print task to Print Fulfillment Agent
result = await intake_agent.submit_task(
    title="Print Invoice INV-2026-1001",
    assignee="acme/print_fulfillment",
    input_data={"document_id": "INV-1001", "format": "PDF/A"}
)

print(result) # -> {"status": "PRINTED", "pages": 3}`}
                </pre>
              </div>

              {/* AGENT 2 : IMPRESSION (PRINT FULFILLMENT) */}
              <div className="bg-[#0D0E12] border border-zinc-800 rounded-2xl p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 font-sans text-xs">
                  <span className="text-white font-bold flex items-center space-x-2">
                    <Printer className="w-4 h-4 text-zinc-400 stroke-[1.5]" />
                    <span>AGENT 2: PRINT FULFILLMENT (IMPRESSION 24/7)</span>
                  </span>
                  <span className="text-emerald-400 font-mono text-[10px]">acme/print_fulfillment</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  Receives print tasks 24/7, generates PDF/A documents, and triggers physical/digital printing.
                </p>
                <pre className="bg-[#050507] p-4 rounded-xl font-mono text-[11px] text-slate-300 border border-zinc-800/80 overflow-x-auto">
{`from intermesh import InterMeshAgent

print_agent = InterMeshAgent(name="print_fulfillment", org_id="acme")

@print_agent.on_task
async def handle_print_task(input_data, task):
    # Process PDF generation & print queue 24/7
    return {
        "status": "PRINTED",
        "document_id": input_data["document_id"],
        "pages": 3
    }

await print_agent.connect()`}
                </pre>
              </div>

            </div>

          </div>
        </section>

        {/* WHY INTERMESH EXISTS */}
        <section className="relative z-10 border-t border-zinc-900 bg-[#08080A] py-20 px-6">
          <div className="max-w-6xl mx-auto space-y-12">
            
            <div className="text-center space-y-3 max-w-3xl mx-auto">
              <span className="text-xs font-mono uppercase tracking-widest text-zinc-400 font-semibold">THE PROBLEM & OUR MISSION</span>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-sans">
                Why AI Agents Needed a Universal Standard
              </h2>
              <p className="text-sm text-slate-400 leading-relaxed font-normal font-sans">
                By 2030, billions of autonomous AI agents will operate across the global economy. Without an open, neutral protocol, agent networks face catastrophic fragmentation and security risks.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              
              <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-2xl p-6 space-y-4 hover:border-zinc-700 transition">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <GitBranch className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white font-sans">The Fragmentation Barrier</h3>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  Today, agents built in LangChain cannot talk to CrewAI teams or custom TypeScript services without writing fragile, custom glue code for every connection.
                </p>
              </div>

              <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-2xl p-6 space-y-4 hover:border-zinc-700 transition">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <ShieldAlert className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white font-sans">The Security Void</h3>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  Sending plaintext prompts and confidential enterprise payloads across third-party brokers creates unacceptable data leakage risks for production.
                </p>
              </div>

              <div className="bg-[#0D0E12] border border-zinc-800/80 rounded-2xl p-6 space-y-4 hover:border-zinc-700 transition">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <CheckCircle2 className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white font-sans">The InterMesh Solution</h3>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  RFC-001 gives the world a neutral, open-source protocol. Agents self-discover, negotiate JWT authentication, and execute tasks with zero-trust E2E encryption.
                </p>
              </div>

            </div>

          </div>
        </section>

        {/* CORE CAPABILITIES GRID */}
        <section className="relative z-10 border-t border-zinc-900 bg-[#0A0A0C] py-20 px-6">
          <div className="max-w-6xl mx-auto space-y-12">
            
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <span className="text-xs font-mono uppercase tracking-widest text-zinc-500 font-semibold">ENTERPRISE FEATURES</span>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight font-sans">
                Engineered for Production Scale
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-left font-sans">
              
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <Lock className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">End-to-End Encryption</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Hybrid RSA-2048-OAEP & AES-256-GCM client-side encryption. The Hub routes messages without ever reading plaintext payloads.
                </p>
              </div>

              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <Globe className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">Cross-Language Mesh</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Native SDKs for Python and Node.js. A Python agent delegates tasks to a TypeScript worker transparently and securely.
                </p>
              </div>

              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <ShieldCheck className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">Immutable Merkle Audit</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Cryptographically chained SHA-256 event log for SOC2, HIPAA, and financial compliance audits built-in.
                </p>
              </div>

              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <Network className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">Hub-to-Hub Federation</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Connect private organization hubs safely across cloud boundaries with zero-trust peering.
                </p>
              </div>

              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <Layers className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">Distributed Task Engine</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Asynchronous task delegation, heartbeat tracking, and status updates across complex multi-agent workflows.
                </p>
              </div>

              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
                  <Cpu className="w-5 h-5 stroke-[1.5]" />
                </div>
                <h3 className="text-base font-bold text-white">Self-Hosted Quota Control</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  10-agent free tier with Ed25519 signed license tokens for offline verification on local hubs.
                </p>
              </div>

            </div>

          </div>
        </section>

        {/* CTA SECTION */}
        <section className="relative z-10 border-t border-zinc-900 bg-[#0A0A0C] py-20 px-6 text-center font-sans">
          <div className="max-w-3xl mx-auto space-y-6">
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Ready to Build the Future of AI Infrastructure?
            </h2>
            <p className="text-sm text-slate-400 max-w-xl mx-auto leading-relaxed">
              Get started in seconds with our open-source SDK. Free self-hosted tier includes 10 active agent slots.
            </p>
            <div className="pt-2 flex justify-center">
              <Link href="/auth" className="px-8 py-3.5 rounded-full bg-white text-black font-semibold text-sm hover:bg-slate-200 transition shadow-[0_0_40px_rgba(255,255,255,0.2)] flex items-center space-x-2">
                <span>Open Control Plane</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </section>

        {/* FOOTER */}
        <footer className="relative z-10 border-t border-zinc-900 bg-[#08080A] py-12 px-6 font-sans">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center text-sm text-slate-500">
            <div className="flex items-center space-x-2 font-semibold">
              <InterMeshLogo className="w-4 h-4 shrink-0" />
              <span>InterMesh Protocol © 2026 • Apache 2.0 License</span>
            </div>
            <div className="flex items-center space-x-6 mt-4 md:mt-0 font-medium text-xs">
              <Link href="/terms" className="hover:text-slate-300 transition">Terms</Link>
              <Link href="/privacy" className="hover:text-white transition">Privacy</Link>
              <Link href="/docs" className="hover:text-white transition">Docs (RFC-001)</Link>
              <a href="https://github.com/intermeshteam/intermesh" target="_blank" className="hover:text-white transition">GitHub</a>
            </div>
          </div>
        </footer>

      </div>
    </div>
  );
}
