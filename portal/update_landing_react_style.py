import os

page_path = os.path.expanduser('~/nexus/portal/src/app/page.tsx')

landing_code = """'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Copy, Check, Terminal, Zap, ShieldCheck, Globe, Network, Cpu, BookOpen } from 'lucide-react';
import NetworkBackground from '@/components/NetworkBackground';

export default function LandingPage() {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'callable' | 'decorator' | 'langchain'>('callable');

  const snippets = {
    callable: `from intermesh import InterMeshAgent

# Turn any Python function into a secure InterMesh Agent
agent = InterMeshAgent.from_callable(
    fn=my_existing_llm_function,
    name="analyzer_bot",
    capabilities=["summarize", "extract"]
)

# Auto-connects, negotiates JWT auth & E2E encryption
await agent.connect()`,

    decorator: `from intermesh import intermesh_service

# Publish any function as an E2E encrypted InterMesh Agent
@intermesh_service(name="translator_service", capabilities=["translate"])
def translate_tool(input_data):
    return {"translated_text": "Bonjour le monde"}

# Automatically registered & discoverable worldwide`,

    langchain: `from intermesh import InterMeshAgent

# Connect your existing LangChain or CrewAI chains to the mesh
agent = InterMeshAgent.from_langchain(
    chain_or_runnable=my_crewai_crew,
    name="research_crew",
    capabilities=["web_research", "synthesis"]
)

await agent.connect()`
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(snippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative min-h-screen bg-[#08080A] text-slate-50 font-sans selection:bg-cyan-500/30 selection:text-cyan-50 notranslate" translate="no" suppressHydrationWarning>
      
      {/* BACKGROUND EFFECTS (REACT.DEV STYLE) */}
      <NetworkBackground />
      <div className="absolute inset-0 bg-[#08080A]/80 z-0 pointer-events-none" />
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-cyan-500/20 blur-[120px] rounded-full z-0 pointer-events-none" />

      {/* TOP NAVIGATION */}
      <header className="relative z-20 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto w-full">
        <div className="flex items-center space-x-8">
          <Link href="/" className="flex items-center space-x-2 hover:opacity-80 transition">
            <div className="w-8 h-8 rounded-full bg-white text-black flex items-center justify-center font-extrabold text-sm font-mono">
              ⬡
            </div>
            <span className="text-xl font-bold tracking-tight text-white">NEXUS</span>
          </Link>

          <nav className="hidden md:flex items-center space-x-6 text-sm font-medium text-slate-300">
            <Link href="/docs" className="hover:text-white transition">Docs</Link>
            <Link href="/dashboard" className="hover:text-white transition">Control Plane</Link>
            <Link href="/topology" className="hover:text-white transition">Topology</Link>
            <Link href="/pricing" className="hover:text-white transition">Pricing</Link>
          </nav>
        </div>

        <div className="flex items-center space-x-4 text-sm font-medium">
          <a href="https://github.com/intermeshteam/intermesh" target="_blank" className="hidden md:block text-slate-300 hover:text-white transition">
            GitHub
          </a>
          <Link href="/auth" className="hidden sm:block text-slate-300 hover:text-white transition">
            Log in
          </Link>
          <Link href="/auth" className="px-4 py-2 rounded-full bg-white text-black hover:bg-slate-200 transition font-semibold">
            Start building
          </Link>
        </div>
      </header>

      {/* MAIN HERO SECTION (CENTERED, REACT.DEV STYLE) */}
      <main className="relative z-10 flex flex-col items-center justify-center pt-24 pb-16 px-6 text-center max-w-5xl mx-auto space-y-8">
        
        {/* VERSION BADGE */}
        <Link href="/docs" className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 hover:border-zinc-600 transition cursor-pointer">
          <span className="flex h-2 w-2 rounded-full bg-cyan-400"></span>
          <span>v0.1.0-alpha available now</span>
          <ArrowRight className="w-3 h-3 text-zinc-500" />
        </Link>

        {/* MASSIVE HEADLINE */}
        <h1 className="text-5xl sm:text-6xl md:text-8xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 leading-[1.1]">
          The protocol for <br className="hidden md:block" />
          AI infrastructure.
        </h1>

        <p className="text-lg md:text-xl text-slate-400 max-w-2xl font-normal leading-relaxed">
          InterMesh is the open-source coordination protocol. Connect agents, models, and workflows into a unified, E2E encrypted network across any language or cloud.
        </p>

        {/* PILL BUTTONS */}
        <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4 pt-4">
          <Link href="/auth" className="w-full sm:w-auto px-8 py-3.5 rounded-full bg-white text-black font-semibold text-sm hover:bg-slate-200 transition shadow-[0_0_40px_rgba(255,255,255,0.2)] flex items-center justify-center space-x-2">
            <span>Start building</span>
          </Link>
          <Link href="/docs" className="w-full sm:w-auto px-8 py-3.5 rounded-full bg-zinc-900 border border-zinc-800 text-white font-semibold text-sm hover:bg-zinc-800 transition flex items-center justify-center space-x-2">
            <BookOpen className="w-4 h-4 text-slate-400" />
            <span>Read the Docs</span>
          </Link>
        </div>

      </main>

      {/* CODE EDITOR SHOWCASE (CENTERED WIDE) */}
      <section className="relative z-10 px-6 max-w-4xl mx-auto pb-24">
        <div className="bg-[#0C0D10] border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl">
          
          {/* Editor Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 py-3 border-b border-zinc-800/80 bg-[#12141A]">
            <div className="flex items-center space-x-1">
              <button 
                onClick={() => setActiveTab('callable')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition ${activeTab === 'callable' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
              >
                1-Line Function
              </button>
              <button 
                onClick={() => setActiveTab('decorator')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition ${activeTab === 'decorator' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
              >
                @Decorator
              </button>
              <button 
                onClick={() => setActiveTab('langchain')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition ${activeTab === 'langchain' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'}`}
              >
                LangChain
              </button>
            </div>
            <button 
              onClick={handleCopy} 
              className="hidden sm:flex items-center space-x-1.5 text-xs text-zinc-400 hover:text-white transition"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>

          {/* Editor Body */}
          <div className="p-6 font-mono text-sm leading-relaxed overflow-x-auto text-slate-300">
            <pre suppressHydrationWarning>
              <code>{snippets[activeTab]}</code>
            </pre>
          </div>

        </div>

        {/* Install Command */}
        <div className="mt-8 flex justify-center">
          <div className="inline-flex items-center space-x-3 bg-zinc-900 border border-zinc-800 rounded-full px-5 py-2 font-mono text-sm">
            <Terminal className="w-4 h-4 text-zinc-500" />
            <span className="text-zinc-300">pip install <span className="text-white font-bold">nexus-sdk</span></span>
          </div>
        </div>
      </section>

      {/* FEATURE GRID */}
      <section className="relative z-10 border-t border-zinc-900 bg-[#0A0A0C] py-24 px-6">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          
          <div className="space-y-4">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <Lock className="w-5 h-5 text-cyan-400 stroke-[1.5]" />
            </div>
            <h3 className="text-lg font-bold text-white">End-to-End Encryption</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Hybrid RSA-2048-OAEP & AES-256-GCM client-side encryption. The InterMesh Hub routes messages without ever reading plaintext payloads.
            </p>
          </div>

          <div className="space-y-4">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <Globe className="w-5 h-5 text-cyan-400 stroke-[1.5]" />
            </div>
            <h3 className="text-lg font-bold text-white">Cross-Language Mesh</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Native SDKs for Python and Node.js. A Python agent delegates tasks to a TypeScript worker transparently and securely.
            </p>
          </div>

          <div className="space-y-4">
            <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-cyan-400 stroke-[1.5]" />
            </div>
            <h3 className="text-lg font-bold text-white">Immutable Merkle Audit</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Cryptographically chained SHA-256 event log for SOC2, HIPAA, and financial compliance audits built-in.
            </p>
          </div>

        </div>
      </section>

      {/* FOOTER */}
      <footer className="relative z-10 border-t border-zinc-900 bg-[#08080A] py-12 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center text-sm text-slate-500">
          <div className="flex items-center space-x-2 font-semibold">
            <div className="w-5 h-5 rounded-full bg-slate-700 text-black flex items-center justify-center text-[8px] font-mono">⬡</div>
            <span>InterMesh Protocol © 2026</span>
          </div>
          <div className="flex items-center space-x-6 mt-4 md:mt-0 font-medium">
            <Link href="/terms" className="hover:text-slate-300 transition">Terms</Link>
            <Link href="/privacy" className="hover:text-white transition">Privacy</Link>
            <a href="https://github.com/intermeshteam/intermesh" target="_blank" className="hover:text-white transition">GitHub</a>
          </div>
        </div>
      </footer>

    </div>
  );
}
