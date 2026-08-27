'use client';

import React, { useState, useEffect } from 'react';
import { Copy, Check, Play, Pause, RotateCcw, Terminal } from 'lucide-react';

type TabKey = 'intracompany' | 'b2b' | 'callable' | 'langchain';

interface CodeStep {
  lineIndex: number;
  log?: { time: string; level: 'INFO' | 'SUCCESS'; text: string };
}

interface SnippetData {
  filename: string;
  lines: string[];
  steps: CodeStep[];
}

const SNIPPETS: Record<TabKey, SnippetData> = {
  intracompany: {
    filename: 'acme_247_intake_to_print.py',
    lines: [
      '# 24/7 INTRA-COMPANY AUTOMATION: Data Intake Agent -> Print Agent',
      'from nexus_sdk import NexusAgent',
      '',
      'intake = NexusAgent(name="data_intake", org_id="acme")',
      'await intake.connect()',
      '',
      '# Delegate PDF print job to sister fulfillment agent 24/7',
      'result = await intake.submit_task(',
      '    title="Print Invoice INV-2026-1001",',
      '    assignee="acme/print_fulfillment",  # Internal print agent',
      '    input_data={"document_id": "INV-1001", "format": "PDF/A"}',
      ')',
      'print(result)  # -> {"status": "PRINTED", "pages": 3}'
    ],
    steps: [
      { lineIndex: 1, log: { time: '0.04s', level: 'INFO', text: 'Initializing 24/7 internal agent: acme/data_intake' } },
      { lineIndex: 4, log: { time: '0.18s', level: 'INFO', text: 'Connected to local Acme Hub ws://localhost:8765' } },
      { lineIndex: 7, log: { time: '0.35s', level: 'INFO', text: 'Submitting task -> acme/print_fulfillment' } },
      { lineIndex: 11, log: { time: '0.68s', level: 'SUCCESS', text: 'Document INV-1001 printed & archived 24/7' } }
    ]
  },
  b2b: {
    filename: 'acme_cross_company.py',
    lines: [
      '# 1. COMPANY A (Acme Corp - Paris Hub)',
      'from nexus_sdk import NexusAgent',
      '',
      'acme_agent = NexusAgent(name="audit_bot", org_id="acme", hub_url="ws://hub.acme.com")',
      'await acme_agent.connect()',
      '',
      '# Delegate encrypted task to Company B (Globex Inc - New York)',
      'result = await acme_agent.submit_task(',
      '    title="Cross-Company Audit",',
      '    assignee="globex/risk_engine",  # Target agent at Globex Inc',
      '    input_data={"portfolio_id": "998877"}',
      ')',
      'print(result)  # -> {"risk_score": 0.04, "status": "APPROVED"}'
    ],
    steps: [
      { lineIndex: 1, log: { time: '0.05s', level: 'INFO', text: 'Importing nexus_sdk v0.1.0' } },
      { lineIndex: 3, log: { time: '0.12s', level: 'INFO', text: 'Generated RSA-2048 keypair & identity fingerprint' } },
      { lineIndex: 4, log: { time: '0.28s', level: 'INFO', text: 'Connected to ws://hub.acme.com (JWT Authenticated)' } },
      { lineIndex: 7, log: { time: '0.45s', level: 'INFO', text: 'Encrypting payload with Globex RSA public key...' } },
      { lineIndex: 11, log: { time: '0.72s', level: 'INFO', text: 'Relaying E2E task via Hub Peering -> globex/risk_engine' } },
      { lineIndex: 12, log: { time: '0.94s', level: 'SUCCESS', text: 'Result: {"risk_score": 0.04, "status": "APPROVED"}' } }
    ]
  },
  callable: {
    filename: 'one_line_agent.py',
    lines: [
      'from nexus_sdk import NexusAgent',
      '',
      '# 1-LINE INTEGRATION: Turn any Python function into a secure Nexus Agent',
      'agent = NexusAgent.from_callable(',
      '    fn=my_existing_llm_function,',
      '    name="analyzer_bot",',
      '    capabilities=["summarize", "extract"]',
      ')',
      '',
      '# Auto-connects, negotiates JWT auth & E2E encryption',
      'await agent.connect()'
    ],
    steps: [
      { lineIndex: 0, log: { time: '0.04s', level: 'INFO', text: 'Nexus SDK adapters initialized' } },
      { lineIndex: 3, log: { time: '0.18s', level: 'INFO', text: 'Wrapped my_existing_llm_function into Agent(analyzer_bot)' } },
      { lineIndex: 10, log: { time: '0.42s', level: 'SUCCESS', text: 'Agent analyzer_bot live on ws://localhost:8765' } }
    ]
  },
  langchain: {
    filename: 'langchain_adapter.py',
    lines: [
      'from nexus_sdk import NexusAgent',
      '',
      '# 1-LINE LANGCHAIN ADAPTER: Connect your existing chains to the mesh',
      'agent = NexusAgent.from_langchain(',
      '    chain_or_runnable=my_crewai_crew,',
      '    name="research_crew",',
      '    capabilities=["web_research", "synthesis"]',
      ')',
      '',
      'await agent.connect()'
    ],
    steps: [
      { lineIndex: 0, log: { time: '0.05s', level: 'INFO', text: 'LangChain Runnable Adapter ready' } },
      { lineIndex: 3, log: { time: '0.22s', level: 'INFO', text: 'Hooked CrewAI team -> Agent(research_crew)' } },
      { lineIndex: 9, log: { time: '0.51s', level: 'SUCCESS', text: 'CrewAI mesh bridge active' } }
    ]
  }
};

export default function AnimatedCodeEditor() {
  const [activeTab, setActiveTab] = useState<TabKey>('intracompany');
  const [activeLine, setActiveLine] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);
  const [consoleLogs, setConsoleLogs] = useState<Array<{ time: string; level: 'INFO' | 'SUCCESS'; text: string }>>([]);

  const currentSnippet = SNIPPETS[activeTab];

  useEffect(() => {
    if (!isPlaying) return;

    const steps = currentSnippet.steps;
    const interval = setInterval(() => {
      setActiveLine((prev) => {
        const nextIndex = (prev + 1) % currentSnippet.lines.length;
        
        const stepMatch = steps.find((s) => s.lineIndex === nextIndex);
        if (stepMatch && stepMatch.log) {
          setConsoleLogs((logs) => [...logs, stepMatch.log!].slice(-5));
        }

        if (nextIndex === 0) {
          setConsoleLogs([]);
        }

        return nextIndex;
      });
    }, 1200);

    return () => clearInterval(interval);
  }, [isPlaying, activeTab, currentSnippet]);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    setActiveLine(0);
    setConsoleLogs([]);
    setIsPlaying(true);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(currentSnippet.lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRestart = () => {
    setActiveLine(0);
    setConsoleLogs([]);
    setIsPlaying(true);
  };

  return (
    <div className="bg-[#0D0E12]/95 border border-[#1F2028] rounded-xl overflow-hidden shadow-2xl backdrop-blur-md font-mono text-xs">
      
      {/* HEADER TABS & CONTROLS */}
      <div className="flex flex-wrap items-center justify-between px-4 py-3 border-b border-[#1F2028] bg-black/40 gap-2">
        <div className="flex items-center space-x-1 bg-black/50 p-1 rounded border border-zinc-800/80">
          <button
            onClick={() => handleTabChange('intracompany')}
            className={`px-2.5 py-1 rounded text-[11px] transition ${
              activeTab === 'intracompany' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            24/7 Internal (Intake ➔ Print)
          </button>
          <button
            onClick={() => handleTabChange('b2b')}
            className={`px-2.5 py-1 rounded text-[11px] transition ${
              activeTab === 'b2b' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            B2B (Acme ↔ Globex)
          </button>
          <button
            onClick={() => handleTabChange('callable')}
            className={`px-2.5 py-1 rounded text-[11px] transition ${
              activeTab === 'callable' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            1-Line Function
          </button>
          <button
            onClick={() => handleTabChange('langchain')}
            className={`px-2.5 py-1 rounded text-[11px] transition ${
              activeTab === 'langchain' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            LangChain
          </button>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="text-zinc-400 hover:text-white transition p-1"
            title={isPlaying ? 'Pause Animation' : 'Play Animation'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>
          
          <button
            onClick={handleRestart}
            className="text-zinc-400 hover:text-white transition p-1"
            title="Restart Animation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 text-zinc-400 hover:text-white transition"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* ANIMATED CODE BODY */}
      <div className="p-4 overflow-x-auto text-slate-300 leading-relaxed font-mono">
        {currentSnippet.lines.map((line, idx) => {
          const isActive = idx === activeLine;
          const isComment = line.trim().startsWith('#');

          return (
            <div
              key={idx}
              className={`flex items-center px-2 py-0.5 rounded transition-all duration-300 ${
                isActive
                  ? 'bg-cyan-500/10 border-l-2 border-[#00D4FF] text-white font-medium pl-2 shadow-[0_0_10px_rgba(0,212,255,0.1)]'
                  : 'border-l-2 border-transparent hover:bg-white/[0.02]'
              }`}
            >
              {/* Line Number */}
              <span className="w-8 shrink-0 text-slate-600 select-none text-[10px] text-right pr-3">
                {idx + 1}
              </span>

              {/* Line Code */}
              <span className={isComment ? 'text-slate-500 italic' : 'text-slate-200'}>
                {line}
              </span>
            </div>
          );
        })}
      </div>

      {/* LIVE EXECUTION CONSOLE AT THE BOTTOM */}
      <div className="border-t border-[#1F2028] bg-black/60 p-3 space-y-2">
        <div className="flex items-center justify-between text-[10px] text-zinc-500 uppercase tracking-wider font-mono">
          <span className="flex items-center space-x-1.5">
            <Terminal className="w-3 h-3 text-cyan-400" />
            <span>Execution Telemetry Console</span>
          </span>
          <span className="flex items-center space-x-1 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>REALTIME EXECUTION</span>
          </span>
        </div>

        <div className="min-h-[50px] space-y-1 font-mono text-[11px]">
          {consoleLogs.length === 0 ? (
            <div className="text-zinc-600 italic">Initializing step execution...</div>
          ) : (
            consoleLogs.map((log, i) => (
              <div key={i} className="flex items-center space-x-2 animate-in fade-in duration-300">
                <span className="text-zinc-500 font-mono text-[10px]">[{log.time}]</span>
                <span
                  className={`text-[9px] font-bold px-1 rounded ${
                    log.level === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-cyan-500/20 text-cyan-300'
                  }`}
                >
                  {log.level}
                </span>
                <span className="text-zinc-300">{log.text}</span>
              </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
}
