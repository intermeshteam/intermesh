'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Network,
  Users,
  Key,
  ShieldCheck,
  CreditCard,
  Settings,
  ChevronDown,
  BookOpen,
} from 'lucide-react';
import DashboardTopbar from '@/components/DashboardTopbar';
import InterMeshLogo from '@/components/InterMeshLogo';
import { HUB_URL } from '@/lib/hub';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { name: 'Overview & Quotas', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Live Topology', href: '/topology', icon: Network },
    { name: 'Agents Directory', href: '/agents', icon: Users },
    { name: 'API Keys & Licenses', href: '/keys', icon: Key },
    { name: 'Audit Log & RBAC', href: '/security', icon: ShieldCheck },
    { name: 'Billing & Plans', href: '/billing', icon: CreditCard },
  ];

  return (
    // `dark` is pinned here: the Control Plane pages are written with
    // hardcoded dark colours, so they would render unreadable under the light
    // theme. Scoping the class to this subtree keeps the toggle working on the
    // public pages without dragging a half-converted app along with it.
    <div className="dark min-h-screen bg-[#09090b] text-white flex font-sans notranslate" translate="no">
      {/* SIDEBAR STRIPE / VERCEL STYLE */}
      <aside className="w-64 fixed top-0 left-0 bottom-0 bg-[#0C0D10] border-r border-white/10 flex flex-col justify-between p-4 z-30 shrink-0">
        <div className="space-y-6">
          <Link href="/" className="flex items-center space-x-3 px-2 py-1 hover:opacity-80 transition">
            <InterMeshLogo className="w-6 h-6 shrink-0" />
            <span className="font-extrabold tracking-widest text-white text-sm">INTERMESH</span>
          </Link>

          <div className="bg-[#141519] border border-white/10 rounded-lg p-2.5 flex items-center justify-between text-xs cursor-pointer hover:border-slate-600 transition">
            <div className="flex items-center space-x-2.5">
              <div className="w-5 h-5 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-[10px] font-mono">
                A
              </div>
              <span className="font-medium text-slate-200">Local workspace</span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          </div>

          <nav className="space-y-1 text-xs font-medium">
            <div className="text-[10px] font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2">
              Control Plane
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg transition ${
                    isActive
                      ? 'bg-white/10 text-white font-semibold border border-white/10'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-4 h-4 stroke-[1.5] ${isActive ? 'text-white' : 'text-slate-400'}`} />
                  <span>{item.name}</span>
                </Link>
              );
            })}

            <div className="text-[10px] font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2 px-2 pt-4">
              Settings
            </div>
            <Link
              href="/settings"
              className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg transition ${
                pathname === '/settings'
                  ? 'bg-white/10 text-white font-semibold border border-white/10'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Settings className="w-4 h-4 text-slate-400 stroke-[1.5]" />
              <span>Workspace Settings</span>
            </Link>
          </nav>
        </div>

        <div className="space-y-3 pt-4 border-t border-white/10 text-xs text-slate-500 font-mono">
          <Link href="/docs" className="flex items-center space-x-2 text-slate-400 hover:text-white transition">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Docs (RFC-001)</span>
          </Link>
          {/* "OPERATIONAL" was a static label: it claimed a healthy system even
              with the hub down. The hub address is a fact; a status is not one
              unless something measured it. */}
          <div className="flex items-center justify-between text-[11px]">
            <span>HUB</span>
            <span className="font-mono text-slate-400">{HUB_URL.replace(/^wss?:\/\//, '')}</span>
          </div>
        </div>
      </aside>

      <div className="flex-1 ml-64 flex flex-col min-h-screen">
        <DashboardTopbar />
        <main className="flex-1 p-6 md:p-8 w-full max-w-[1400px]">{children}</main>
      </div>
    </div>
  );
}
