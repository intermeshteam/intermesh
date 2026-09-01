'use client';

import React, { useEffect, useState } from 'react';
import { Github } from 'lucide-react';
import { OAUTH_PROVIDERS, type OAuthProvider } from '@/lib/supabase/account';

/**
 * Identity-provider buttons, shared by sign-in and sign-up.
 *
 * Both pages carried their own copy of a single GitHub button. Adding two
 * providers to each would have meant six blocks to keep in step.
 *
 * Microsoft and Google are the enterprise answer: a company running Entra ID
 * or Google Workspace already holds every employee in one directory, so
 * joiners and leavers are handled there rather than by hand here. Restricting
 * Entra ID to a single tenant is configured on the Supabase side — see
 * docs/ENTERPRISE-SSO.md.
 */

/** Lucide has no brand marks for these two; the paths are drawn inline. */
function MicrosoftMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 23 23" className={className} aria-hidden focusable="false">
      <path fill="#f25022" d="M1 1h10v10H1z" />
      <path fill="#7fba00" d="M12 1h10v10H12z" />
      <path fill="#00a4ef" d="M1 12h10v10H1z" />
      <path fill="#ffb900" d="M12 12h10v10H12z" />
    </svg>
  );
}

function GoogleMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden focusable="false">
      <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h11.8c-.5 2.7-2 5-4.4 6.6v5.5h7.1c4.1-3.8 6.6-9.4 6.6-16.1z" />
      <path fill="#34A853" d="M24 46c5.9 0 10.9-2 14.5-5.4l-7.1-5.5c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.6-3.9-12.3-9.1H4.3v5.7C7.9 41.1 15.4 46 24 46z" />
      <path fill="#FBBC05" d="M11.7 28.1c-.4-1.3-.7-2.7-.7-4.1s.2-2.8.7-4.1v-5.7H4.3C2.8 17.1 2 20.4 2 24s.8 6.9 2.3 9.8l7.4-5.7z" />
      <path fill="#EA4335" d="M24 10.8c3.2 0 6.1 1.1 8.4 3.3l6.3-6.3C34.9 4.1 29.9 2 24 2 15.4 2 7.9 6.9 4.3 14.2l7.4 5.7c1.7-5.2 6.6-9.1 12.3-9.1z" />
    </svg>
  );
}

const MARKS: Record<OAuthProvider, React.ComponentType<{ className?: string }>> = {
  github: ({ className }) => <Github className={className} />,
  azure: MicrosoftMark,
  google: GoogleMark,
};

export default function OAuthButtons({
  configured,
  onError,
}: {
  configured: boolean;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState<OAuthProvider | null>(null);
  const [available, setAvailable] = useState<OAuthProvider[] | null>(null);

  // Seuls les fournisseurs réellement activés sont proposés. Un bouton vers
  // un fournisseur désactivé n'échoue pas côté client : il emmène le
  // visiteur sur une page d'erreur JSON du domaine Supabase, dont il ne
  // revient pas.
  useEffect(() => {
    if (!configured) {
      setAvailable([]);
      return;
    }
    let cancelled = false;
    import('@/lib/supabase/account')
      .then((m) => m.enabledProviders())
      .then((list) => {
        if (!cancelled) setAvailable(list);
      })
      .catch(() => {
        if (!cancelled) setAvailable([]);
      });
    return () => {
      cancelled = true;
    };
  }, [configured]);

  const start = async (provider: OAuthProvider, label: string) => {
    if (!configured) {
      onError('Supabase is not configured on this deployment.');
      return;
    }
    setBusy(provider);
    // Imported lazily so a deployment without Supabase never loads the client.
    const { signInWithProvider } = await import('@/lib/supabase/account');
    const result = await signInWithProvider(provider);
    if (!result.ok) {
      // Reste pour les échecs réels du SDK — client non configuré, réseau.
      // Un fournisseur désactivé n'arrive pas ici : il est écarté en amont
      // par enabledProviders(), car le SDK ne signale pas ce cas.
      onError(result.error ?? `${label} sign-in failed.`);
      setBusy(null);
    }
    // On success the browser navigates away; leaving `busy` set avoids a
    // flash of the idle state during the redirect.
  };

  // Pendant l'interrogation, rien n'est affiché : faire apparaître des
  // boutons pour les retirer aussitôt est plus déroutant qu'une brève
  // absence.
  if (available === null || available.length === 0) return null;

  return (
    <div className="space-y-2.5">
      {OAUTH_PROVIDERS.filter((p) => available.includes(p.id)).map(({ id, label }) => {
        const Mark = MARKS[id];
        return (
          <button
            key={id}
            type="button"
            onClick={() => start(id, label)}
            disabled={!configured || busy !== null}
            title={configured ? undefined : 'Supabase is not configured on this deployment'}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:hover:bg-white/[0.06]"
          >
            <Mark className="h-4 w-4" />
            <span>{busy === id ? `Redirecting to ${label}…` : `Continue with ${label}`}</span>
          </button>
        );
      })}
    </div>
  );
}
