'use client';

import React, { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

export const THEME_KEY = 'intermesh-theme';

/**
 * Light/dark switch.
 *
 * The class on <html> is set by an inline script in the root layout, before
 * the first paint — React cannot do it early enough, and mounting a toggle
 * that "corrects" the theme after hydration is exactly what produces the
 * dark flash on a light page.
 *
 * This component therefore reads the class rather than deciding it, and only
 * writes on an actual click. `mounted` guards the icon: rendering it during
 * SSR would guess a theme the server has no way of knowing.
 */
export default function ThemeToggle({ className = '' }: { className?: string }) {
  const [isDark, setIsDark] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'));
    setMounted(true);
  }, []);

  const toggle = () => {
    const next = !isDark;
    document.documentElement.classList.toggle('dark', next);
    try {
      localStorage.setItem(THEME_KEY, next ? 'dark' : 'light');
    } catch {
      /* private browsing: the choice simply does not persist */
    }
    setIsDark(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Light theme' : 'Dark theme'}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-900/[0.06] hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/[0.08] dark:hover:text-white ${className}`}
    >
      {/* Fixed-size box so the header does not shift when the icon appears. */}
      <span className="block h-[18px] w-[18px]">
        {mounted &&
          (isDark ? <Sun className="h-[18px] w-[18px] stroke-[1.6]" /> : <Moon className="h-[18px] w-[18px] stroke-[1.6]" />)}
      </span>
    </button>
  );
}
