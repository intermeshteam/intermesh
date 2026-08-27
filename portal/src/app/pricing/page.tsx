'use client';

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
