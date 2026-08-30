'use client';

import React from 'react';
import LegalShell, { LegalLink, LegalList, LegalSection } from '@/components/LegalShell';

export default function TermsPage() {
  return (
    <LegalShell title="Terms of Service" updated="26 August 2026">
      <LegalSection title="1. Acceptance of these terms">
        <p>
          By accessing InterMesh Protocol, the Control Plane, the SDKs, the CLI or any associated
          service (together, &ldquo;the Service&rdquo;), you agree to these Terms of Service. If you
          do not accept them, do not use the Service.
        </p>
      </LegalSection>

      <LegalSection title="2. What the Service is">
        <p>
          InterMesh is an open-source protocol and coordination infrastructure for AI agents. The
          Service includes:
        </p>
        <LegalList>
          <li>the Python and JavaScript/TypeScript SDKs;</li>
          <li>the developer CLI;</li>
          <li>the self-hosted hub and the Control Plane;</li>
          <li>Enterprise features (quotas, licensing, audit, RBAC) according to your plan.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="3. Accounts and access">
        <p>
          You are responsible for keeping your credentials, API keys and license keys confidential.
          Any activity carried out through your account or your keys is treated as yours. Tell us
          without delay if you believe either has been used without your authorization.
        </p>
      </LegalSection>

      <LegalSection title="4. Free, Pro and Enterprise plans">
        <p>
          The Free plan is limited to a maximum of 10 concurrently active agents, unless a license
          says otherwise. The Pro and Enterprise plans unlock additional quotas and features as set
          out on the Pricing page and in your applicable contract.
        </p>
      </LegalSection>

      <LegalSection title="5. Permitted and prohibited use">
        <p>You agree to use the Service lawfully and responsibly. You must not:</p>
        <LegalList>
          <li>circumvent quotas, licensing, access controls or security mechanisms;</li>
          <li>use the Service for illegal, fraudulent or harmful activity;</li>
          <li>disrupt the infrastructure, attack it, or reverse engineer it with malicious intent;</li>
          <li>resell the Service without written permission.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="6. Intellectual property">
        <p>
          The open-source InterMesh code is distributed under the Apache 2.0 license unless stated
          otherwise. Proprietary components — the commercial Control Plane, Enterprise features and
          the brand — remain the property of InterMesh Protocol and its rights holders.
        </p>
      </LegalSection>

      <LegalSection title="7. Data and privacy">
        <p>
          How personal data is handled is described in our{' '}
          <LegalLink href="/privacy">Privacy Policy</LegalLink>. For self-hosted deployments, you
          remain responsible for the data processed on your own infrastructure.
        </p>
      </LegalSection>

      <LegalSection title="8. Availability and support">
        <p>
          The Service is provided &ldquo;as is&rdquo;. Availability levels (SLA) and support depend
          on your plan. No guarantee of uninterrupted availability is given outside an Enterprise
          contractual commitment.
        </p>
      </LegalSection>

      <LegalSection title="9. Limitation of liability">
        <p>
          To the extent permitted by law, InterMesh Protocol is not liable for indirect damages,
          loss of data, loss of profit or business interruption arising from the use of, or the
          inability to use, the Service.
        </p>
      </LegalSection>

      <LegalSection title="10. Termination">
        <p>
          We may suspend or terminate access to the Service in the event of a breach of these terms,
          abusive use, non-payment or a security risk. You may stop using the Service at any time.
        </p>
      </LegalSection>

      <LegalSection title="11. Governing law">
        <p>
          These terms are governed by the laws applicable in the country where the publisher of the
          Service is established, subject to mandatory local provisions.
        </p>
      </LegalSection>

      <LegalSection title="12. Contact">
        <p>
          For any question about these terms:{' '}
          <span className="font-mono text-xs text-slate-900 dark:text-white">
            legal@intermeshprotocol.org
          </span>
        </p>
      </LegalSection>
    </LegalShell>
  );
}
