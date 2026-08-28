'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function DocsPage() {
  return (
    <div className="space-y-8 font-sans max-w-4xl mx-auto p-8">
      <Link href="/" className="inline-flex items-center space-x-2 text-xs text-slate-400 hover:text-white transition">
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Home</span>
      </Link>

      <div>
        <span className="text-xs font-mono text-slate-500 uppercase tracking-widest">RFC-001 SPECIFICATION</span>
        <h1 className="text-3xl font-extrabold text-white mt-1">InterMesh Core Protocol v1</h1>
        <p className="text-sm text-slate-400 mt-2">Official technical specification for universal AI agent coordination.</p>
      </div>

      <div className="bg-[#0D0E12] border border-slate-800 rounded-xl p-6 space-y-6 font-mono text-xs text-slate-300 leading-relaxed">
        <div>
          <h3 className="text-white font-bold text-sm mb-2 font-sans">1. InterMesh Message Envelope (intermesh/v1)</h3>
          <pre className="bg-[#08080A] p-4 rounded-lg text-slate-200 overflow-x-auto">
{`{
  "id": "UUID-v4 (Unique message ID)",
  "version": "intermesh/v1",
  "type": "register | message | request | response | task_submit | task_assign | task_update",
  "sender": "org_id/agent_name",
  "to": "org_id/target_agent",
  "content": "Ciphertext B64 (RSA-2048 + AES-256-GCM)",
  "timestamp": 1770000000.0,
  "token": "JWT_Signed_Token"
}`}
          </pre>
        </div>

        <div>
          <h3 className="text-white font-bold text-sm mb-2 font-sans">2. Cryptographic Security & E2E Encryption</h3>
          <p className="text-slate-400 font-sans text-xs leading-relaxed">
            All payload content is encrypted client-side using hybrid encryption: RSA-2048-OAEP for key exchange and AES-256-GCM for payload data. The InterMesh Hub routes messages without access to plaintext content.
          </p>
        </div>
      </div>
    </div>
  );
}
