import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { isResendConfigured, sendTeamNotificationEmail } from '@/lib/resend';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ROLES = new Set(['Admin', 'Developer', 'Viewer']);

/**
 * Sends the "you were added to a workspace" notification (see
 * src/lib/resend.ts for what it does and does not promise). Requires a
 * signed-in caller — without that check, this route would be an open relay
 * anyone on the internet could use to send arbitrary email through our
 * Resend account.
 */
export async function POST(request: Request) {
  if (!isResendConfigured()) {
    return NextResponse.json({ error: 'Email sending is not configured on this deployment.' }, { status: 503 });
  }

  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user?.email) {
    return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }

  const { email, role, orgName } = (body ?? {}) as Record<string, unknown>;
  if (typeof email !== 'string' || !EMAIL_RE.test(email)) {
    return NextResponse.json({ error: 'Invalid email address.' }, { status: 400 });
  }
  if (typeof role !== 'string' || !ROLES.has(role)) {
    return NextResponse.json({ error: 'Invalid role.' }, { status: 400 });
  }
  if (typeof orgName !== 'string' || !orgName.trim()) {
    return NextResponse.json({ error: 'Missing organization name.' }, { status: 400 });
  }

  const siteUrl = request.headers.get('origin') || new URL(request.url).origin;

  try {
    await sendTeamNotificationEmail({
      to: email,
      orgName: orgName.trim(),
      role,
      inviterEmail: user.email,
      siteUrl,
    });
  } catch (err) {
    console.error('Resend send failed:', err);
    return NextResponse.json({ error: 'Failed to send the notification email.' }, { status: 502 });
  }

  return NextResponse.json({ ok: true });
}
