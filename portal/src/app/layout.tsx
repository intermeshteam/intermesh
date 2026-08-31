import './globals.css';
import React from 'react';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { BASE_URL } from './sitemap';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });

/**
 * The title used to be "INTERMESH — Control Plane" on every page, and the
 * description "AI Developer Infrastructure Control Plane". Control Plane is the
 * name of the signed-in dashboard, so the public site was advertising an
 * internal screen — and neither string contains a word anyone would search for.
 *
 * `metadataBase` matters more than it looks: without it, relative Open Graph
 * image paths resolve against nothing and social previews come out blank.
 */
export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: 'InterMesh — The coordination protocol for AI agents',
    template: '%s — InterMesh',
  },
  description:
    'Open-source protocol that lets AI agents find each other, delegate work, and negotiate across organizations — with end-to-end encryption and a verifiable audit log.',
  keywords: ['AI agents', 'agent protocol', 'multi-agent', 'agent coordination', 'open source', 'MCP', 'A2A'],
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: BASE_URL,
    siteName: 'InterMesh',
    title: 'InterMesh — The coordination protocol for AI agents',
    description:
      'Let AI agents discover each other, talk, and delegate work — across teams, and across the boundary between two organizations that do not trust each other.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'InterMesh — The coordination protocol for AI agents',
    description:
      'Open-source protocol for AI agents that work together, across organizations. End-to-end encrypted, with a verifiable audit log.',
  },
  robots: { index: true, follow: true },
};

/**
 * Applied before the first paint, so the page never renders in one theme and
 * then snaps to the other. It has to be inline and blocking for that reason:
 * a React effect runs after hydration, which is already too late.
 *
 * `theme-ready` is added afterwards so colour transitions only animate on a
 * real toggle, not on the initial application of the stored theme.
 */
const THEME_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('intermesh-theme');
    var dark = stored
      ? stored === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
  requestAnimationFrame(function () {
    document.documentElement.classList.add('theme-ready');
  });
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body
        className="min-h-screen bg-white font-sans text-slate-900 antialiased selection:bg-cyan-500/25 dark:bg-[#08080A] dark:text-slate-100"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
