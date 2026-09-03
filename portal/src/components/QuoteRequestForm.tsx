'use client';

import React, { useState } from 'react';
import { Check, Loader2 } from 'lucide-react';

/**
 * Quote request form for /pricing.
 *
 * The only way to reach us before this was a public GitHub issue, which no
 * procurement department will use to discuss a contract — and which would
 * put a company's evaluation in the open.
 *
 * Nothing here takes a payment. An enterprise settles an invoice by bank
 * transfer against a purchase order, so the form gathers what an invoice
 * and a quote actually need, and the terms are stated next to it rather
 * than discovered later.
 */

const HAIRLINE = 'border-slate-200 dark:border-white/[0.07]';
const LABEL = 'text-xs font-medium text-slate-600 dark:text-slate-400';
const INPUT =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition ' +
  'placeholder:text-slate-400 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 ' +
  'dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:placeholder:text-slate-600 dark:focus:border-cyan-400';

type Status = 'idle' | 'sending' | 'sent';

export default function QuoteRequestForm() {
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setStatus('sending');

    const data = new FormData(event.currentTarget);
    const payload = Object.fromEntries(data.entries());

    try {
      const res = await fetch('/api/quote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const json = (await res.json().catch(() => ({}))) as { error?: string };
      if (!res.ok) {
        setError(json.error ?? 'Could not send the request.');
        setStatus('idle');
        return;
      }
      setStatus('sent');
    } catch {
      setError('Network error. Please try again.');
      setStatus('idle');
    }
  };

  if (status === 'sent') {
    return (
      <div className={`rounded-2xl border p-8 ${HAIRLINE}`}>
        <div className="flex items-start gap-3">
          <Check className="mt-0.5 h-5 w-5 shrink-0 text-cyan-600 dark:text-cyan-400" />
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-900 dark:text-white">Request received.</p>
            <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              You will get a written quote by email, with the bank details and the terms on the
              invoice itself. No confirmation email is sent from here — that would let anyone make
              this domain mail a stranger.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const busy = status === 'sending';

  return (
    <form onSubmit={submit} className={`space-y-5 rounded-2xl border p-8 ${HAIRLINE}`}>
      {/* Hidden from people, not from bots. Never rendered as display:none
          alone, which some form-fillers now skip. */}
      <div className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden" aria-hidden>
        <label htmlFor="website">Leave this empty</label>
        <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="company">
            Company <span className="text-cyan-600 dark:text-cyan-400">*</span>
          </label>
          <input id="company" name="company" required maxLength={120} className={INPUT} placeholder="Acme Bank" />
        </div>
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="contactName">
            Your name <span className="text-cyan-600 dark:text-cyan-400">*</span>
          </label>
          <input id="contactName" name="contactName" required maxLength={120} className={INPUT} placeholder="Ada Lovelace" />
        </div>
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="email">
            Work email <span className="text-cyan-600 dark:text-cyan-400">*</span>
          </label>
          <input id="email" name="email" type="email" required maxLength={200} className={INPUT} placeholder="ada@acme.com" />
        </div>
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="country">
            Country of the invoicing entity <span className="text-cyan-600 dark:text-cyan-400">*</span>
          </label>
          <input id="country" name="country" required maxLength={80} className={INPUT} placeholder="Germany" />
        </div>
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="agentCount">
            Agents expected
          </label>
          <input id="agentCount" name="agentCount" maxLength={40} className={INPUT} placeholder="around 200" />
        </div>
        <div className="space-y-1.5">
          <label className={LABEL} htmlFor="deployment">
            Deployment
          </label>
          <select id="deployment" name="deployment" defaultValue="undecided" className={INPUT}>
            <option value="undecided">Not decided yet</option>
            <option value="self-hosted">Self-hosted, with internet access</option>
            <option value="air-gapped">Closed network / air-gapped</option>
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <label className={LABEL} htmlFor="message">
          What are you trying to do?
        </label>
        <textarea
          id="message"
          name="message"
          rows={4}
          maxLength={4000}
          className={INPUT}
          placeholder="What the agents would coordinate, any compliance constraints, and the timeline you are working to."
        />
      </div>

      {error && (
        <p className="notranslate text-sm text-rose-600 dark:text-rose-400"
           translate="no" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        {/* Texte qui change en place : Google Traduction enveloppe le
            nœud, React ne le retrouve plus en le remplaçant, et la page
            entière tombe sur « une exception côté client s'est produite ».
            Soustraire ces nœuds-là à la traduction est le remède ciblé —
            marquer tout le formulaire priverait un lecteur francophone
            des libellés, ce qui coûte plus que ça ne rapporte. */}
        <span className="notranslate" translate="no">
          {busy ? 'Sending…' : 'Request a quote'}
        </span>
      </button>
    </form>
  );
}
