import os

page_path = os.path.expanduser('~/nexus/portal/src/app/page.tsx')

landing_code = """'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Copy, Check, FileCode2, Zap } from 'lucide-react';
import NetworkBackground from '@/components/NetworkBackground';

export default function LandingPage() {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'callable' | 'decorator' | 'langchain'>('callable');

  const snippets = {
    callable: `from nexus_sdk import NexusAgent

# 1-LINE INTEGRATION: Turn any Python/AI function into a secure Nexus Agent
agent = NexusAgent.from_callable(
    fn=my_existing_llm_function,
    name="analyzer_bot",
    capabilities=["summarize", "extract"]
)

# Auto-connects, negotiates JWT auth & E2E encryption
await agent.connect()`,

    decorator: `from nexus_sdk import nexus_service

# 1-LINE DECORATOR: Publish any function as an E2E encrypted Nexus Agent
@nexus_service(name="translator_service", capabilities=["translate"])
def translate_tool(input_data):
    return {"translated_text": "Bonjour le monde"}

# Automatically registered & discoverable worldwide`,

    langchain: `from nexus_sdk import NexusAgent
from langchain_core.runnables import Runnable

# 1-LINE LANGCHAIN/CREWAI ADAPTER: Connect your existing chains to the mesh
agent = NexusAgent.from_langchain(
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
    <div className="relative min-h-screen bg-[#08080A] text-white overflow-hidden" suppressHydrationWarning>
      {/* Topology Background */}
      <NetworkBackground />

      {/* Readability Veil */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 1,
          background:
            'radial-gradient(ellipse 80% 70% at 50% 45%, rgba(8,8,10,0.55) 0%, rgba(8,8,10,0.78) 55%, rgba(8,8,10,0.92) 100%)',
        }}
      />

      {/* Main Container */}
      <div className="relative z-10 min-h-screen flex flex-col justify-between p-8 lg:p-12 max-w-[1500px] mx-auto font-sans">
        
        {/* TOPBAR */}
        <header className="flex items-center justify-between py-2">
          <Link 
            href="/" 
            className="text-xl font-extrabold tracking-widest hover:opacity-80 transition notranslate"
            translate="no"
          >
            N E X U S
          </Link>

          <nav className="hidden md:flex items-center space-x-8 text-xs text-slate-300 font-medium">
            <Link href="/dashboard" className="hover:text-white transition">Control Plane</Link>
            <Link href="/docs" className="hover:text-white transition">Docs (RFC-001)</Link>
            <Link href="/pricing" className="hover:text-white transition">Pricing</Link>
            <a href="https://github.com/mrlomemba-cmd/nexus" target="_blank" className="hover:text-white transition">GitHub</a>
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
        <main className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center my-auto py-12">
          
          {/* LEFT: TEXT CONTENT */}
          <div className="lg:col-span-6 space-y-8">
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded bg-white/5 border border-white/10 text-[11px] font-mono text-zinc-300">
              <Zap className="w-3 h-3 text-cyan-400 stroke-[1.5]" />
              <span>1-LINE INTEGRATION ADAPTERS READY</span>
            </div>

            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.95] text-white uppercase">
              BUILD. SCALE.<br />INTELLIGENCE.
            </h1>

            <p className="text-sm text-slate-200 max-w-md leading-relaxed">
              NEXUS is the open protocol for AI infrastructure. Connect any function, LangChain, or CrewAI agent in <strong>1 line of code</strong> into a unified, E2E encrypted network.
            </p>

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

          {/* RIGHT: CODE EDITOR SHOWCASING 1-LINE ADAPTERS */}
          <div className="lg:col-span-6">
            <div className="bg-[#0D0E12]/95 border border-[#1F2028] rounded-xl overflow-hidden shadow-2xl backdrop-blur-md">
              
              {/* CODE HEADER WITH TABS */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2028] text-xs text-slate-400 font-mono">
                <div className="flex items-center space-x-1 bg-black/40 p-1 rounded border border-zinc-800">
                  <button 
                    onClick={() => setActiveTab('callable')}
                    className={`px-2.5 py-1 rounded text-[11px] transition ${activeTab === 'callable' ? 'bg-zinc-800 text-white font-bold' : 'hover:text-white text-zinc-400'}`}
                  >
                    1-Line Function
                  </button>
                  <button 
                    onClick={() => setActiveTab('decorator')}
                    className={`px-2.5 py-1 rounded text-[11px] transition ${activeTab === 'decorator' ? 'bg-zinc-800 text-white font-bold' : 'hover:text-white text-zinc-400'}`}
                  >
                    @Decorator
                  </button>
                  <button 
                    onClick={() => setActiveTab('langchain')}
                    className={`px-2.5 py-1 rounded text-[11px] transition ${activeTab === 'langchain' ? 'bg-zinc-800 text-white font-bold' : 'hover:text-white text-zinc-400'}`}
                  >
                    LangChain
                  </button>
                </div>

                <button onClick={handleCopy} className="hover:text-white transition flex items-center space-x-1 text-xs">
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              {/* CODE BODY */}
              <div className="p-5 font-mono text-xs leading-relaxed overflow-x-auto text-slate-300">
                <pre suppressHydrationWarning>
                  <code>{snippets[activeTab]}</code>
                </pre>
              </div>

            </div>
          </div>

        </main>

        {/* FOOTER */}
        <footer className="grid grid-cols-2 md:grid-cols-4 gap-4 py-6 border-t border-slate-900/80 text-xs text-slate-400 font-medium">
          <div>1-Line Code Integration</div>
          <div className="border-l-0 md:border-l border-slate-900 md:pl-6">E2E Encrypted (RSA/AES)</div>
          <div className="border-l-0 md:border-l border-slate-900 md:pl-6">Python & Node.js SDKs</div>
          <div className="border-l-0 md:border-l border-slate-900 md:pl-6">LangChain & CrewAI Ready</div>
        </footer>

      </div>
    </div>
  );
}
