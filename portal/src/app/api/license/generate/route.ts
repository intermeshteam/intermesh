import { NextResponse } from 'next/server';
import crypto from 'crypto';

const SECRET_SIGNING_KEY = process.env.INTERMESH_LICENSE_SIGNING_KEY;

export async function POST(request: Request) {
  try {
    if (!SECRET_SIGNING_KEY) {
      return NextResponse.json(
        { success: false, error: 'INTERMESH_LICENSE_SIGNING_KEY is not configured on the server.' },
        { status: 500 }
      );
    }
    const body = await request.json();
    const { org_name, plan = 'free', max_agents = 10 } = body;

    const payload = {
      org_id: org_name || 'acme_corp',
      plan: plan,
      max_agents: plan === 'enterprise' ? 999999 : (plan === 'pro' ? 50 : max_agents),
      issued_at: Math.floor(Date.now() / 1000),
      expires_at: Math.floor(Date.now() / 1000) + (365 * 24 * 3600)
    };

    const rawPayload = JSON.stringify(payload);
    const signature = crypto.createHmac('sha256', SECRET_SIGNING_KEY).update(rawPayload).digest('hex');

    const licenseKey = `nx_lic_${Buffer.from(JSON.stringify({ ...payload, sig: signature })).toString('base64url')}`;

    return NextResponse.json({
      success: true,
      license_key: licenseKey,
      details: payload
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
