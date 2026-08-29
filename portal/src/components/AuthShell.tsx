'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import InterMeshLogo from '@/components/InterMeshLogo';
import AngledBand from '@/components/AngledBand';
import ThemeToggle from '@/components/ThemeToggle';

/**
 * Two-column frame shared by sign-in and sign-up.
 *
 * The left column carries the argument, the right one the form. Keeping the
 * frame in one place is what stops the two pages drifting apart — the reason
 * the previous auth page was still in French and dark-only after the rest of
 * the site had moved on.
 */
export default function AuthShell({
  title,
  subtitle,
  aside,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  aside: React.ReactNode;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen bg-white font-sans text-slate-900 dark:bg-[#08080A] dark:text-slate-100">
      <div className="absolute right-6 top-6 z-20">
        <ThemeToggle />
      </div>

      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
        {/* Argument side */}
        <div className="relative hidden overflow-hidden border-r border-slate-200 bg-slate-50 lg:block dark:border-white/[0.07] dark:bg-white/[0.015]">
          <AngledBand variant="bottom-right" opacity={0.12} />

          <div className="relative flex h-full flex-col justify-between p-12">
            <Link
              href="/"
              className="inline-flex items-center gap-2.5 text-lg font-bold tracking-[0.18em] text-slate-900 transition hover:opacity-80 dark:text-white"
            >
              <InterMeshLogo className="h-5 w-5 shrink-0" />
              <span>INTERMESH</span>
            </Link>

            <div className="max-w-md space-y-8">{aside}</div>

            <p className="text-xs text-slate-500">
              Open source under Apache-2.0 · Self-hosted tier free up to 10 agents
            </p>
          </div>
        </div>

        {/* Form side */}
        <div className="flex flex-col">
          <div className="p-6 lg:p-8">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-900 dark:hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to home</span>
            </Link>
          </div>

          <div className="flex flex-1 items-center justify-center px-6 pb-12">
            <div className="w-full max-w-[400px] space-y-8">
              <div className="space-y-2">
                <h1 className="text-[1.75rem] font-bold leading-tight tracking-[-0.03em] text-slate-900 dark:text-white">
                  {title}
                </h1>
                <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">{subtitle}</p>
              </div>

              {children}

              <div className="border-t border-slate-200 pt-6 text-sm text-slate-600 dark:border-white/[0.07] dark:text-slate-400">
                {footer}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
