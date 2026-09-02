import { NextResponse } from 'next/server';
import { isResendConfigured, salesAddress, sendQuoteRequestEmail } from '@/lib/resend';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Receives quote requests from /pricing.
 *
 * Unlike /api/invite this route is deliberately public — a prospect
 * evaluating the product has no account yet, and demanding one before they
 * can ask a price would lose exactly the customer we want. What makes that
 * safe is that the recipient is fixed in the environment: the request body
 * cannot redirect the mail anywhere. See src/lib/resend.ts.
 *
 * Enterprises do not pay through a checkout page. Procurement raises a
 * purchase order and settles an invoice by bank transfer, which needs no
 * payment processor at all — a fact worth stating plainly, since the
 * merchant account this project would otherwise need is unavailable.
 */

const MAX = { company: 120, contactName: 120, email: 200, country: 80, agentCount: 40, deployment: 40, message: 4000 };
const DEPLOYMENTS = new Set(['self-hosted', 'air-gapped', 'undecided']);

/**
 * One request per address per window. In-memory, so it resets whenever the
 * serverless instance is recycled and is not shared between instances —
 * it blunts an accidental double-submit and casual abuse, nothing more.
 * Saying so here is cheaper than someone later mistaking it for real
 * protection; put a WAF or a durable store in front if that is needed.
 */
const WINDOW_MS = 60_000;
const seen = new Map<string, number>();

function rateLimited(key: string): boolean {
  const now = Date.now();
  // forEach rather than for..of: this project's tsconfig targets below
  // ES2015, where iterating a Map needs --downlevelIteration.
  const stale: string[] = [];
  seen.forEach((at, k) => {
    if (now - at > WINDOW_MS) stale.push(k);
  });
  stale.forEach((k) => seen.delete(k));
  const last = seen.get(key);
  if (last && now - last < WINDOW_MS) return true;
  seen.set(key, now);
  return false;
}

/**
 * `missing` and `too long` are kept apart on purpose. Folding both into one
 * null told someone who had pasted an over-long company name that the field
 * was required — which they could see it was, having just filled it in.
 */
type Field = { ok: true; value: string } | { ok: false; why: 'missing' | 'too-long'; name: string };

function field(source: Record<string, unknown>, name: keyof typeof MAX, required = true): Field {
  const raw = source[name];
  const value = typeof raw === 'string' ? raw.trim() : '';
  if (!value) return required ? { ok: false, why: 'missing', name } : { ok: true, value: '' };
  if (value.length > MAX[name]) return { ok: false, why: 'too-long', name };
  return { ok: true, value };
}

export async function POST(request: Request) {
  if (!isResendConfigured() || !salesAddress()) {
    return NextResponse.json(
      { error: 'Quote requests are not configured on this deployment.' },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }

  const source = (body ?? {}) as Record<string, unknown>;

  // Honeypot: a field hidden from people but not from the bots that fill
  // every input they find. Answering 200 rather than an error denies them
  // the signal that would let them tune around it.
  if (typeof source.website === 'string' && source.website.trim()) {
    return NextResponse.json({ ok: true });
  }

  const parsed = {
    company: field(source, 'company'),
    contactName: field(source, 'contactName'),
    email: field(source, 'email'),
    country: field(source, 'country'),
    agentCount: field(source, 'agentCount', false),
    deployment: field(source, 'deployment', false),
    message: field(source, 'message', false),
  };

  const tooLong = Object.values(parsed).find((f) => !f.ok && f.why === 'too-long');
  if (tooLong && !tooLong.ok) {
    return NextResponse.json({ error: `The ${tooLong.name} field is too long.` }, { status: 400 });
  }
  if (Object.values(parsed).some((f) => !f.ok)) {
    return NextResponse.json({ error: 'Company, name, email and country are required.' }, { status: 400 });
  }

  const { company, contactName, email, country, agentCount, deployment, message } = Object.fromEntries(
    Object.entries(parsed).map(([k, f]) => [k, f.ok ? f.value : '']),
  ) as Record<keyof typeof parsed, string>;

  if (!EMAIL_RE.test(email)) {
    return NextResponse.json({ error: 'That email address does not look valid.' }, { status: 400 });
  }
  if (deployment && !DEPLOYMENTS.has(deployment)) {
    return NextResponse.json({ error: 'Unknown deployment type.' }, { status: 400 });
  }

  if (rateLimited(email.toLowerCase())) {
    return NextResponse.json(
      { error: 'A request from this address was just received. Give it a minute.' },
      { status: 429 },
    );
  }

  try {
    await sendQuoteRequestEmail({
      company,
      contactName,
      email,
      country,
      agentCount: agentCount || 'not stated',
      deployment: deployment || 'not stated',
      message: message || '(no message)',
    });
  } catch (error) {
    // The address is released so a genuine retry is not blocked by our own
    // failure.
    seen.delete(email.toLowerCase());
    console.error('[quote] send failed', error);
    return NextResponse.json({ error: 'Could not send the request. Please try again.' }, { status: 502 });
  }

  return NextResponse.json({ ok: true });
}
