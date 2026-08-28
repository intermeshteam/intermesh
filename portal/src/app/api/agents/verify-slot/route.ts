import { NextResponse } from 'next/server';

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
          message: `Free tier limit reached (${current_active_agents}/${max_allowed} active agents). Upgrade to Pro at https://intermeshprotocol.org/pricing to unlock up to 50 agents.`
        },
        { status: 403 }
      );
    }

    return NextResponse.json({
      allowed: true,
      current_count: requested_count,
      remaining_slots: max_allowed - requested_count
    });
  } catch (error: any) {
    return NextResponse.json({ allowed: false, error: error.message }, { status: 500 });
  }
}
