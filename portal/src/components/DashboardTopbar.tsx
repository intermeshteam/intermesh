'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { HUB_URL } from '@/lib/hub';
import { BORDER, SURFACE_CHROME_BLUR, SURFACE_RAISED, TONE } from '@/lib/ui';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import {
  Search,
  Bell,
  HelpCircle,
  X,
  Users,
  Key,
  CreditCard,
  ShieldCheck,
  LayoutDashboard,
  FileText,
  LogOut,
  Settings,
  User,
  ExternalLink,
  Check,
} from 'lucide-react';

type SearchItem = {
  id: string;
  label: string;
  description: string;
  href: string;
  icon: React.ElementType;
  group: string;
};

const SEARCH_ITEMS: SearchItem[] = [
  {
    id: 'overview',
    label: 'Overview & Quotas',
    description: 'Dashboard principal et limites d’agents',
    href: '/dashboard',
    icon: LayoutDashboard,
    group: 'Navigation',
  },
  {
    id: 'agents',
    label: 'Agents Directory',
    description: 'Liste des agents connectés',
    href: '/agents',
    icon: Users,
    group: 'Navigation',
  },
  {
    id: 'keys',
    label: 'API Keys & Licenses',
    description: 'Gérer les clés et licences',
    href: '/keys',
    icon: Key,
    group: 'Navigation',
  },
  {
    id: 'security',
    label: 'Audit Log & RBAC',
    description: 'Journal d’audit et permissions',
    href: '/security',
    icon: ShieldCheck,
    group: 'Navigation',
  },
  {
    id: 'billing',
    label: 'Billing & Plans',
    description: 'Abonnement et tarification',
    href: '/billing',
    icon: CreditCard,
    group: 'Navigation',
  },
  {
    id: 'settings',
    label: 'Workspace Settings',
    description: 'Paramètres d’organisation, membres et webhooks',
    href: '/settings',
    icon: Settings,
    group: 'Navigation',
  },
  {
    id: 'docs',
    label: 'RFC-001 Documentation',
    description: 'Spécification du protocole InterMesh',
    href: '/docs',
    icon: FileText,
    group: 'Resources',
  },
];

type Notification = {
  id: string;
  title: string;
  body: string;
  time: string;
  unread: boolean;
};

// Notifications start empty. The three that used to sit here were invented —
// a fictional agent connecting, a fictional quota warning — and a badge
// showing unread items nobody had received is exactly the kind of detail that
// makes a console feel staged.
const INITIAL_NOTIFICATIONS: Notification[] = [];

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Overview',
  '/topology': 'Topology',
  '/agents': 'Agents',
  '/keys': 'API keys',
  '/security': 'Audit log',
  '/billing': 'Billing',
  '/settings': 'Settings',
};

export default function DashboardTopbar() {
  const router = useRouter();
  const pathname = usePathname();
  const pageTitle = PAGE_TITLES[pathname] ?? 'Overview';
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [notifOpen, setNotifOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifications, setNotifications] = useState(INITIAL_NOTIFICATIONS);
  const [activeIndex, setActiveIndex] = useState(0);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const helpRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const handleSignOut = async () => {
    setProfileOpen(false);
    if (isSupabaseConfigured()) {
      const { signOut } = await import('@/lib/supabase/account');
      await signOut();
    }
    router.push('/auth');
  };

  const filtered = SEARCH_ITEMS.filter((item) => {
    const q = query.toLowerCase().trim();
    if (!q) return true;
    return (
      item.label.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.group.toLowerCase().includes(q)
    );
  });

  const grouped = filtered.reduce<Record<string, SearchItem[]>>((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {});

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
        setNotifOpen(false);
        setHelpOpen(false);
        setProfileOpen(false);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setNotifOpen(false);
        setHelpOpen(false);
        setProfileOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
      setActiveIndex(0);
    } else {
      setQuery('');
    }
  }, [searchOpen]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (notifRef.current && !notifRef.current.contains(t)) setNotifOpen(false);
      if (helpRef.current && !helpRef.current.contains(t)) setHelpOpen(false);
      if (profileRef.current && !profileRef.current.contains(t)) setProfileOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const goTo = (href: string) => {
    setSearchOpen(false);
    setQuery('');
    router.push(href);
  };

  const onSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[activeIndex]) {
      e.preventDefault();
      goTo(filtered[activeIndex].href);
    }
  };

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

  return (
    <>
      <header className={`sticky top-0 z-20 flex h-14 items-center justify-between border-b px-6 backdrop-blur-xl md:px-8 ${BORDER} ${SURFACE_CHROME_BLUR}`}>
        {/* L'adresse du Hub etait affichee ici, dans l'en-tete de page et
            dans le pied de la barre laterale : trois fois le meme fait, et un
            grand vide au milieu de la barre. Elle ne subsiste qu'en bas de la
            barre laterale ; cet emplacement dit ou l'on se trouve. */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-400">Control plane</span>
          <span className="text-slate-500">/</span>
          <span className="font-medium text-white">{pageTitle}</span>
        </div>

        <div className="flex items-center space-x-3 md:space-x-4">
          <button
            onClick={() => setSearchOpen(true)}
            className="hidden md:flex items-center bg-[#141519] border border-white/10 rounded-md px-3 py-1.5 text-xs text-slate-400 w-64 hover:border-white/20 transition text-left"
          >
            <Search className="w-3.5 h-3.5 mr-2 text-slate-400" />
            <span className="flex-1 text-slate-400">Search agents, keys...</span>
            <span className="text-[10px] font-mono border border-white/20 rounded px-1 text-slate-400">⌘K</span>
          </button>

          <button
            onClick={() => setSearchOpen(true)}
            className="md:hidden text-slate-400 hover:text-white transition p-1"
          >
            <Search className="w-4 h-4" />
          </button>

          <div className="relative" ref={helpRef}>
            <button
              onClick={() => setHelpOpen((v) => !v)}
              className={`text-slate-400 hover:text-white transition p-1 rounded ${helpOpen ? 'text-white bg-white/5' : ''}`}
            >
              <HelpCircle className="w-4 h-4" />
            </button>

            {helpOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-[#111114] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-white/10">
                  <div className="text-sm font-semibold text-white">Help & Resources</div>
                </div>
                <div className="p-2 space-y-0.5">
                  <Link href="/docs" onClick={() => setHelpOpen(false)} className="flex items-center justify-between px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-white/5 hover:text-white transition">
                    <span className="flex items-center space-x-2"><FileText className="w-3.5 h-3.5" /><span>RFC-001 Spec</span></span>
                    <ExternalLink className="w-3 h-3 text-slate-400" />
                  </Link>
                  <a href="https://github.com/intermeshteam/intermesh" target="_blank" className="flex items-center justify-between px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-white/5 hover:text-white transition">
                    <span className="flex items-center space-x-2"><ExternalLink className="w-3.5 h-3.5" /><span>GitHub Repository</span></span>
                  </a>
                </div>
              </div>
            )}
          </div>

          <div className="relative" ref={notifRef}>
            <button
              onClick={() => setNotifOpen((v) => !v)}
              className={`relative text-slate-400 hover:text-white transition p-1 rounded ${notifOpen ? 'text-white bg-white/5' : ''}`}
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-red-500 text-[9px] font-bold text-white flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-[#111114] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                  <div className="text-sm font-semibold text-white">Notifications</div>
                  {unreadCount > 0 && (
                    <button onClick={markAllRead} className="text-[11px] text-slate-400 hover:text-white transition">
                      Tout marquer lu
                    </button>
                  )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.map((n) => (
                    <div key={n.id} className="p-3 border-b border-white/5 hover:bg-white/[0.02]">
                      <div className="text-xs font-semibold text-white">{n.title}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">{n.body}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setProfileOpen((v) => !v)}
              className="w-7 h-7 rounded-full bg-white/10 border border-white/20 text-white font-mono font-bold text-xs flex items-center justify-center hover:bg-white/15 transition"
            >
              AC
            </button>

            {profileOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-[#111114] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-white/10">
                  <div className="text-sm font-semibold text-white">Local workspace</div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">self-hosted</div>
                </div>
                <div className="p-2 space-y-0.5">
                  <Link href="/dashboard" onClick={() => setProfileOpen(false)} className="flex items-center space-x-2 px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-white/5 hover:text-white transition">
                    <User className="w-3.5 h-3.5" /><span>Account Overview</span>
                  </Link>
                  <Link href="/settings" onClick={() => setProfileOpen(false)} className="flex items-center space-x-2 px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-white/5 hover:text-white transition">
                    <Settings className="w-3.5 h-3.5" /><span>Workspace Settings</span>
                  </Link>
                </div>
                <div className="p-2 border-t border-white/10">
                  {/* Was a link to /auth, which navigated away while leaving
                      the session intact — the account stayed signed in. */}
                  <button
                    onClick={handleSignOut}
                    className="flex w-full items-center space-x-2 px-3 py-2 rounded-lg text-xs text-red-400 hover:bg-red-500/10 transition"
                  >
                    <LogOut className="w-3.5 h-3.5" /><span>Log out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {searchOpen && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setSearchOpen(false)} />
          <div className="relative w-full max-w-xl bg-[#111114] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
            <div className="flex items-center px-4 border-b border-white/10">
              <Search className="w-4 h-4 text-slate-400 mr-3" />
              <input
                ref={searchInputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActiveIndex(0);
                }}
                onKeyDown={onSearchKeyDown}
                placeholder="Search agents, keys, settings..."
                className="flex-1 bg-transparent py-3.5 text-sm text-white outline-none placeholder:text-slate-400"
              />
              <button onClick={() => setSearchOpen(false)} className="text-slate-400 hover:text-white p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="max-h-80 overflow-y-auto p-2">
              {filtered.length === 0 ? (
                <div className="px-3 py-8 text-center text-xs text-slate-400">Aucun résultat pour “{query}”</div>
              ) : (
                Object.entries(grouped).map(([group, items]) => (
                  <div key={group} className="mb-2">
                    <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400">{group}</div>
                    {items.map((item) => {
                      const globalIndex = filtered.findIndex((f) => f.id === item.id);
                      const Icon = item.icon;
                      const active = globalIndex === activeIndex;
                      return (
                        <button
                          key={item.id}
                          onClick={() => goTo(item.href)}
                          onMouseEnter={() => setActiveIndex(globalIndex)}
                          className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-left transition ${
                            active ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/5'
                          }`}
                        >
                          <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-white' : 'text-slate-400'}`} />
                          <div className="min-w-0 flex-1">
                            <div className="text-xs font-medium truncate">{item.label}</div>
                            <div className="text-[11px] text-slate-400 truncate">{item.description}</div>
                          </div>
                          {active && <Check className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
