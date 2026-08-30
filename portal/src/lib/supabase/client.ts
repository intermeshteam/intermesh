'use client';

import { createBrowserClient } from '@supabase/ssr';

/**
 * Supabase client for the browser.
 *
 * Only the anon key belongs here. It is published in the client bundle by
 * design, and it is safe there *because* Row Level Security decides what a
 * given session may read — never because the key is hard to find. If a table
 * has no policy, the anon key reads nothing; if its policies are wrong, the
 * key reads everything. The security lives in the SQL, not in this file.
 *
 * The service role key must never appear in this directory, nor behind any
 * NEXT_PUBLIC_ name: it bypasses RLS entirely.
 */
export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error(
      'Supabase is not configured. Copy .env.example to .env.local and set ' +
        'NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.',
    );
  }

  return createBrowserClient(url, anonKey);
}

/** True when both public variables are present. Lets the UI explain itself
 *  instead of throwing on a page a visitor has merely opened. */
export function isSupabaseConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}
