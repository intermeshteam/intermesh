'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BookOpen,
  CreditCard,
  FileText,
  Key,
  LayoutDashboard,
  Network,
  Settings,
  ShieldCheck,
  Users,
} from 'lucide-react';
import DashboardTopbar from '@/components/DashboardTopbar';
import InterMeshLogo from '@/components/InterMeshLogo';
import HubConnection from '@/components/HubConnection';
import { BORDER, CAPTION, SURFACE_BASE, SURFACE_CHROME } from '@/lib/ui';

const NAV = [
  {
    label: 'Control plane',
    items: [
      { name: 'Overview', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Topology', href: '/topology', icon: Network },
      { name: 'Agents', href: '/agents', icon: Users },
      { name: 'Summaries', href: '/resumes', icon: FileText },
      { name: 'API keys', href: '/keys', icon: Key },
      { name: 'Audit log', href: '/security', icon: ShieldCheck },
      { name: 'Billing', href: '/billing', icon: CreditCard },
    ],
  },
  {
    label: 'Workspace',
    items: [{ name: 'Settings', href: '/settings', icon: Settings }],
  },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    // `dark` is pinned here: these pages are written with dark colours in the
    // markup, so they would be unreadable under the light theme. Scoping the
    // class to this subtree keeps the public pages switchable.
    <div className={`dark flex min-h-screen font-sans text-slate-100 ${SURFACE_BASE}`}>
      <aside className={`fixed bottom-0 left-0 top-0 z-30 flex w-[248px] shrink-0 flex-col justify-between border-r ${BORDER} ${SURFACE_CHROME}`}>
        <div>
          <div className={`flex h-14 items-center gap-2.5 border-b px-5 ${BORDER}`}>
            <Link href="/" className="flex items-center gap-2.5 transition hover:opacity-80">
              <InterMeshLogo className="h-5 w-5 shrink-0" />
              <span className="text-sm font-bold tracking-[0.16em] text-white">INTERMESH</span>
            </Link>
          </div>

          <nav className="space-y-6 px-3 py-5">
            {NAV.map((group) => (
              <div key={group.label} className="space-y-1">
                <div className={`px-3 pb-1.5 ${CAPTION}`}>{group.label}</div>

                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      // The active row carries an accent bar and a tinted
                      // surface. A bold label alone is too weak to locate at a
                      // glance in a list of eight.
                      className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                        active
                          ? 'bg-cyan-500/[0.08] font-medium text-white'
                          : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-100'
                      }`}
                    >
                      {active && (
                        <span className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-gradient-to-b from-cyan-400 to-violet-400" />
                      )}
                      <Icon
                        className={`h-[17px] w-[17px] stroke-[1.6] transition ${
                          active ? 'text-cyan-300' : 'text-slate-400 group-hover:text-slate-300'
                        }`}
                      />
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        <div className={`space-y-3 border-t px-5 py-4 ${BORDER}`}>
          <Link
            href="/docs"
            className="flex items-center gap-2 text-xs text-slate-400 transition hover:text-slate-100"
          >
            <BookOpen className="h-3.5 w-3.5 stroke-[1.6]" />
            <span>Docs — RFC-001</span>
          </Link>

          <HubConnection />
        </div>
      </aside>

      <div className="ml-[248px] flex min-h-screen flex-1 flex-col">
        <DashboardTopbar />
        <main className="w-full max-w-[1400px] flex-1 p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}
