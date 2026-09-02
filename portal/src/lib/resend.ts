import { Resend } from 'resend';

/**
 * Server-only. `RESEND_API_KEY` carries no `NEXT_PUBLIC_` prefix on purpose —
 * unlike the Supabase anon key, this one is not safe for the browser to hold.
 * Import this file only from Route Handlers, Server Components or Server
 * Actions.
 */

let client: Resend | null = null;

export function isResendConfigured(): boolean {
  return Boolean(process.env.RESEND_API_KEY);
}

function getClient(): Resend {
  if (!process.env.RESEND_API_KEY) {
    throw new Error('Resend is not configured (RESEND_API_KEY is unset).');
  }
  if (!client) {
    client = new Resend(process.env.RESEND_API_KEY);
  }
  return client;
}

/** `from` must be on a domain verified in the Resend dashboard, or every send fails. */
function fromAddress(): string {
  return process.env.RESEND_FROM_EMAIL || 'InterMesh <onboarding@resend.dev>';
}

export interface TeamNotificationInput {
  to: string;
  orgName: string;
  role: string;
  inviterEmail: string;
  siteUrl: string;
}

/**
 * Tells someone they were added to a workspace — it does not grant them
 * access. There is no invitation-token/accept flow in this codebase yet:
 * `memberships` rows are created only for the person who signs up and
 * creates an organization (see supabase/account.ts), never for someone
 * added from Settings, which today only writes to the browser's
 * localStorage. Wording this as a working "click to join" link would be a
 * promise the product cannot keep, so the email states what actually
 * happened and points at the sign-in page rather than a magic link.
 */
export async function sendTeamNotificationEmail(input: TeamNotificationInput) {
  const { to, orgName, role, inviterEmail, siteUrl } = input;

  return getClient().emails.send({
    from: fromAddress(),
    to,
    subject: `You've been added to ${orgName} on InterMesh`,
    html: `
      <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: 0 auto; color: #0f172a;">
        <p style="font-size: 15px; line-height: 1.6;">
          <strong>${inviterEmail}</strong> added you to the
          <strong>${orgName}</strong> workspace on InterMesh as
          <strong>${role}</strong>.
        </p>
        <p style="font-size: 15px; line-height: 1.6;">
          Sign in with this email address to access it:
        </p>
        <p style="margin: 24px 0;">
          <a href="${siteUrl}/auth"
             style="display: inline-block; background: #0f172a; color: #fff; text-decoration: none;
                    padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 600;">
            Sign in to InterMesh
          </a>
        </p>
        <p style="font-size: 12px; color: #64748b; line-height: 1.6;">
          If you did not expect this, you can ignore this email.
        </p>
      </div>
    `,
  });
}

/** Where quote requests land. Never taken from the request body. */
export function salesAddress(): string | null {
  return process.env.INTERMESH_SALES_EMAIL || null;
}

export interface QuoteRequestInput {
  company: string;
  contactName: string;
  email: string;
  country: string;
  agentCount: string;
  deployment: string;
  message: string;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Delivers a quote request to our own inbox.
 *
 * The recipient comes from the environment, never from the caller. That is
 * the whole reason this route can be public while /api/invite requires a
 * session: an endpoint that mails an address supplied by the request is an
 * open relay, and ours would be sending from a domain we had to verify.
 *
 * Nothing is sent back to the address in the form either. A confirmation
 * email would let anyone make our domain deliver mail to a stranger by
 * typing their address here — the classic way a contact form becomes a
 * spam vector. The page confirms on screen instead.
 */
export async function sendQuoteRequestEmail(input: QuoteRequestInput) {
  const to = salesAddress();
  if (!to) {
    throw new Error('Quote requests are not configured (INTERMESH_SALES_EMAIL is unset).');
  }

  const rows: [string, string][] = [
    ['Company', input.company],
    ['Contact', input.contactName],
    ['Email', input.email],
    ['Country', input.country],
    ['Agents expected', input.agentCount],
    ['Deployment', input.deployment],
  ];

  return getClient().emails.send({
    from: fromAddress(),
    to,
    // `replyTo` is what makes this usable: hitting reply in the mail client
    // answers the prospect rather than our own sending address.
    replyTo: input.email,
    subject: `Quote request — ${input.company}`,
    html: `
      <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 560px; margin: 0 auto; color: #0f172a;">
        <h2 style="font-size: 16px; margin: 0 0 16px;">Quote request</h2>
        <table style="border-collapse: collapse; font-size: 14px; width: 100%;">
          ${rows
            .map(
              ([label, value]) => `
            <tr>
              <td style="padding: 6px 12px 6px 0; color: #64748b; vertical-align: top; white-space: nowrap;">${label}</td>
              <td style="padding: 6px 0;"><strong>${escapeHtml(value)}</strong></td>
            </tr>`,
            )
            .join('')}
        </table>
        <p style="font-size: 14px; line-height: 1.6; white-space: pre-wrap; border-top: 1px solid #e2e8f0; margin-top: 16px; padding-top: 16px;">${escapeHtml(
          input.message,
        )}</p>
      </div>
    `,
  });
}
