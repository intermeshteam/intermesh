'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Github, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import NexusLogo from '@/components/NexusLogo';

export default function AuthPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleAuth = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      router.push('/dashboard');
    }, 1500);
  };

  const handleGithubAuth = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      router.push('/dashboard');
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#08080A] flex flex-col font-sans text-slate-200">
      <div className="p-8">
        <Link href="/" className="inline-flex items-center space-x-2 text-xs text-slate-400 hover:text-white transition">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Retour à l&apos;accueil</span>
        </Link>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-[380px] space-y-8">
          <div className="text-center space-y-2">
            <div className="flex justify-center mb-6">
              <div className="w-12 h-12 rounded-xl bg-[#00D4FF]/10 border border-[#00D4FF]/40 flex items-center justify-center shadow-[0_0_15px_rgba(0,212,255,0.15)]">
                <NexusLogo className="w-8 h-8" />
              </div>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Connectez-vous à Nexus</h1>
            <p className="text-sm text-slate-400">
              Bienvenue. Saisissez vos identifiants pour accéder au plan de contrôle.
            </p>
          </div>

          <button
            onClick={handleGithubAuth}
            disabled={isLoading}
            className="w-full flex items-center justify-center space-x-3 py-2.5 px-4 bg-[#111827] hover:bg-[#1A2234] border border-slate-700/50 rounded-lg text-sm font-medium transition"
          >
            <Github className="w-4 h-4" />
            <span>Continuer avec GitHub</span>
          </button>

          <div className="flex items-center space-x-3 text-xs text-slate-600">
            <div className="flex-1 h-px bg-slate-800"></div>
            <span className="uppercase tracking-widest font-mono">OU</span>
            <div className="flex-1 h-px bg-slate-800"></div>
          </div>

          <form onSubmit={handleAuth} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="block text-xs font-medium text-slate-400">
                Adresse email
              </label>
              <input
                id="email"
                type="email"
                required
                placeholder="developer@acme.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[#111827] border border-slate-800 focus:border-[#00D4FF]/50 focus:ring-1 focus:ring-[#00D4FF]/50 rounded-lg px-4 py-2.5 text-sm outline-none transition placeholder:text-slate-600"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 bg-white hover:bg-slate-200 text-black rounded-lg text-sm font-semibold transition flex items-center justify-center"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-500" />
              ) : (
                <span>Poursuivre par courriel</span>
              )}
            </button>
          </form>

          <p className="text-center text-xs text-slate-500 pt-4 leading-relaxed">
            En vous connectant, vous acceptez nos{' '}
            <Link href="/terms" className="underline underline-offset-4 hover:text-slate-300">
              Conditions d&apos;utilisation
            </Link>{' '}
            et notre{' '}
            <Link href="/privacy" className="underline underline-offset-4 hover:text-slate-300">
              Politique de confidentialité
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
