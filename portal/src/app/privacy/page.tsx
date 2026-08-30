'use client';

import React from 'react';
import LegalShell, { LegalList, LegalSection } from '@/components/LegalShell';

/** Emphasised term inside a list item. */
function Term({ children }: { children: React.ReactNode }) {
  return <span className="font-medium text-slate-900 dark:text-slate-200">{children}</span>;
}

export default function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy" updated="26 August 2026">
      <LegalSection title="1. Introduction">
        <p>
          This Privacy Policy describes how InterMesh Protocol collects, uses and protects your
          information when you use the site, the Control Plane, the SDKs and associated services.
        </p>
      </LegalSection>

      <LegalSection title="2. What we collect">
        <p>Depending on how you use the Service, we may collect:</p>
        <LegalList>
          <li><Term>Account data</Term> — email, organization name, OAuth identifiers (for example GitHub);</li>
          <li><Term>Technical data</Term> — access logs, IP address, browser type, timestamps;</li>
          <li><Term>Product usage data</Term> — number of agents, quota events, key and license generation;</li>
          <li><Term>Billing data</Term> — payment information handled by our provider (for example Stripe).</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="3. What we do not collect by default">
        <p>
          In a self-hosted deployment, the contents of messages exchanged between agents stay on
          your infrastructure. Those payloads are encrypted end to end, so InterMesh does not have
          access to the plaintext of agent-to-agent communication.
        </p>
      </LegalSection>

      <LegalSection title="4. Why we use it">
        <p>We use your data to:</p>
        <LegalList>
          <li>provide, secure and improve the Service;</li>
          <li>authenticate users and manage access;</li>
          <li>enforce quotas and licensing;</li>
          <li>handle support, billing and compliance;</li>
          <li>prevent fraud, abuse and security incidents.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="5. Legal basis (GDPR)">
        <p>
          Where the GDPR applies, our processing rests on performance of the contract, legitimate
          interest (security, product improvement), and consent where consent is required.
        </p>
      </LegalSection>

      <LegalSection title="6. Sharing">
        <p>
          We do not sell your personal data. We may share certain information with providers that
          are strictly necessary — hosting, payment, transactional email, monitoring — under
          appropriate confidentiality obligations.
        </p>
      </LegalSection>

      <LegalSection title="7. Retention">
        <p>
          We keep data for as long as needed for the purposes described here and for our legal,
          accounting and security obligations. Technical logs may be kept for a limited period
          depending on the plan and on operational needs.
        </p>
      </LegalSection>

      <LegalSection title="8. Security">
        <p>
          We apply appropriate technical and organizational measures: encryption in transit, access
          controls, audit logs, and sound secret-management practice. No system is perfectly
          secure, so we also recommend hardening your own self-hosted environments.
        </p>
      </LegalSection>

      <LegalSection title="9. Your rights">
        <p>
          Depending on your jurisdiction, you may have rights of access, rectification, erasure,
          restriction, objection and portability. To exercise them, contact us at the address below.
        </p>
      </LegalSection>

      <LegalSection title="10. Cookies">
        <p>
          The site may use cookies that are essential to its operation (session, security) and,
          where applicable, audience-measurement cookies. You can configure your browser to limit
          non-essential cookies.
        </p>
      </LegalSection>

      <LegalSection title="11. International transfers">
        <p>
          If data is transferred outside your country, we put appropriate safeguards in place where
          the law requires it.
        </p>
      </LegalSection>

      <LegalSection title="12. Contact">
        <p>
          For any privacy request:{' '}
          <span className="font-mono text-xs text-slate-900 dark:text-white">
            privacy@intermeshprotocol.org
          </span>
        </p>
      </LegalSection>
    </LegalShell>
  );
}
