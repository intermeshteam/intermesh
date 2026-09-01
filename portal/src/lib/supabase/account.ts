'use client';

import { createClient } from '@/lib/supabase/client';

/**
 * Account operations shared by the sign-up and sign-in screens.
 *
 * Passwords are handed straight to Supabase and never stored, logged or
 * echoed anywhere in this codebase.
 */

export interface SignUpInput {
  email: string;
  password: string;
  fullName: string;
  orgName: string;
  orgSlug: string;
}

export interface AuthOutcome {
  ok: boolean;
  /** True when Supabase requires the address to be confirmed before signing in. */
  needsEmailConfirmation?: boolean;
  error?: string;
}

/** Normalises an organization name the way the SQL check constraint expects. */
export function toSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

export async function signUp(input: SignUpInput): Promise<AuthOutcome> {
  const supabase = createClient();

  const { data, error } = await supabase.auth.signUp({
    email: input.email,
    password: input.password,
    // With email confirmation on there is no session yet, so the
    // organization cannot be inserted here — RLS would reject it. The intent
    // is carried in user metadata and acted on at first sign-in, otherwise
    // what the person typed is simply lost between the form and the inbox.
    options: {
      data: {
        full_name: input.fullName,
        pending_org_name: input.orgName,
        pending_org_slug: input.orgSlug,
      },
    },
  });

  if (error) return { ok: false, error: error.message };

  if (!data.session) {
    return { ok: true, needsEmailConfirmation: true };
  }

  const orgError = await ensureOrganization(input.orgName, input.orgSlug);
  if (orgError) return { ok: false, error: orgError };

  return { ok: true };
}

export async function signIn(email: string, password: string): Promise<AuthOutcome> {
  const supabase = createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { ok: false, error: error.message };
  await ensurePendingOrganization();
  return { ok: true };
}

/**
 * Creates the organization requested at sign-up, once a session finally
 * exists. Runs after every sign-in: it is a no-op as soon as the account has
 * a membership, and it is the only thing standing between a confirmed account
 * and an org-less one that cannot create a single API key.
 */
export async function ensurePendingOrganization(): Promise<string | null> {
  const supabase = createClient();
  const { data } = await supabase.auth.getUser();
  const meta = data.user?.user_metadata ?? {};

  const name = (meta.pending_org_name as string) || (meta.full_name as string) || 'My workspace';
  const slug = (meta.pending_org_slug as string) || toSlug(name) || 'workspace';

  return ensureOrganization(name, slug);
}

export async function signOut(): Promise<void> {
  await createClient().auth.signOut();
}

/**
 * Creates the organization if the signed-in user has none.
 *
 * A trigger makes the creator its owner, so this is a single statement: doing
 * it in two calls leaves a window where an organization exists that nobody can
 * read, and the second call can simply fail.
 */
export async function ensureOrganization(name: string, slug: string): Promise<string | null> {
  const supabase = createClient();

  const { data: existing, error: readError } = await supabase
    .from('memberships')
    .select('org_id')
    .limit(1);

  if (readError) return readError.message;
  if (existing && existing.length > 0) return null;

  const { error } = await supabase
    .from('organizations')
    .insert({ name: name.trim(), slug });

  if (error) {
    if (error.code === '23505') {
      return `The organization slug "${slug}" is already taken.`;
    }
    return error.message;
  }
  return null;
}

/**
 * Identity providers this deployment offers.
 *
 * GitHub is for individual developers. Microsoft and Google are the
 * enterprise path: a company that runs Entra ID or Google Workspace already
 * has every employee in one directory, with joiners and leavers handled
 * there. That is the requirement behind "we need SSO" — not a particular
 * protocol, but not provisioning five thousand accounts by hand and having
 * a departure revoke access on its own.
 *
 * True SAML 2.0 is a separate matter: Supabase offers it on Pro and above,
 * configured through its CLI rather than the dashboard. The OAuth providers
 * below cover the large majority of companies and cost nothing, so they come
 * first. See docs/ENTERPRISE-SSO.md.
 */
export type OAuthProvider = 'github' | 'azure' | 'google';

interface ProviderSpec {
  id: OAuthProvider;
  label: string;
  /** Extra scopes the provider needs beyond Supabase's defaults. */
  scopes?: string;
}

export const OAUTH_PROVIDERS: ProviderSpec[] = [
  { id: 'github', label: 'GitHub' },
  // `email` is not implied for Entra ID; without it the session carries no
  // address and the organization lookup that follows sign-in has nothing to
  // match on.
  { id: 'azure', label: 'Microsoft', scopes: 'email' },
  { id: 'google', label: 'Google' },
];

/**
 * Which providers this Supabase project actually has enabled.
 *
 * Rendering a button for a disabled provider is worse than omitting it.
 * `signInWithOAuth` does not fail in that case — it only builds a URL and
 * navigates — so the browser leaves the site and lands on raw JSON from the
 * Supabase domain: `{"code":400,...,"msg":"Unsupported provider: provider is
 * not enabled"}`. There is no error for the caller to catch. Verified
 * against a live project.
 *
 * The settings endpoint answers with the anon key, which the browser already
 * holds, so asking is cheap and needs no privileged credential.
 */
export async function enabledProviders(): Promise<OAuthProvider[]> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return [];

  try {
    const res = await fetch(`${url}/auth/v1/settings`, { headers: { apikey: key } });
    if (!res.ok) return [];
    const data = (await res.json()) as { external?: Record<string, boolean> };
    const external = data.external ?? {};
    return OAUTH_PROVIDERS.filter((p) => external[p.id]).map((p) => p.id);
  } catch {
    // Réseau indisponible : on ne devine pas. L'appelant retombe sur le
    // formulaire e-mail plutôt que d'afficher des boutons incertains.
    return [];
  }
}

/**
 * Starts an OAuth sign-in. Supabase handles the redirect dance.
 *
 * Only call this for a provider {@link enabledProviders} has confirmed —
 * otherwise the visitor is sent to a JSON error page and never comes back.
 */
export async function signInWithProvider(provider: OAuthProvider): Promise<AuthOutcome> {
  const supabase = createClient();
  const spec = OAUTH_PROVIDERS.find((p) => p.id === provider);

  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
      ...(spec?.scopes ? { scopes: spec.scopes } : {}),
    },
  });
  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

/** @deprecated Use {@link signInWithProvider}. Kept so existing callers keep working. */
export async function signInWithGithub(): Promise<AuthOutcome> {
  return signInWithProvider('github');
}
