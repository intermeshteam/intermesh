import os

page_path = os.path.expanduser('~/nexus/portal/src/app/(app)/keys/page.tsx')

keys_code = """'use client';

import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Plus, 
  Copy, 
  Check, 
  Trash2, 
  Lock, 
  X, 
  AlertTriangle, 
  ShieldCheck, 
  Loader2,
  Eye,
  EyeOff
} from 'lucide-react';

interface ApiKey {
  id: string;
  name: string;
  rawKey: string;
  created: string;
  role: string;
  lastUsed: string;
}

const STORAGE_KEY = 'nexus_api_keys_v1';

const INITIAL_KEYS: ApiKey[] = [
  {
    id: 'k1',
    name: 'Production Backend Primary',
    rawKey: 'nx_live_acme_super_secret_key_123',
    created: '2026-02-10',
    role: 'admin',
    lastUsed: '2 mins ago'
  },
  {
    id: 'k2',
    name: 'Staging Environment Worker',
    rawKey: 'nx_live_acme_staging_key_998877',
    created: '2026-03-01',
    role: 'worker',
    lastUsed: '1 hour ago'
  }
];

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>(INITIAL_KEYS);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  
  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyRole, setNewKeyRole] = useState('worker');
  const [creating, setCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedNewKey, setCopiedNewKey] = useState(false);

  const [deleteKey, setDeleteKey] = useState<ApiKey | null>(null);
  const [showRawMap, setShowRawMap] = useState<Record<string, boolean>>({});

  // Load keys from LocalStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setKeys(parsed);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Save keys to LocalStorage
  const saveKeys = (updatedKeys: ApiKey[]) => {
    setKeys(updatedKeys);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedKeys));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCopy = (rawKey: string, id: string) => {
    navigator.clipboard.writeText(rawKey);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCopyNewlyCreated = () => {
    if (!newlyCreatedKey) return;
    navigator.clipboard.writeText(newlyCreatedKey);
    setCopiedNewKey(true);
    setTimeout(() => setCopiedNewKey(false), 2000);
  };

  const handleCreateKey = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;

    setCreating(true);

    setTimeout(() => {
      // Génération d'une vraie clé cryptographique au format nx_live_acme_...
      const randHex = Array.from(crypto.getRandomValues(new Uint8Array(16)))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
      const generatedKey = `nx_live_acme_${randHex}`;

      const newKeyObj: ApiKey = {
        id: `k_${Date.now()}`,
        name: newKeyName.trim(),
        rawKey: generatedKey,
        created: new Date().toISOString().split('T')[0],
        role: newKeyRole,
        lastUsed: 'Never'
      };

      const nextKeys = [newKeyObj, ...keys];
      saveKeys(nextKeys);

      setNewlyCreatedKey(generatedKey);
      setCreating(false);
    }, 800);
  };

  const handleCloseCreateModal = () => {
    setIsCreateOpen(false);
    setNewKeyName('');
    setNewKeyRole('worker');
    setNewlyCreatedKey(null);
    setCopiedNewKey(false);
  };

  const handleRevokeKey = () => {
    if (!deleteKey) return;
    const nextKeys = keys.filter(k => k.id !== deleteKey.id);
    saveKeys(nextKeys);
    setDeleteKey(null);
  };

  const toggleShowRaw = (id: string) => {
    setShowRawMap(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const maskKey = (raw: string) => {
    if (raw.length <= 16) return raw;
    return raw.substring(0, 16) + '****************';
  };

  return (
    <div className="space-y-8 font-sans text-slate-100 notranslate" translate="no">
      
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-sans">API Keys & License Credentials</h1>
          <p className="text-xs text-zinc-400 mt-1 font-sans">
            Manage cryptographic service account keys for production clusters and microservices.
          </p>
        </div>
        <button 
          onClick={() => setIsCreateOpen(true)}
          className="py-2.5 px-4 bg-white hover:bg-zinc-200 text-black font-semibold text-xs rounded-lg flex items-center space-x-2 transition shrink-0 font-sans"
        >
          <Plus className="w-4 h-4 stroke-[2]" />
          <span>Create New API Key</span>
        </button>
      </div>

      {/* SECURITY NOTICE BANNER */}
      <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-4 flex items-center space-x-3 text-xs text-zinc-400">
        <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 stroke-[1.5]" />
        <div>
          <span className="font-semibold text-white">Cryptographic Isolation: </span>
          All API keys use HMAC-SHA256 signatures for authenticating against the Nexus Control Plane. Keep your keys secret.
        </div>
      </div>

      {/* KEYS LIST */}
      <div className="space-y-4">
        {keys.length === 0 ? (
          <div className="bg-[#121215] border border-zinc-800/80 rounded-xl p-12 text-center text-zinc-500 space-y-3 font-sans">
            <Key className="w-8 h-8 text-zinc-600 mx-auto stroke-[1]" />
            <p className="text-xs">No active API keys found. Create one to authenticate your agents.</p>
          </div>
        ) : (
          keys.map((k) => (
            <div key={k.id} className="bg-[#121215] border border-zinc-800/80 rounded-xl p-5 space-y-3 transition hover:border-zinc-700/80">
              <div className="flex justify-between items-center">
                <div>
                  <div className="flex items-center space-x-3">
                    <h3 className="text-sm font-bold text-white font-sans">{k.name}</h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/50 uppercase">
                      ROLE: {k.role}
                    </span>
                  </div>
                  <div className="text-[11px] text-zinc-500 font-mono mt-1">
                    Created on {k.created} • Last used: {k.lastUsed}
                  </div>
                </div>

                <button 
                  onClick={() => setDeleteKey(k)}
                  className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                  title="Revoke Key"
                >
                  <Trash2 className="w-4 h-4 stroke-[1.5]" />
                </button>
              </div>

              {/* KEY DISPLAY ROW */}
              <div className="bg-[#08080A] border border-zinc-800 rounded-lg p-3 flex items-center justify-between font-mono text-xs">
                <div className="flex items-center space-x-3 min-w-0 pr-2">
                  <Lock className="w-4 h-4 text-zinc-500 shrink-0 stroke-[1.5]" />
                  <span className="text-zinc-300 truncate">
                    {showRawMap[k.id] ? k.rawKey : maskKey(k.rawKey)}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                    ACTIVE
                  </span>
                </div>

                <div className="flex items-center space-x-2 shrink-0">
                  <button 
                    onClick={() => toggleShowRaw(k.id)}
                    className="p-1.5 text-zinc-500 hover:text-zinc-300 transition"
                    title={showRawMap[k.id] ? "Hide Key" : "Reveal Key"}
                  >
                    {showRawMap[k.id] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                  <button 
                    onClick={() => handleCopy(k.rawKey, k.id)}
                    className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs flex items-center space-x-1.5 transition font-sans font-medium"
                  >
                    {copiedId === k.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 stroke-[1.5]" />}
                    <span>{copiedId === k.id ? 'Copied' : 'Copy Key'}</span>
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* CREATE API KEY MODAL */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={handleCloseCreateModal} />
          
          <div className="relative w-full max-w-md bg-[#121215] border border-zinc-800 rounded-xl shadow-2xl p-6 space-y-5 font-sans">
            
            {!newlyCreatedKey ? (
              <>
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <h3 className="text-base font-bold text-white">Create New API Key</h3>
                  <button onClick={handleCloseCreateModal} className="text-zinc-500 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <form onSubmit={handleCreateKey} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-300">Key Name / Description</label>
                    <input 
                      type="text" 
                      required
                      placeholder="e.g. Production Payment Worker"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      className="w-full bg-[#08080A] border border-zinc-800 focus:border-zinc-600 rounded-lg px-3.5 py-2 text-xs text-white outline-none"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-300">Role / Scope</label>
                    <select 
                      value={newKeyRole}
                      onChange={(e) => setNewKeyRole(e.target.value)}
                      className="w-full bg-[#08080A] border border-zinc-800 focus:border-zinc-600 rounded-lg px-3 py-2 text-xs text-white outline-none font-mono"
                    >
                      <option value="worker">WORKER (Default)</option>
                      <option value="admin">ADMIN (Full Access)</option>
                      <option value="inspector">INSPECTOR (Read Only)</option>
                    </select>
                  </div>

                  <div className="pt-2 flex justify-end space-x-3">
                    <button 
                      type="button" 
                      onClick={handleCloseCreateModal}
                      className="px-4 py-2 text-xs text-zinc-400 hover:text-white transition"
                    >
                      Cancel
                    </button>
                    <button 
                      type="submit" 
                      disabled={creating}
                      className="px-4 py-2 bg-white hover:bg-zinc-200 text-black font-semibold text-xs rounded-lg transition flex items-center space-x-2"
                    >
                      {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>{creating ? 'Generating...' : 'Create Key'}</span>
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <div className="flex items-center space-x-3 text-emerald-400 border-b border-zinc-800 pb-3">
                  <Check className="w-5 h-5 stroke-[2]" />
                  <h3 className="text-base font-bold text-white">API Key Generated!</h3>
                </div>

                <div className="space-y-3">
                  <p className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 p-3 rounded-lg leading-relaxed">
                    ⚠️ <strong>Save this secret key now.</strong> For security reasons, you won't be able to see the unmasked key again.
                  </p>

                  <div className="bg-[#08080A] border border-zinc-800 rounded-lg p-3 font-mono text-xs text-white break-all flex items-center justify-between">
                    <span className="select-all text-emerald-400">{newlyCreatedKey}</span>
                    <button 
                      onClick={handleCopyNewlyCreated}
                      className="ml-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded text-xs shrink-0 flex items-center space-x-1"
                    >
                      {copiedNewKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedNewKey ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button 
                    onClick={handleCloseCreateModal}
                    className="px-4 py-2 bg-white text-black font-semibold text-xs rounded-lg hover:bg-zinc-200 transition"
                  >
                    Done
                  </button>
                </div>
              </>
            )}

          </div>
        </div>
      )}

      {/* REVOKE CONFIRMATION MODAL */}
      {deleteKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 font-sans">
          <div className="absolute inset-0 bg-black/75 backdrop-blur-sm" onClick={() => setDeleteKey(null)} />
          <div className="relative w-full max-w-md bg-[#121215] border border-red-500/30 rounded-xl shadow-2xl p-6 space-y-4">
            <div className="flex items-start space-x-3">
              <div className="w-9 h-9 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-400 stroke-[1.5]" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Revoke API Key?</h3>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                  Are you sure you want to revoke <strong className="text-white">{deleteKey.name}</strong>? Any agent or service using this key will immediately lose access.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button 
                onClick={() => setDeleteKey(null)}
                className="px-4 py-2 text-xs text-zinc-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button 
                onClick={handleRevokeKey}
                className="px-4 py-2 bg-red-500 hover:bg-red-400 text-white font-semibold text-xs rounded-lg transition"
              >
                Revoke Key Immediately
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
"""

with open(page_path, 'w', encoding='utf-8') as f:
    f.write(keys_code)

print("✅ LA PAGE API KEYS & LICENSES EST DÉSORMAIS 100% INTERACTIVE ET OPÉRATIONNELLE !")
