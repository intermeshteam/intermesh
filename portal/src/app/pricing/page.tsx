'use client';

import BrandName from '@/components/BrandName';
import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Check, Github, Terminal } from 'lucide-react';
import InterMeshLogo from '@/components/InterMeshLogo';
import ThemeToggle from '@/components/ThemeToggle';
import QuoteRequestForm from '@/components/QuoteRequestForm';

/**
 * This page used to advertise a $29/month "Pro Production" tier with an
 * "Upgrade to Pro" button that linked to /dashboard, a "Contact Sales" button
 * wired to nothing, and a "Managed Cloud Hub Option" that does not exist in any
 * form. None of it could be bought: there is no payment integration, and the
 * merchant account needed to add one is blocked for the time being.
 *
 * Everything the old table listed as paid — end-to-end encryption, federation,
 * the Merkle audit log — is in fact free and open source today. So the honest
 * page is also the stronger one, and it no longer needs a fake price to make
 * the point.
 */

const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const ALT_SURFACE = 'bg-slate-50 dark:bg-white/[0.015]';
const HEADING = 'text-slate-900 dark:text-white';
const BODY = 'text-slate-600 dark:text-slate-400';
const MUTED = 'text-slate-500 dark:text-slate-500';

const INCLUDED = [
  'Unlimited agents — the limit is your own machine, not a plan',
  'End-to-end encryption (RSA-2048-OAEP + AES-256-GCM)',
  'Hub-to-hub federation between organizations, over TLS',
  'Ed25519 federated identity',
  'Merkle-chained audit log',
  'Egress policies on what leaves your organization',
  'Python and JavaScript SDKs, plus the universal bridge',
  'The Control Plane you are looking at, pointed at your own hub',
];

export default function PricingPage() {
  return (
    <div
      className="min-h-screen bg-white font-sans text-slate-900 dark:bg-[#08080A] dark:text-slate-50"
      suppressHydrationWarning
    >
      <header className={`sticky top-0 z-50 border-b bg-white/80 backdrop-blur-xl dark:bg-[#08080A]/80 ${HAIRLINE}`}>
        <div className="mx-auto flex max-w-[900px] items-center justify-between px-6 py-4">
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

      <div className="mx-auto max-w-[900px] space-y-12 px-6 py-12">
        <Link
          href="/"
          className={`inline-flex items-center gap-2 text-xs transition hover:text-slate-900 dark:hover:text-white ${MUTED}`}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to home</span>
        </Link>

        <div className="space-y-4">
          <h1 className={`text-[2.4rem] font-bold leading-[1.1] tracking-[-0.03em] sm:text-[3rem] ${HEADING}`}>
            Free, and open source.
          </h1>
          <p className={`max-w-2xl text-lg leading-relaxed ${BODY}`}>
            There is no paid plan yet — not a free tier with things held back, but genuinely everything,
            under Apache&nbsp;2.0. You run the hub on your own infrastructure, so there is no per-agent
            cost for us to pass on to you.
          </p>
        </div>

        <div className={`rounded-2xl border p-8 ${HAIRLINE} ${ALT_SURFACE}`}>
          <div className="flex flex-wrap items-baseline gap-3">
            <span className={`text-4xl font-bold ${HEADING}`}>$0</span>
            <span className={`text-sm ${MUTED}`}>self-hosted · Apache 2.0 · no account required</span>
          </div>

          <ul className="mt-8 grid grid-cols-1 gap-x-8 gap-y-3.5 sm:grid-cols-2">
            {INCLUDED.map((item) => (
              <li key={item} className={`flex items-start gap-2.5 text-sm leading-relaxed ${BODY}`}>
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-600 dark:text-cyan-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <div className={`mt-8 flex flex-wrap items-center gap-3 border-t pt-6 ${HAIRLINE}`}>
            <div
              className={`flex items-center gap-2.5 rounded-lg border px-3.5 py-2 font-mono text-sm ${HAIRLINE} ${HEADING}`}
            >
              <Terminal className="h-3.5 w-3.5 shrink-0 text-cyan-600 dark:text-cyan-400" />
              pip install intermesh
            </div>
            <a
              href="https://github.com/intermeshteam/intermesh"
              target="_blank"
              rel="noreferrer"
              className={`inline-flex items-center gap-2 text-sm font-medium transition hover:text-slate-900 dark:hover:text-white ${BODY}`}
            >
              <Github className="h-4 w-4" />
              Read the source
            </a>
          </div>
        </div>

        <div className={`space-y-4 border-t pt-10 ${HAIRLINE}`}>
          <h2 className={`text-xl font-semibold ${HEADING}`}>Is there a hosted version?</h2>
          <p className={`max-w-2xl text-sm leading-relaxed ${BODY}`}>
            Not today. The Control Plane is hosted, but it is a client for the hub you run yourself —
            your browser connects to it directly, and no agent traffic passes through our servers.
            That is what keeps this free, and it is also why your payloads stay on your own
            infrastructure.
          </p>
          <p className={`max-w-2xl text-sm leading-relaxed ${BODY}`}>
            A managed hub and team features are the obvious next step, and they will be paid. They do
            not exist yet, so there is nothing to sell you and no waitlist to put you on. When that
            changes it will be announced on the repository.
          </p>
        </div>

        <div id="enterprise" className={`space-y-6 border-t pt-10 ${HAIRLINE}`}>
          <div className="space-y-4">
            <h2 className={`text-xl font-semibold ${HEADING}`}>Buying this for a company</h2>
            <p className={`max-w-2xl text-sm leading-relaxed ${BODY}`}>
              The software above stays free and Apache&nbsp;2.0 — running it yourself costs nothing and
              needs no contract. What a company usually wants alongside it is different: a named
              contact, an agreed response time, help with a closed-network deployment, and someone
              answerable when something breaks at three in the morning. That is what a quote covers.
            </p>
            <ul className={`max-w-2xl space-y-2.5 text-sm leading-relaxed ${BODY}`}>
              <li className="flex items-start gap-2.5">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-600 dark:text-cyan-400" />
                <span>
                  <strong className={HEADING}>Invoice and bank transfer.</strong> There is no card
                  checkout, by choice as much as by circumstance — procurement raises a purchase
                  order and settles an invoice, which is how this is bought anyway.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-600 dark:text-cyan-400" />
                <span>
                  <strong className={HEADING}>Quoted before anything is signed.</strong> You get a
                  written quote with the scope and the terms on it. Nothing recurring starts by
                  itself.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-600 dark:text-cyan-400" />
                <span>
                  <strong className={HEADING}>What is not there yet.</strong> No SOC&nbsp;2, no
                  ISO&nbsp;27001, no independent penetration test. If your security review requires
                  one of those, say so in the form and we will tell you honestly where it stands
                  rather than waste a procurement cycle.
                </span>
              </li>
            </ul>
          </div>

          <QuoteRequestForm />
        </div>

        <div className={`border-t pt-10 ${HAIRLINE}`}>
          <p className={`text-sm leading-relaxed ${MUTED}`}>
            Questions, or a use case you want to discuss?{' '}
            <a
              href="https://github.com/intermeshteam/intermesh/issues"
              target="_blank"
              rel="noreferrer"
              className="font-medium text-cyan-600 underline underline-offset-4 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200"
            >
              Open an issue on GitHub
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
