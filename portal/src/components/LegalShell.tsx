'use client';

import BrandName from '@/components/BrandName';
import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import InterMeshLogo from '@/components/InterMeshLogo';
import ThemeToggle from '@/components/ThemeToggle';

/**
 * Shared chrome for /terms and /privacy.
 *
 * Both pages previously carried their own copy of this markup, hardcoded to
 * the dark palette — so they stayed black under the light theme while every
 * other public page switched. Extracting the shell fixes it once rather than
 * twice, and keeps the two documents visually identical, which is what a
 * reader expects of a pair of legal pages.
 */

const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const HEADING = 'text-slate-900 dark:text-white';
const BODY = 'text-slate-600 dark:text-slate-400';
const MUTED = 'text-slate-500 dark:text-slate-500';

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className={`text-base font-semibold ${HEADING}`}>{title}</h2>
      {children}
    </section>
  );
}

export function LegalList({ children }: { children: React.ReactNode }) {
  return <ul className={`list-disc space-y-1.5 pl-5 ${BODY}`}>{children}</ul>;
}

export function LegalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="font-medium text-cyan-600 underline underline-offset-4 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200"
    >
      {children}
    </Link>
  );
}

export default function LegalShell({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="min-h-screen bg-white font-sans text-slate-900 dark:bg-[#08080A] dark:text-slate-50"
      suppressHydrationWarning
    >
      <header className={`sticky top-0 z-50 border-b bg-white/80 backdrop-blur-xl dark:bg-[#08080A]/80 ${HAIRLINE}`}>
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            className={`flex items-center gap-2.5 text-base font-bold tracking-[0.18em] transition hover:opacity-80 notranslate ${HEADING}`}
            translate="no"
          >
            <InterMeshLogo className="h-4 w-4 shrink-0" />
            <BrandName />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <div className="mx-auto max-w-3xl space-y-10 px-6 py-12">
        <div className="space-y-5">
          <Link
            href="/"
            className={`inline-flex items-center gap-2 text-xs transition hover:text-slate-900 dark:hover:text-white ${MUTED}`}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to home</span>
          </Link>

          <div>
            <div className={`mb-2 font-mono text-[11px] uppercase tracking-[0.18em] ${MUTED}`}>Legal</div>
            <h1 className={`text-3xl font-bold tracking-tight ${HEADING}`}>{title}</h1>
            <p className={`mt-2 text-sm ${MUTED}`}>Last updated: {updated}</p>
          </div>

          {/* Stated plainly rather than buried: these are templates shipped
              with an open-source project, not advice from a lawyer. */}
          <p className={`rounded-lg border px-4 py-3 text-xs leading-relaxed ${HAIRLINE} ${MUTED}`}>
            This document is a template provided with an open-source project. It has not been
            reviewed by a lawyer and is not legal advice. Have counsel review it before relying on
            it for a real deployment.
          </p>
        </div>

        <div className={`space-y-8 text-sm leading-relaxed ${BODY}`}>{children}</div>

        <div className={`flex items-center justify-between border-t pt-6 text-xs ${HAIRLINE} ${MUTED}`}>
          <span>© 2026 InterMesh Protocol</span>
          <div className="flex items-center gap-5">
            <Link href="/terms" className="transition hover:text-slate-900 dark:hover:text-slate-300">Terms</Link>
            <Link href="/privacy" className="transition hover:text-slate-900 dark:hover:text-slate-300">Privacy</Link>
            <Link href="/auth" className="transition hover:text-slate-900 dark:hover:text-slate-300">Log in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
