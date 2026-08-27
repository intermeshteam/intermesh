'use client';

import React from 'react';
import { Check, ArrowUpRight } from 'lucide-react';

export default function BillingPage() {
  return (
    <div className="space-y-8 font-sans text-slate-100 notranslate" translate="no">
      
      {/* HEADER */}
      <div className="border-b border-zinc-800/80 pb-4">
        <h1 className="text-xl font-bold tracking-tight text-white font-sans">Subscription Plans & Billing</h1>
        <p className="text-xs text-zinc-400 mt-1 font-sans">
          Scale your agent infrastructure smoothly from Developer to Enterprise.
        </p>
      </div>

      {/* PRICING CARDS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* PLAN 1 : DEVELOPER */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-6 flex flex-col justify-between space-y-6 hover:border-zinc-700 transition">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-semibold">Developer</div>
            <div className="text-4xl font-extrabold text-white mt-3 tracking-tight font-sans">
              $0 <span className="text-xs font-normal text-zinc-500 font-sans">/ month</span>
            </div>
            <p className="text-xs text-zinc-400 mt-2 font-sans leading-relaxed">
              Perfect for prototyping & personal AI agent projects.
            </p>

            <ul className="space-y-3 text-xs text-zinc-300 mt-6 font-sans">
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Up to 10 Active Concurrent Agents</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>E2E Encryption (RSA-2048 + AES-256-GCM)</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Self-Hosted Local Hub & CLI Tool</span>
              </li>
              <li className="flex items-center space-x-2.5 text-zinc-500">
                <Check className="w-4 h-4 text-zinc-600 stroke-[1.5] shrink-0" />
                <span>Community Support (GitHub)</span>
              </li>
            </ul>
          </div>

          <button className="w-full py-2 bg-zinc-900 border border-zinc-800 text-zinc-400 text-xs font-semibold rounded-lg cursor-default font-sans">
            Current Active Plan
          </button>
        </div>

        {/* PLAN 2 : PRO PRODUCTION */}
        <div className="bg-[#121215] border border-zinc-700 rounded-xl p-6 flex flex-col justify-between space-y-6 relative">
          <div className="absolute top-3.5 right-3.5 bg-white text-black text-[10px] font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 rounded">
            POPULAR
          </div>

          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-white font-semibold">Pro Production</div>
            <div className="text-4xl font-extrabold text-white mt-3 tracking-tight font-sans">
              $29 <span className="text-xs font-normal text-zinc-500 font-sans">/ month</span>
            </div>
            <p className="text-xs text-zinc-400 mt-2 font-sans leading-relaxed">
              For growing teams deploying production agent clusters.
            </p>

            <ul className="space-y-3 text-xs text-zinc-200 mt-6 font-sans">
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-white stroke-[1.5] shrink-0" />
                <span className="font-semibold text-white">Up to 50 Active Concurrent Agents</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-white stroke-[1.5] shrink-0" />
                <span>Managed Cloud Hub Option</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-white stroke-[1.5] shrink-0" />
                <span>30-Day Real-Time Telemetry Logs</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-white stroke-[1.5] shrink-0" />
                <span>Priority Email & Discord Support</span>
              </li>
            </ul>
          </div>

          <button className="w-full py-2 bg-white hover:bg-zinc-200 text-black font-semibold text-xs rounded-lg flex items-center justify-center space-x-1.5 transition font-sans">
            <span>Upgrade to Pro Plan</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* PLAN 3 : ENTERPRISE */}
        <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-6 flex flex-col justify-between space-y-6 hover:border-zinc-700 transition">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-semibold">Enterprise Custom</div>
            <div className="text-4xl font-extrabold text-white mt-3 tracking-tight font-sans">
              Custom
            </div>
            <p className="text-xs text-zinc-400 mt-2 font-sans leading-relaxed">
              For mission-critical infrastructure, compliance & SLA guarantees.
            </p>

            <ul className="space-y-3 text-xs text-zinc-300 mt-6 font-sans">
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Unlimited Active Agents</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Hub-to-Hub Federation Peering</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Merkle Audit Log Export (SOC2 / HIPAA)</span>
              </li>
              <li className="flex items-center space-x-2.5">
                <Check className="w-4 h-4 text-zinc-400 stroke-[1.5] shrink-0" />
                <span>Dedicated SLA & 24/7 Phone Support</span>
              </li>
            </ul>
          </div>

          <button className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition font-sans">
            Contact Enterprise Sales
          </button>
        </div>

      </div>
    </div>
  );
}
