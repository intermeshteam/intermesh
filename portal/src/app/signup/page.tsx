'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Check,
  Eye,
  EyeOff,
  Github,
  Loader2,
  Lock,
  Network,
  Terminal,
} from 'lucide-react';

import AuthShell from '@/components/AuthShell';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import { signUp, toSlug } from '@/lib/supabase/account';

/**
 * Sign-up.
 *
 * The password is evaluated in this component and never leaves it — no
 * analytics call, no state lifted, no logging. Strength scoring is a hint for
 * the person typing, not a gate: the real guarantee has to live on the server
 * that eventually stores the hash.
 */

const MIN_PASSWORD = 10;

interface Strength {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  hint: string;
}

function scorePassword(pw: string): Strength {
  if (!pw) return { score: 0, label: '', hint: '' };

  const checks = [
    pw.length >= MIN_PASSWORD,
    pw.length >= 16,
    /[a-z]/.test(pw) && /[A-Z]/.test(pw),
    /\d/.test(pw),
    /[^\w\s]/.test(pw),
  ];
  const passed = checks.filter(Boolean).length;

  if (pw.length < MIN_PASSWORD) {
    return { score: 1, label: 'Too short', hint: `At least ${MIN_PASSWORD} characters.` };
  }
  if (passed <= 2) return { score: 2, label: 'Weak', hint: 'Add length, or mix in other character types.' };
  if (passed === 3) return { score: 3, label: 'Fair', hint: 'Longer beats more complicated.' };
  if (passed === 4) return { score: 4, label: 'Good', hint: '' };
  return { score: 4, label: 'Strong', hint: '' };
}

const BAR_TONES = [
  'bg-slate-200 dark:bg-white/10',
  'bg-red-500',
  'bg-amber-500',
  'bg-cyan-500',
  'bg-cyan-500',
];

const INPUT =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:placeholder:text-slate-600 dark:focus:border-cyan-400';

const LABEL = 'block text-xs font-medium text-slate-700 dark:text-slate-300';

const ASIDE = (
<>
          <h2 className="text-2xl font-bold leading-tight tracking-[-0.02em] text-slate-900 dark:text-white">
            Your agents are about to start
            <span className="bg-gradient-to-r from-cyan-600 to-violet-600 bg-clip-text text-transparent dark:from-cyan-300 dark:to-violet-300">
              {' '}
              talking to each other.
            </span>
          </h2>

          <ul className="space-y-5">
            {[
              { icon: Terminal, title: 'Any language, one command', body: 'A Go binary, a Node script or an HTTP service becomes an agent without an SDK.' },
              { icon: Network, title: 'Federation across companies', body: 'Peer with a partner hub over a verified TLS link and Ed25519 identity.' },
              { icon: Lock, title: 'Encrypted end to end', body: 'The hub routes ciphertext it cannot read, and every event chains into an audit log.' },
            ].map((f) => (
              <li key={f.title} className="flex gap-4">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/15 to-cyan-500/5 text-cyan-600 ring-1 ring-cyan-500/20 dark:text-cyan-300 dark:ring-cyan-400/20">
                  <f.icon className="h-[18px] w-[18px] stroke-[1.6]" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">{f.title}</div>
                  <div className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{f.body}</div>
                </div>
              </li>
            ))}
          </ul>

          <div className="rounded-xl border border-slate-800 bg-[#0B0C10] p-4 font-mono text-xs dark:border-white/10">
            <div><span className="text-cyan-400">$</span> <span className="text-slate-200">pip install intermesh</span></div>
            <div className="mt-1.5"><span className="text-cyan-400">$</span> <span className="text-slate-200">intermesh hub</span></div>
          </div>
        </>
);

export default function SignupPage() {
  const router = useRouter();

  const [name, setName] = useState('');
  const [org, setOrg] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSent, setConfirmSent] = useState(false);
  const configured = isSupabaseConfigured();

  const strength = useMemo(() => scorePassword(password), [password]);

  // `org_id` namespaces every agent this account registers, so it is worth
  // showing the normalised value rather than letting it be a surprise later.
  const orgSlug = useMemo(() => toSlug(org), [org]);

  const canSubmit =
    name.trim().length > 1 &&
    orgSlug.length > 1 &&
    /\S+@\S+\.\S+/.test(email) &&
    password.length >= MIN_PASSWORD &&
    accepted &&
    !isLoading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < MIN_PASSWORD) {
      setError(`Your password needs at least ${MIN_PASSWORD} characters.`);
      return;
    }
    if (!accepted) {
      setError('Please accept the terms to continue.');
      return;
    }
    if (!configured) {
      setError('Supabase is not configured on this deployment, so no account can be created.');
      return;
    }

    setIsLoading(true);
    const result = await signUp({
      email: email.trim(),
      password,
      fullName: name.trim(),
      orgName: org.trim(),
      orgSlug,
    });
    setIsLoading(false);

    if (!result.ok) {
      setError(result.error ?? 'Sign-up failed.');
      return;
    }
    if (result.needsEmailConfirmation) {
      setConfirmSent(true);
      return;
    }
    router.push('/dashboard');
  };


  // Real OAuth rather than a redirect that pretended to authenticate.
  const handleGithub = async () => {
    setError(null);
    if (!configured) {
      setError('Supabase is not configured on this deployment.');
      return;
    }
    const { signInWithGithub } = await import('@/lib/supabase/account');
    const result = await signInWithGithub();
    if (!result.ok) setError(result.error ?? 'GitHub sign-in failed.');
  };

  if (confirmSent) {
    return (
      <AuthShell
        title="Check your inbox"
        subtitle={`We sent a confirmation link to ${email}. Your organization is created the first time you sign in.`}
        aside={ASIDE}
        footer={
          <>
            Wrong address?{' '}
            <button onClick={() => setConfirmSent(false)} className="font-semibold text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300">
              Go back
            </button>
          </>
        }
      >
        <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 px-4 py-3.5 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
          The link confirms the address. Nothing is created until you follow it —
          if it does not arrive, check the spam folder before signing up again.
        </div>
        <Link href="/auth" className="flex w-full items-center justify-center rounded-lg bg-gradient-to-r from-cyan-500 to-violet-500 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 dark:from-cyan-400 dark:to-violet-400 dark:text-[#08080A]">
          Go to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Run a hub, connect your first agents, and delegate work across them in minutes."
      aside={ASIDE}
      footer={
        <>
          Already have an account?{' '}
          <Link href="/auth" className="font-semibold text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200">
            Sign in
          </Link>
        </>
      }
    >
      {!configured && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3.5 py-2.5 text-xs leading-relaxed text-amber-700 dark:text-amber-400">
          Supabase is not configured on this deployment, so accounts cannot be
          created or signed into. Set NEXT_PUBLIC_SUPABASE_URL and
          NEXT_PUBLIC_SUPABASE_ANON_KEY, then run supabase/schema.sql.
        </p>
      )}

      <button
        type="button"
        onClick={handleGithub}
        disabled={!configured}
        title={configured ? undefined : 'Supabase is not configured on this deployment'}
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:hover:bg-white/[0.06]"
      >
        <Github className="h-4 w-4" />
        <span>Continue with GitHub</span>
      </button>

      <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-600">
        <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
        <span className="font-mono uppercase tracking-widest">or</span>
        <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="name" className={LABEL}>Full name</label>
            <input
              id="name"
              name="name"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ada Lovelace"
              className={INPUT}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="org" className={LABEL}>Organization</label>
            <input
              id="org"
              name="organization"
              autoComplete="organization"
              value={org}
              onChange={(e) => setOrg(e.target.value)}
              placeholder="Acme Corp"
              className={INPUT}
            />
          </div>
        </div>

        {orgSlug && (
          <p className="-mt-2 font-mono text-xs text-slate-500">
            Agents will be namespaced <span className="text-cyan-600 dark:text-cyan-300">{orgSlug}/your_agent</span>
          </p>
        )}

        <div className="space-y-1.5">
          <label htmlFor="email" className={LABEL}>Work email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ada@acme.com"
            className={INPUT}
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className={LABEL}>Password</label>
          <div className="relative">
            <input
              id="password"
              name="password"
              type={reveal ? 'text' : 'password'}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`At least ${MIN_PASSWORD} characters`}
              className={`${INPUT} pr-11`}
            />
            <button
              type="button"
              onClick={() => setReveal((v) => !v)}
              aria-label={reveal ? 'Hide password' : 'Show password'}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 transition hover:text-slate-700 dark:hover:text-slate-200"
            >
              {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          {password && (
            <div className="space-y-1.5 pt-1">
              <div className="flex gap-1">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full transition ${
                      i <= strength.score ? BAR_TONES[strength.score] : BAR_TONES[0]
                    }`}
                  />
                ))}
              </div>
              <p className="text-xs text-slate-500">
                <span className="font-medium text-slate-700 dark:text-slate-300">{strength.label}</span>
                {strength.hint && <> — {strength.hint}</>}
              </p>
            </div>
          )}
        </div>

        <label className="flex cursor-pointer items-start gap-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          <span className="relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              className="peer h-4 w-4 cursor-pointer appearance-none rounded border border-slate-300 bg-white transition checked:border-cyan-500 checked:bg-cyan-500 dark:border-white/20 dark:bg-white/[0.03]"
            />
            <Check className="pointer-events-none absolute h-3 w-3 text-white opacity-0 peer-checked:opacity-100" />
          </span>
          <span>
            I agree to the{' '}
            <Link href="/terms" className="underline underline-offset-2 hover:text-slate-900 dark:hover:text-white">Terms</Link>
            {' '}and the{' '}
            <Link href="/privacy" className="underline underline-offset-2 hover:text-slate-900 dark:hover:text-white">Privacy Policy</Link>.
          </span>
        </label>

        {error && (
          <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/5 px-3.5 py-2.5 text-xs text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="flex w-full items-center justify-center rounded-lg bg-gradient-to-r from-cyan-500 to-violet-500 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 dark:from-cyan-400 dark:to-violet-400 dark:text-[#08080A]"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <span>Create account</span>}
        </button>
      </form>
    </AuthShell>
  );
}
