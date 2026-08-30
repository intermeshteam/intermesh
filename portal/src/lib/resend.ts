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
