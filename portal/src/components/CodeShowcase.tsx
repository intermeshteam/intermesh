'use client';

import React, { useState } from 'react';
import { Copy, Check, FileCode2 } from 'lucide-react';

/**
 * Static, tabbed code showcase.
 *
 * This replaces an animated editor that swept a highlight down the code and
 * streamed invented telemetry lines on a loop. Two reasons it went:
 * the motion pulled attention away from the code it was meant to sell, and
 * the fabricated logs — with fabricated timings — read as theatre to the
 * developers this page is addressed to. Real code, standing still, is the
 * stronger argument.
 */

type TabKey = 'intracompany' | 'b2b' | 'callable' | 'langchain';

interface Snippet {
  label: string;
  filename: string;
  lines: string[];
}

const SNIPPETS: Record<TabKey, Snippet> = {
  intracompany: {
    label: 'Same company',
    filename: 'intake_to_print.py',
    lines: [
      '# Data intake agent delegates to the print agent, same org',
      'from intermesh import InterMeshAgent',
      '',
      'intake = InterMeshAgent(name="data_intake", org_id="acme")',
      'await intake.connect()',
      '',
      'result = await intake.submit_task(',
      '    title="Print Invoice INV-2026-1001",',
      '    assignee="acme/print_fulfillment",',
      '    input_data={"document_id": "INV-1001", "format": "PDF/A"}',
      ')',
      '',
      'print(result)  # -> {"status": "PRINTED", "pages": 3}',
    ],
  },
  b2b: {
    label: 'Across companies',
    filename: 'cross_company.py',
    lines: [
      '# Acme delegates to an agent inside Globex, over a peered hub',
      'from intermesh import InterMeshAgent',
      '',
      'audit = InterMeshAgent(name="audit_bot", org_id="acme",',
      '                       hub_url="wss://hub.acme.com")',
      'await audit.connect()',
      '',
      'result = await audit.submit_task(',
      '    title="Cross-Company Audit",',
      '    assignee="globex/risk_engine",',
      '    input_data={"portfolio_id": "998877"}',
      ')',
      '',
      'print(result)  # -> {"risk_score": 0.04, "status": "APPROVED"}',
    ],
  },
  callable: {
    label: 'One line',
    filename: 'one_line_agent.py',
    lines: [
      '# Any Python function becomes an agent',
      'from intermesh import InterMeshAgent',
      '',
      'agent = InterMeshAgent.from_callable(',
      '    fn=my_existing_llm_function,',
      '    name="analyzer_bot",',
      '    capabilities=["summarize", "extract"],',
      ')',
      '',
      '# Connects, authenticates, and encrypts end to end',
      'agent.run()',
    ],
  },
  langchain: {
    label: 'LangChain',
    filename: 'langchain_adapter.py',
    lines: [
      '# An existing chain or crew, bridged as-is',
      'from intermesh import InterMeshAgent',
      '',
      'agent = InterMeshAgent.from_langchain(',
      '    chain_or_runnable=my_crewai_crew,',
      '    name="research_crew",',
      '    capabilities=["web_research", "synthesis"],',
      ')',
      '',
      'agent.run()',
    ],
  },
};

const TAB_ORDER: TabKey[] = ['intracompany', 'b2b', 'callable', 'langchain'];

export default function CodeShowcase() {
  const [activeTab, setActiveTab] = useState<TabKey>('intracompany');
  const [copied, setCopied] = useState(false);

  const snippet = SNIPPETS[activeTab];

  const handleCopy = () => {
    navigator.clipboard.writeText(snippet.lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-[#1F2028] bg-[#0D0E12]/95 font-mono text-xs shadow-2xl backdrop-blur-md">
      {/* Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1F2028] bg-black/40 px-3 py-2.5">
        <div className="flex items-center gap-1 rounded border border-zinc-800/80 bg-black/50 p-1">
          {TAB_ORDER.map((key) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`rounded px-2.5 py-1 text-[11px] transition ${
                activeTab === key
                  ? 'bg-cyan-500/15 font-bold text-white'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {SNIPPETS[key].label}
            </button>
          ))}
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-1 text-zinc-400 transition hover:text-white"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-cyan-400" /> : <Copy className="h-3.5 w-3.5" />}
          <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>

      {/* Code */}
      <div className="overflow-x-auto p-4 font-mono leading-relaxed text-slate-300">
        {snippet.lines.map((line, idx) => {
          const isComment = line.trim().startsWith('#');
          return (
            <div key={idx} className="flex px-2 py-0.5">
              <span className="w-8 shrink-0 select-none pr-3 text-right text-[10px] text-slate-600">
                {idx + 1}
              </span>
              <span className={isComment ? 'italic text-slate-500' : 'text-slate-200'}>
                {line || ' '}
              </span>
            </div>
          );
        })}
      </div>

      {/* Filename footer */}
      <div className="flex items-center gap-2 border-t border-[#1F2028] bg-black/40 px-4 py-2.5 text-[10px] uppercase tracking-wider text-zinc-500">
        <FileCode2 className="h-3 w-3 text-cyan-400" />
        <span>{snippet.filename}</span>
      </div>
    </div>
  );
}
