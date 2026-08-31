'use client';

import React from 'react';
import { Check, Github } from 'lucide-react';
import { BORDER, CAPTION, CARD, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY } from '@/lib/ui';

/**
 * This page used to show three plans: $0, $29/month "Pro Production" with an
 * "Upgrade to Pro Plan" button, and an Enterprise tier claiming a dedicated
 * SLA, 24/7 phone support, and "Merkle Audit Log Export (SOC2 / HIPAA)".
 *
 * None of it was real. There is no payment integration behind the button, no
 * managed hub, no support rota — and SOC2 and HIPAA are audited certifications
 * that InterMesh does not hold. Naming them on a billing screen is not
 * optimistic positioning, it is a compliance claim a buyer could act on.
 *
 * Everything the paid tiers listed is in fact free and open source, so the page
 * now says that instead.
 */

const INCLUDED = [
  'Unlimited agents — bounded by your own machine, not by a plan',
  'End-to-end encryption (RSA-2048-OAEP + AES-256-GCM)',
  'Hub-to-hub federation between organizations, over TLS',
  'Ed25519 federated identity',
  'Merkle-chained audit log',
  'Egress policies on what leaves your organization',
  'Python and JavaScript SDKs, plus the universal bridge',
  'This Control Plane, pointed at the hub you run',
];

export default function BillingPage() {
  return (
    <div className="space-y-8 font-sans">
      <div className={`border-b pb-4 ${BORDER}`}>
        <h1 className={`text-xl font-bold tracking-tight ${TEXT_PRIMARY}`}>Plan</h1>
        <p className={`mt-1 text-xs ${TEXT_MUTED}`}>
          There is nothing to bill: InterMesh is open source and you host it yourself.
        </p>
      </div>

      <div className={`${CARD} p-6`}>
        <div className="flex flex-wrap items-baseline gap-3">
          <span className={`text-4xl font-bold tracking-tight ${TEXT_PRIMARY}`}>$0</span>
          <span className={`text-xs ${TEXT_MUTED}`}>self-hosted · Apache 2.0</span>
          <span className="ml-auto rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
            Active
          </span>
        </div>

        <ul className="mt-7 grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
          {INCLUDED.map((item) => (
            <li key={item} className={`flex items-start gap-2.5 text-xs leading-relaxed ${TEXT_SECONDARY}`}>
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 stroke-[1.8] text-cyan-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className={`${CARD} p-6`}>
        <div className={CAPTION}>Paid plans</div>
        <p className={`mt-3 max-w-2xl text-xs leading-relaxed ${TEXT_SECONDARY}`}>
          A managed hub and team features are the intended next step, and they will be paid. They do
          not exist yet, so there is no plan to upgrade to and nothing here to enter a card into.
        </p>
        <p className={`mt-3 max-w-2xl text-xs leading-relaxed ${TEXT_MUTED}`}>
          When that changes it will be announced on the repository, not through this screen.
        </p>
        <a
          href="https://github.com/intermeshteam/intermesh"
          target="_blank"
          rel="noreferrer"
          className={`mt-5 inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-xs font-medium transition hover:bg-white/[0.04] ${BORDER} ${TEXT_SECONDARY}`}
        >
          <Github className="h-3.5 w-3.5" />
          Follow the repository
        </a>
      </div>
    </div>
  );
}
