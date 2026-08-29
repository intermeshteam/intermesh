'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, Github, Loader2 } from 'lucide-react';

import AuthShell from '@/components/AuthShell';

const INPUT =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:placeholder:text-slate-600 dark:focus:border-cyan-400';

const LABEL = 'block text-xs font-medium text-slate-700 dark:text-slate-300';

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      router.push('/dashboard');
    }, 1200);
  };

  return (
    <AuthShell
      title="Sign in to InterMesh"
      subtitle="Pick up where your agents left off."
      aside={
        <>
          <h2 className="text-2xl font-bold leading-tight tracking-[-0.02em] text-slate-900 dark:text-white">
            The coordination layer for
            <span className="bg-gradient-to-r from-cyan-600 to-violet-600 bg-clip-text text-transparent dark:from-cyan-300 dark:to-violet-300">
              {' '}
              agents that work together.
            </span>
          </h2>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            Discovery by capability, end-to-end encrypted delegation, a Merkle-chained
            audit log, and federation across organizations that do not trust each other.
          </p>
          <div className="rounded-xl border border-slate-800 bg-[#0B0C10] p-4 font-mono text-xs dark:border-white/10">
            <div><span className="text-cyan-400">$</span> <span className="text-slate-200">intermesh hub</span></div>
            <div className="mt-1.5"><span className="text-cyan-400">$</span> <span className="text-slate-200">intermesh serve --name bot --exec ./my-agent</span></div>
          </div>
        </>
      }
      footer={
        <>
          New to InterMesh?{' '}
          <Link href="/signup" className="font-semibold text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300 dark:hover:text-cyan-200">
            Create an account
          </Link>
        </>
      }
    >
      <button
        type="button"
        onClick={() => router.push('/dashboard')}
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-white dark:hover:bg-white/[0.06]"
      >
        <Github className="h-4 w-4" />
        <span>Continue with GitHub</span>
      </button>

      <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-600">
        <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
        <span className="font-mono uppercase tracking-widest">or</span>
        <div className="h-px flex-1 bg-slate-200 dark:bg-white/10" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-1.5">
          <label htmlFor="email" className={LABEL}>Work email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ada@acme.com"
            className={INPUT}
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className={LABEL}>Password</label>
            <Link href="/auth" className="text-xs text-cyan-600 transition hover:text-cyan-500 dark:text-cyan-300">
              Forgot?
            </Link>
          </div>
          <div className="relative">
            <input
              id="password"
              name="password"
              type={reveal ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
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
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="flex w-full items-center justify-center rounded-lg bg-gradient-to-r from-cyan-500 to-violet-500 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-50 dark:from-cyan-400 dark:to-violet-400 dark:text-[#08080A]"
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <span>Sign in</span>}
        </button>
      </form>
    </AuthShell>
  );
}
