import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

/**
 * Session refresh and route protection.
 *
 * Until now every Control Plane page was reachable without an account:
 * /dashboard rendered for anyone who typed the URL. Checking the session in a
 * React component would not fix that — the page would still be sent, then
 * hidden. This runs before the response exists.
 *
 * When Supabase is not configured the middleware steps aside entirely, so a
 * fresh clone still runs; the pages then say so themselves.
 */

const PROTECTED = ['/dashboard', '/topology', '/agents', '/keys', '/security', '/billing', '/settings'];
const AUTH_PAGES = ['/auth', '/signup'];

export async function middleware(request: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return NextResponse.next();

  let response = NextResponse.next({ request });

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // getUser() revalidates against Supabase. getSession() only decodes the
  // cookie, which a client could have forged — it must not gate anything.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;

  if (!user && PROTECTED.some((p) => path.startsWith(p))) {
    const to = request.nextUrl.clone();
    to.pathname = '/auth';
    to.searchParams.set('next', path);
    return NextResponse.redirect(to);
  }

  if (user && AUTH_PAGES.some((p) => path.startsWith(p))) {
    const to = request.nextUrl.clone();
    to.pathname = '/dashboard';
    to.search = '';
    return NextResponse.redirect(to);
  }

  return response;
}

export const config = {
  matcher: [
    // Everything except static assets and image files: the session cookie has
    // to be refreshed on real navigations, not on every icon request.
    '/((?!_next/static|_next/image|favicon.ico|icon.png|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
