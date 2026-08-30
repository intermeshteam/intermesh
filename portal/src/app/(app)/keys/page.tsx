'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import { createKey, listKeys, revokeKey } from '@/lib/supabase/keys';
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

// The stored shape has no plaintext: a digest cannot be turned back into a
// key, so an existing key can be revoked but never shown again.
import type { StoredKey as ApiKey } from '@/lib/supabase/keys';

const STORAGE_KEY = 'intermesh_api_keys_v1';

// No seeded keys. Two fake ones used to sit here — `nx_live_acme_super_
// secret_key_123` and a staging twin, with invented creation dates and a
// "2 mins ago" last-used stamp. Displaying credential-shaped strings that
// authenticate nothing teaches people to trust the wrong thing.
const INITIAL_KEYS: ApiKey[] = [];

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

  const [loadError, setLoadError] = useState<string | null>(null);
  const configured = isSupabaseConfigured();

  const refresh = useCallback(async () => {
    if (!configured) return;
    const { keys: rows, error } = await listKeys();
    if (error) setLoadError(error);
    else {
      setLoadError(null);
      setKeys(rows);
    }
  }, [configured]);

  useEffect(() => {
    refresh();
  }, [refresh]);

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

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    if (!configured) {
      setLoadError('Supabase is not configured on this deployment.');
      return;
    }

    setCreating(true);
    const { secret, error } = await createKey(newKeyName, newKeyRole);
    setCreating(false);

    if (error || !secret) {
      setLoadError(error ?? 'Key creation failed.');
      return;
    }
    // Shown once, here. It is not stored anywhere it could be read back.
    setNewlyCreatedKey(secret);
    refresh();
  };

  const handleCloseCreateModal = () => {
    setIsCreateOpen(false);
    setNewKeyName('');
    setNewKeyRole('worker');
    setNewlyCreatedKey(null);
    setCopiedNewKey(false);
  };

  const handleRevokeKey = async () => {
    if (!deleteKey) return;
    const error = await revokeKey(deleteKey.id);
    if (error) setLoadError(error);
    setDeleteKey(null);
    refresh();
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
          All API keys use HMAC-SHA256 signatures for authenticating against the InterMesh Control Plane. Keep your keys secret.
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
                    Created {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at ? ` • last used ${new Date(k.last_used_at).toLocaleDateString()}` : ' • never used'}
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

              {/* Only the prefix survives creation — the rest is a digest. */}
              <div className="bg-[#08080A] border border-zinc-800 rounded-lg p-3 flex items-center justify-between font-mono text-xs">
                <div className="flex items-center space-x-3 min-w-0 pr-2">
                  <Lock className="w-4 h-4 text-zinc-500 shrink-0 stroke-[1.5]" />
                  <span className="text-zinc-300 truncate">{k.prefix}{'\u2026'}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded shrink-0 border ${k.revoked_at ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-zinc-800 text-zinc-300 border-zinc-700/50'}`}>
                    {k.revoked_at ? 'REVOKED' : 'ACTIVE'}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-600 shrink-0">shown once at creation</span>
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
