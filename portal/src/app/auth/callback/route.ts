import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@/lib/supabase/server';

/**
 * OAuth landing point.
 *
 * Supabase sends the provider back here with a one-time code; exchanging it
 * sets the session cookies that middleware and server components read.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/dashboard';

  if (!code) {
    return NextResponse.redirect(`${origin}/auth?error=missing_code`);
  }

  const supabase = createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(`${origin}/auth?error=${encodeURIComponent(error.message)}`);
  }
  // A GitHub account arriving for the first time has no organization; the
  // client-side helper creates it right after the redirect lands.
  return NextResponse.redirect(`${origin}${next}`);
}
