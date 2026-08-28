'use client';

import React, { useEffect, useState } from 'react';
import {
  Building2,
  Users,
  Webhook,
  ShieldAlert,
  Save,
  Plus,
  Copy,
  Check,
  Trash2,
  Globe,
  X,
  Loader2,
  Mail,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

type Member = {
  id: string;
  name: string;
  email: string;
  role: 'Owner' | 'Admin' | 'Developer' | 'Viewer';
  status: 'Active' | 'Pending';
};

type Toast = {
  type: 'success' | 'error' | 'info';
  message: string;
};

const STORAGE_KEY = 'intermesh_workspace_settings_v1';

const DEFAULT_MEMBERS: Member[] = [
  { id: 'm1', name: 'M. Lomemba', email: 'mrlomemba@gmail.com', role: 'Owner', status: 'Active' },
  { id: 'm2', name: 'Équipe DevOps', email: 'devops@acme.com', role: 'Admin', status: 'Active' },
  { id: 'm3', name: 'Auditeur de sécurité', email: 'security@acme.com', role: 'Viewer', status: 'Pending' },
];

export default function SettingsPage() {
  const [orgName, setOrgName] = useState('Acme Corp');
  const [orgSlug, setOrgSlug] = useState('acme_corp_main');
  const [region, setRegion] = useState('us-east-1');
  const [webhookUrl, setWebhookUrl] = useState('https://api.acme.com/intermesh/events');
  const [webhookSecret, setWebhookSecret] = useState('whsec_intermesh_99a8b7c6d5e4f3a2b109876543210fed');
  const [webhookEnabled, setWebhookEnabled] = useState(true);
  const [events, setEvents] = useState({
    agent_connected: true,
    quota_alert: true,
    key_created: true,
    security_event: true,
  });

  const [members, setMembers] = useState<Member[]>(DEFAULT_MEMBERS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  // Modals
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'Admin' | 'Developer' | 'Viewer'>('Developer');
  const [inviteLoading, setInviteLoading] = useState(false);

  const [deleteMember, setDeleteMember] = useState<Member | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  // Load from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data.orgName) setOrgName(data.orgName);
      if (data.orgSlug) setOrgSlug(data.orgSlug);
      if (data.region) setRegion(data.region);
      if (data.webhookUrl) setWebhookUrl(data.webhookUrl);
      if (data.webhookSecret) setWebhookSecret(data.webhookSecret);
      if (typeof data.webhookEnabled === 'boolean') setWebhookEnabled(data.webhookEnabled);
      if (data.events) setEvents(data.events);
      if (Array.isArray(data.members) && data.members.length) setMembers(data.members);
    } catch {
      // ignore
    }
  }, []);

  const showToast = (type: Toast['type'], message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 2800);
  };

  const persist = (next?: Partial<{
    orgName: string;
    orgSlug: string;
    region: string;
    webhookUrl: string;
    webhookSecret: string;
    webhookEnabled: boolean;
    events: typeof events;
    members: Member[];
  }>) => {
    const payload = {
      orgName,
      orgSlug,
      region,
      webhookUrl,
      webhookSecret,
      webhookEnabled,
      events,
      members,
      ...next,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  };

  const handleSaveGeneral = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgName.trim() || !orgSlug.trim()) {
      showToast('error', 'Le nom et l’identifiant de l’organisation sont requis.');
      return;
    }
    setSaving(true);
    await new Promise((r) => setTimeout(r, 700));
    persist({ orgName: orgName.trim(), orgSlug: orgSlug.trim(), region });
    setSaving(false);
    setSaved(true);
    showToast('success', 'Paramètres généraux enregistrés.');
    setTimeout(() => setSaved(false), 2000);
  };

  const handleSaveWebhooks = async () => {
    if (webhookEnabled && webhookUrl && !webhookUrl.startsWith('https://') && !webhookUrl.startsWith('http://')) {
      showToast('error', 'L’URL du webhook doit commencer par http:// ou https://');
      return;
    }
    setSaving(true);
    await new Promise((r) => setTimeout(r, 600));
    persist({ webhookUrl, webhookSecret, webhookEnabled, events });
    setSaving(false);
    showToast('success', 'Configuration webhook enregistrée.');
  };

  const handleCopySecret = async () => {
    await navigator.clipboard.writeText(webhookSecret);
    setCopiedSecret(true);
    showToast('info', 'Secret webhook copié.');
    setTimeout(() => setCopiedSecret(false), 2000);
  };

  const handleRotateSecret = () => {
    const rand = Array.from(crypto.getRandomValues(new Uint8Array(16)))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    const next = `whsec_intermesh_${rand}`;
    setWebhookSecret(next);
    persist({ webhookSecret: next });
    showToast('success', 'Nouveau secret webhook généré.');
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    const email = inviteEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      showToast('error', 'Email invalide.');
      return;
    }
    if (members.some((m) => m.email.toLowerCase() === email)) {
      showToast('error', 'Ce membre existe déjà.');
      return;
    }

    setInviteLoading(true);
    await new Promise((r) => setTimeout(r, 800));

    const name = email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    const nextMembers: Member[] = [
      ...members,
      {
        id: `m_${Date.now()}`,
        name,
        email,
        role: inviteRole,
        status: 'Pending',
      },
    ];
    setMembers(nextMembers);
    persist({ members: nextMembers });
    setInviteLoading(false);
    setInviteOpen(false);
    setInviteEmail('');
    setInviteRole('Developer');
    showToast('success', `Invitation envoyée à ${email}`);
  };

  const handleDeleteMember = async () => {
    if (!deleteMember || deleteMember.role === 'Owner') return;
    const nextMembers = members.filter((m) => m.id !== deleteMember.id);
    setMembers(nextMembers);
    persist({ members: nextMembers });
    setDeleteMember(null);
    showToast('success', `${deleteMember.email} a été retiré de l’espace de travail.`);
  };

  const handleRoleChange = (id: string, role: Member['role']) => {
    const nextMembers = members.map((m) => (m.id === id && m.role !== 'Owner' ? { ...m, role } : m));
    setMembers(nextMembers);
    persist({ members: nextMembers });
    showToast('success', 'Rôle mis à jour.');
  };

  const handleResetCredentials = async () => {
    if (resetConfirm !== 'RESET') {
      showToast('error', 'Tapez RESET pour confirmer.');
      return;
    }
    setResetLoading(true);
    await new Promise((r) => setTimeout(r, 1000));

    const rand = Array.from(crypto.getRandomValues(new Uint8Array(16)))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    const nextSecret = `whsec_intermesh_${rand}`;
    setWebhookSecret(nextSecret);
    persist({ webhookSecret: nextSecret });

    setResetLoading(false);
    setResetOpen(false);
    setResetConfirm('');
    showToast('success', 'Toutes les credentials ont été réinitialisées.');
  };

  return (
    <div className="space-y-10 font-sans relative">
      {/* TOAST */}
      {toast && (
        <div
          className={`fixed top-20 right-8 z-50 px-4 py-3 rounded-lg border text-xs font-medium shadow-2xl ${
            toast.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : toast.type === 'error'
              ? 'bg-red-500/10 border-red-500/30 text-red-300'
              : 'bg-white/10 border-white/20 text-slate-200'
          }`}
        >
          {toast.message}
        </div>
      )}

      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Paramètres de l&apos;espace de travail</h1>
        <p className="text-xs text-slate-400 mt-1">
          Gérez les informations de votre organisation, les membres, les webhooks et la sécurité.
        </p>
      </div>

      {/* GENERAL */}
      <form onSubmit={handleSaveGeneral} className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center space-x-3">
            <Building2 className="w-5 h-5 text-slate-400" />
            <div>
              <h2 className="text-base font-bold text-white">Informations générales</h2>
              <p className="text-xs text-slate-400">Informations de base concernant le compte principal de votre organisation.</p>
            </div>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="py-2 px-4 bg-white hover:bg-slate-200 disabled:opacity-60 text-black text-xs font-semibold rounded-lg flex items-center space-x-2 transition"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : saved ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Save className="w-3.5 h-3.5" />}
            <span>{saving ? 'Enregistrement...' : saved ? 'Enregistré' : 'Enregistrer les modifications'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
          <div className="space-y-1.5">
            <label className="block font-medium text-slate-300">Nom d&apos;affichage de l&apos;espace de travail</label>
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="w-full bg-[#08080A] border border-slate-800 focus:border-white/40 rounded-lg px-3.5 py-2.5 text-slate-200 outline-none transition"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block font-medium text-slate-300">Identifiant de l&apos;organisation</label>
            <input
              type="text"
              value={orgSlug}
              onChange={(e) => setOrgSlug(e.target.value.toLowerCase().replace(/\s+/g, '_'))}
              className="w-full bg-[#08080A] border border-slate-800 focus:border-white/40 rounded-lg px-3.5 py-2.5 text-slate-200 font-mono outline-none transition"
            />
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <label className="block font-medium text-slate-300">Région par défaut</label>
            <div className="relative">
              <Globe className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="w-full bg-[#08080A] border border-slate-800 focus:border-white/40 rounded-lg pl-10 pr-3.5 py-2.5 text-slate-200 outline-none transition appearance-none"
              >
                <option value="us-east-1">us-east-1 (N. Virginia - Low Latency)</option>
                <option value="us-west-2">us-west-2 (Oregon)</option>
                <option value="eu-west-1">eu-west-1 (Ireland)</option>
                <option value="ap-southeast-1">ap-southeast-1 (Singapore)</option>
              </select>
            </div>
          </div>
        </div>
      </form>

      {/* MEMBERS */}
      <div className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center space-x-3">
            <Users className="w-5 h-5 text-slate-400" />
            <div>
              <h2 className="text-base font-bold text-white">Membres de l&apos;équipe et accès</h2>
              <p className="text-xs text-slate-400">Personnes ayant accès à cet espace de travail du plan de contrôle.</p>
            </div>
          </div>
          <button
            onClick={() => setInviteOpen(true)}
            className="py-2 px-3.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center space-x-2 transition border border-white/10"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Inviter un membre</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500 border-b border-white/10 uppercase text-[10px] font-mono">
              <tr>
                <th className="pb-3">Utilisateur</th>
                <th className="pb-3">Rôle</th>
                <th className="pb-3">Statut</th>
                <th className="pb-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {members.map((m) => (
                <tr key={m.id} className="hover:bg-white/[0.02] transition">
                  <td className="py-3.5">
                    <div className="font-medium text-white">{m.name}</div>
                    <div className="text-[11px] text-slate-500 font-mono">{m.email}</div>
                  </td>
                  <td className="py-3.5">
                    {m.role === 'Owner' ? (
                      <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300">Propriétaire</span>
                    ) : (
                      <select
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value as Member['role'])}
                        className="bg-[#08080A] border border-white/10 rounded px-2 py-1 text-slate-300 outline-none"
                      >
                        <option value="Admin">Administrateur</option>
                        <option value="Developer">Développeur</option>
                        <option value="Viewer">Téléspectateur</option>
                      </select>
                    )}
                  </td>
                  <td className="py-3.5">
                    <span className={`inline-flex items-center space-x-1.5 text-[11px] ${m.status === 'Active' ? 'text-emerald-400' : 'text-amber-400'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${m.status === 'Active' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                      <span>{m.status === 'Active' ? 'Actif' : 'En attente'}</span>
                    </span>
                  </td>
                  <td className="py-3.5 text-right">
                    {m.role !== 'Owner' && (
                      <button
                        onClick={() => setDeleteMember(m)}
                        className="text-slate-500 hover:text-red-400 p-1 transition"
                        title="Retirer le membre"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* WEBHOOKS */}
      <div className="bg-[#121214] border border-white/10 rounded-xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center space-x-3">
            <Webhook className="w-5 h-5 text-slate-400" />
            <div>
              <h2 className="text-base font-bold text-white">Event Webhooks</h2>
              <p className="text-xs text-slate-400">Recevez des callbacks HTTP en temps réel pour les connexions d&apos;agents et alertes de quota.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setWebhookEnabled((v) => !v)}
            className={`relative w-11 h-6 rounded-full transition ${webhookEnabled ? 'bg-emerald-500' : 'bg-slate-700'}`}
            aria-label="Toggle webhook"
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition ${webhookEnabled ? 'translate-x-5' : ''}`} />
          </button>
        </div>

        <div className={`space-y-4 text-xs ${webhookEnabled ? '' : 'opacity-50 pointer-events-none'}`}>
          <div className="space-y-1.5">
            <label className="block font-medium text-slate-300">Webhook Endpoint URL</label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://api.acme.com/intermesh/events"
              className="w-full bg-[#08080A] border border-slate-800 focus:border-white/40 rounded-lg px-3.5 py-2.5 text-slate-200 font-mono outline-none transition"
            />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {(
              [
                ['agent_connected', 'Agent connecté'],
                ['quota_alert', 'Alerte quota'],
                ['key_created', 'Clé créée'],
                ['security_event', 'Événement sécurité'],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center space-x-2 bg-[#08080A] border border-slate-800 rounded-lg px-3 py-2 cursor-pointer hover:border-slate-600 transition">
                <input
                  type="checkbox"
                  checked={events[key]}
                  onChange={(e) => setEvents((prev) => ({ ...prev, [key]: e.target.checked }))}
                  className="accent-white"
                />
                <span className="text-slate-300">{label}</span>
              </label>
            ))}
          </div>

          <div className="bg-[#08080A] border border-slate-800 rounded-lg p-3 flex items-center justify-between font-mono">
            <div className="space-y-1 min-w-0">
              <span className="text-[10px] text-slate-500 uppercase block">Webhook Signing Secret</span>
              <span className="text-slate-300 truncate block">{webhookSecret.substring(0, 18)}****************</span>
            </div>
            <div className="flex items-center space-x-2 shrink-0">
              <button
                type="button"
                onClick={handleCopySecret}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center space-x-1.5 transition font-sans"
              >
                {copiedSecret ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedSecret ? 'Copié' : 'Copier'}</span>
              </button>
              <button
                type="button"
                onClick={handleRotateSecret}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center space-x-1.5 transition font-sans"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Régénérer</span>
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSaveWebhooks}
            disabled={saving}
            className="py-2 px-4 bg-white hover:bg-slate-200 disabled:opacity-60 text-black text-xs font-semibold rounded-lg flex items-center space-x-2 transition"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>Enregistrer les webhooks</span>
          </button>
        </div>
      </div>

      {/* DANGER ZONE */}
      <div className="bg-[#121214] border border-red-500/20 rounded-xl p-6 space-y-4">
        <div className="flex items-center space-x-3 text-red-400 border-b border-red-500/10 pb-4">
          <ShieldAlert className="w-5 h-5" />
          <h2 className="text-base font-bold">Danger Zone</h2>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs pt-2">
          <div>
            <div className="font-bold text-white">Réinitialiser les credentials de l&apos;organisation</div>
            <div className="text-slate-400 mt-0.5">
              Révoque le secret webhook et force la régénération des credentials sensibles locales.
            </div>
          </div>
          <button
            type="button"
            onClick={() => setResetOpen(true)}
            className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-semibold rounded-lg transition shrink-0"
          >
            Reset All Credentials
          </button>
        </div>
      </div>

      {/* INVITE MODAL */}
      {inviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setInviteOpen(false)} />
          <div className="relative w-full max-w-md bg-[#121214] border border-white/10 rounded-xl shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Inviter un membre</h3>
                <p className="text-xs text-slate-400 mt-0.5">Envoyez une invitation à rejoindre ce workspace.</p>
              </div>
              <button type="button" onClick={() => setInviteOpen(false)} className="text-slate-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400">Email</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="dev@acme.com"
                    className="w-full bg-[#08080A] border border-slate-800 rounded-lg pl-10 pr-3 py-2.5 text-sm text-white outline-none focus:border-white/40"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400">Rôle</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as 'Admin' | 'Developer' | 'Viewer')}
                  className="w-full bg-[#08080A] border border-slate-800 rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-white/40"
                >
                  <option value="Admin">Administrateur</option>
                  <option value="Developer">Développeur</option>
                  <option value="Viewer">Téléspectateur</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={inviteLoading}
                className="w-full py-2.5 bg-white hover:bg-slate-200 disabled:opacity-60 text-black rounded-lg text-sm font-semibold flex items-center justify-center space-x-2"
              >
                {inviteLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                <span>{inviteLoading ? 'Envoi...' : 'Envoyer l’invitation'}</span>
              </button>
            </form>
          </div>
        </div>
      )}

      {/* DELETE MEMBER MODAL */}
      {deleteMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setDeleteMember(null)} />
          <div className="relative w-full max-w-md bg-[#121214] border border-white/10 rounded-xl shadow-2xl p-6 space-y-5">
            <div className="flex items-start space-x-3">
              <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Retirer ce membre ?</h3>
                <p className="text-xs text-slate-400 mt-1">
                  <span className="text-white font-mono">{deleteMember.email}</span> perdra immédiatement l&apos;accès au Control Plane.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={() => setDeleteMember(null)}
                className="px-4 py-2 text-xs text-slate-300 hover:text-white transition"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleDeleteMember}
                className="px-4 py-2 bg-red-500 hover:bg-red-400 text-white text-xs font-semibold rounded-lg transition"
              >
                Confirmer la suppression
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESET MODAL */}
      {resetOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setResetOpen(false)} />
          <div className="relative w-full max-w-md bg-[#121214] border border-red-500/20 rounded-xl shadow-2xl p-6 space-y-5">
            <div className="flex items-start space-x-3">
              <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Reset All Credentials</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Cette action régénère le secret webhook et invalide les credentials sensibles locales.
                  Tapez <span className="text-red-300 font-mono">RESET</span> pour confirmer.
                </p>
              </div>
            </div>

            <input
              type="text"
              value={resetConfirm}
              onChange={(e) => setResetConfirm(e.target.value)}
              placeholder="RESET"
              className="w-full bg-[#08080A] border border-red-500/30 rounded-lg px-3.5 py-2.5 text-sm text-white font-mono outline-none focus:border-red-400"
            />

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setResetOpen(false);
                  setResetConfirm('');
                }}
                className="px-4 py-2 text-xs text-slate-300 hover:text-white transition"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleResetCredentials}
                disabled={resetLoading || resetConfirm !== 'RESET'}
                className="px-4 py-2 bg-red-500 hover:bg-red-400 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition flex items-center space-x-2"
              >
                {resetLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{resetLoading ? 'Réinitialisation...' : 'Confirmer le reset'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
