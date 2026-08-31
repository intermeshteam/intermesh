import './globals.css';
import React from 'react';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });

export const metadata = {
  title: 'INTERMESH — Control Plane',
  description: 'AI Developer Infrastructure Control Plane',
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
