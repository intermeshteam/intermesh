'use client';

import { createClient } from '@/lib/supabase/client';

/**
 * API keys.
 *
 * The plaintext key exists exactly once — in the object returned by
 * `createKey`, so the interface can show it to the person who asked for it.
 * What reaches the database is a SHA-256 digest plus a short prefix, which is
 * the same shape the hub stores in `intermesh.apikeys`: enough to verify a
 * key, never enough to reveal one.
 *
 * That is why a lost key cannot be recovered, only revoked and replaced. It
 * is also why the previous version of this page — which kept full keys in
 * localStorage, seeded with two fake ones — had to go.
 */

export interface StoredKey {
  id: string;
  name: string;
  prefix: string;
  role: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

/** Same alphabet and shape the hub's own generator uses. */
function generateSecret(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `nx_live_${hex}`;
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function listKeys(): Promise<{ keys: StoredKey[]; error?: string }> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from('api_keys')
    .select('id, name, prefix, role, created_at, last_used_at, revoked_at')
    .order('created_at', { ascending: false });

  if (error) return { keys: [], error: error.message };
  return { keys: (data ?? []) as StoredKey[] };
}

export async function createKey(
  name: string,
  role: string,
): Promise<{ key?: StoredKey; secret?: string; error?: string }> {
  const supabase = createClient();

  const { data: membership, error: memberError } = await supabase
    .from('memberships')
    .select('org_id')
    .limit(1)
    .maybeSingle();

  if (memberError) return { error: memberError.message };
  if (!membership) return { error: 'This account does not belong to an organization yet.' };

  const secret = generateSecret();
  const digest = await sha256Hex(secret);

  const { data, error } = await supabase
    .from('api_keys')
    .insert({
      org_id: membership.org_id,
      name: name.trim(),
      key_digest: digest,
      prefix: secret.slice(0, 16),
      role,
    })
    .select('id, name, prefix, role, created_at, last_used_at, revoked_at')
    .single();

  if (error) return { error: error.message };
  return { key: data as StoredKey, secret };
}

/** Revoke rather than delete: the audit trail of what existed has value. */
export async function revokeKey(id: string): Promise<string | null> {
  const supabase = createClient();
  const { error } = await supabase
    .from('api_keys')
    .update({ revoked_at: new Date().toISOString() })
    .eq('id', id);
  return error ? error.message : null;
}
