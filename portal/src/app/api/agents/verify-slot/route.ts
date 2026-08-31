import { NextResponse } from 'next/server';

/**
 * Arithmetic helper for a caller that wants to cap its own agent count.
 *
 * It is not a quota gate, and must not be relied on as one: `max_allowed`
 * comes from the request body, so the caller picks its own limit and can raise
 * it at will. There is no session check and nothing is read from the database.
 *
 * The 403 used to read "Upgrade to Pro at https://intermeshprotocol.org/pricing
 * to unlock up to 50 agents" — a paid tier that does not exist, on a domain
 * that is not this site. Since InterMesh is self-hosted and open source, the
 * only real limit is the machine running the hub.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { current_active_agents, max_allowed = 15 } = body;

    const requested_count = current_active_agents + 1;

    if (requested_count > max_allowed) {
      return NextResponse.json(
        {
          allowed: false,
          error: 'AGENT_QUOTA_EXCEEDED',
          code: 403,
          message: `Caller-defined limit reached (${current_active_agents}/${max_allowed} active agents). This ceiling comes from your own request, not from a plan — raise max_allowed if your hub can take it.`,
        },
        { status: 403 },
      );
    }

    return NextResponse.json({
      allowed: true,
      current_count: requested_count,
      remaining_slots: max_allowed - requested_count,
    });
  } catch (error: any) {
    return NextResponse.json({ allowed: false, error: error.message }, { status: 500 });
  }
}
