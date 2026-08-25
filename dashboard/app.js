/**
 * Nexus — Console d'administration.
 *
 * Parle le protocole nexus/v1 directement en WebSocket : la console est
 * un agent comme un autre, simplement porteur d'une clé d'API admin.
 *
 * La clé n'est jamais écrite dans localStorage ni sessionStorage. Elle
 * vit dans une variable, le temps de l'onglet. Un rechargement la
 * redemande — c'est volontaire : un jeton d'administration qui survit
 * dans le stockage du navigateur survit aussi à l'utilisateur qui
 * s'éloigne de son poste.
 */
'use strict';

const S = {
  ws: null, key: null, url: null, token: null, name: null, org: null,
  pending: new Map(), view: 'overview', events: [], reconnect: null,
};

const $ = (id) => document.getElementById(id);
const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
  : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    }));

const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ago = (ts) => {
  if (!ts) return '—';
  const d = Date.now() / 1000 - ts;
  if (d < 60) return `il y a ${Math.max(0, Math.round(d))} s`;
  if (d < 3600) return `il y a ${Math.round(d / 60)} min`;
  if (d < 86400) return `il y a ${Math.round(d / 3600)} h`;
  return new Date(ts * 1000).toLocaleDateString('fr-FR');
};

const clock = (ts) => ts
  ? new Date(ts * 1000).toLocaleTimeString('fr-FR', { hour12: false })
  : '—';

function toast(msg, bad = false) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast on' + (bad ? ' bad' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = 'toast'; }, 4200);
}

// ---------------------------------------------------------------- réseau

function connect(url, key) {
  return new Promise((resolve, reject) => {
    let ws;
    try { ws = new WebSocket(url); }
    catch (e) { return reject(new Error('Adresse invalide : ' + e.message)); }

    const guard = setTimeout(() => {
      try { ws.close(); } catch (_) {}
      reject(new Error("Le Hub n'a pas répondu. Est-il démarré à cette adresse ?"));
    }, 8000);

    ws.onopen = () => ws.send(JSON.stringify({
      id: uuid(), version: 'nexus/v1', type: 'register',
      sender: 'admin_console',
      content: {
        name: 'admin_console', api_key: key,
        roles: ['admin', 'observer'], capabilities: ['administration'],
        metadata: { client: 'web-console' },
      },
    }));

    ws.onmessage = (raw) => {
      let m; try { m = JSON.parse(raw.data); } catch (_) { return; }

      if (!S.token) {
        clearTimeout(guard);
        if (m.type === 'registered') {
          S.ws = ws; S.token = m.content.token;
          S.name = m.content.qualified_name; S.org = m.content.org_id;
          // Le rôle observer est accordé par la clé, pas déclaré : si le
          // Hub ne l'a pas confirmé, la clé n'est pas une clé admin.
          route(ws);
          return resolve(m.content);
        }
        if (m.type === 'error') {
          try { ws.close(); } catch (_) {}
          return reject(new Error(m.content));
        }
        return;
      }
      handle(m);
    };

    ws.onerror = () => { clearTimeout(guard); if (!S.token) reject(new Error('Connexion impossible.')); };
    ws.onclose = () => { clearTimeout(guard); if (S.token) offline(); };
  });
}

function route(ws) { ws.onmessage = (raw) => { try { handle(JSON.parse(raw.data)); } catch (_) {} }; }

function handle(m) {
  if (m.type === 'admin_result' && S.pending.has(m.reply_to)) {
    const { resolve, reject } = S.pending.get(m.reply_to);
    S.pending.delete(m.reply_to);
    m.content.ok ? resolve(m.content.result) : reject(new Error(m.content.error));
    return;
  }
  if (m.type === 'telemetry_event') pushEvent(m.content);
}

function admin(command, params = {}) {
  return new Promise((resolve, reject) => {
    if (!S.ws || S.ws.readyState !== WebSocket.OPEN)
      return reject(new Error('Hub déconnecté.'));

    const id = uuid();
    S.pending.set(id, { resolve, reject });
    setTimeout(() => {
      if (S.pending.has(id)) { S.pending.delete(id); reject(new Error('Délai dépassé.')); }
    }, 12000);

    S.ws.send(JSON.stringify({
      id, version: 'nexus/v1', type: 'admin_request',
      sender: S.name, content: { command, params }, token: S.token,
    }));
  });
}

function offline() {
  $('conn-dot').className = 'dot down';
  $('conn-txt').textContent = 'déconnecté';
  if (S.reconnect) return;
  toast('Connexion au Hub perdue. Tentative de reconnexion…', true);
  S.reconnect = setInterval(async () => {
    try {
      S.token = null;
      await connect(S.url, S.key);
      clearInterval(S.reconnect); S.reconnect = null;
      $('conn-dot').className = 'dot up';
      $('conn-txt').textContent = 'connecté';
      toast('Reconnecté au Hub.');
      render();
    } catch (_) { /* on retente */ }
  }, 4000);
}

// ------------------------------------------------------------- télémétrie

const EV = {
  agent_connected:    { c: 'join',  l: 'JOIN',  t: e => `${e.name} — ${(e.roles || []).join(', ') || 'standard'}` },
  agent_disconnected: { c: 'left',  l: 'LEFT',  t: e => e.name },
  task_submitted:     { c: 'task',  l: 'TASK',  t: e => `« ${e.title} » ${e.orchestrator} ➜ ${e.assignee}` },
  task_updated:       { c: 'task',  l: 'TASK',  t: e => `${e.title || e.task_id?.slice(0, 8)} → ${e.status}${e.error_message ? ' : ' + e.error_message : ''}` },
  message_routed:     { c: 'msg',   l: 'MESG',  t: e => `${e.sender} ➜ ${e.to}` },
  admin_action:       { c: 'admin', l: 'ADMN',  t: e => `${e.actor} : ${e.command}` },
  admin_denied:       { c: 'deny',  l: 'DENY',  t: e => `${e.actor} refusé sur ${e.command}` },
};

function pushEvent(ev) {
  const spec = EV[ev.event];
  if (!spec) return;
  S.events.unshift({ cls: spec.c, lbl: spec.l, txt: spec.t(ev), at: ev.at });
  if (S.events.length > 200) S.events.pop();
  if (S.view === 'overview') drawFeed();

  // Les vues concernées se rafraîchissent d'elles-mêmes.
  if (S.view === 'agents' && ev.event.startsWith('agent_')) loadAgents();
  if (S.view === 'tasks' && ev.event.startsWith('task_')) loadTasks();
}

function drawFeed() {
  const box = $('feed');
  if (!S.events.length) { box.innerHTML = '<div class="empty">En attente d\'événements…</div>'; return; }
  box.innerHTML = S.events.map(e => `
    <div class="ev ${e.cls}">
      <div class="top"><span class="lbl">[${e.lbl}]</span><span>${clock(e.at)}</span></div>
      <div class="txt">${esc(e.txt)}</div>
    </div>`).join('');
}

// ------------------------------------------------------------------ vues

async function loadOverview() {
  try {
    const i = await admin('hub.info');
    $('ov-meta').textContent =
      `Organisation ${i.org} · Hub v${i.version} · ${i.federation_peers.length} pair(s) fédéré(s)`;
    $('brand-org').textContent = i.org;

    const unfinished = (i.tasks_by_status.pending || 0) + (i.tasks_by_status.running || 0);
    $('ov-stats').innerHTML = [
      ['Agents connectés', i.agents_online, 'cyan', `${i.agents_known} connus au total`],
      ['Tâches', i.tasks_total, 'green', `${unfinished} inachevée(s)`],
      ['Journal d\'audit', i.audit_entries,
        i.audit_intact ? 'green' : 'red',
        i.audit_intact ? 'chaîne vérifiée' : '🚨 CHAÎNE ROMPUE'],
      ['Comptes de service', i.api_keys, 'cyan', i.api_keys_mutable ? 'modifiables' : 'lecture seule'],
      ['État', i.state_ephemeral ? 'MÉM.' : 'DISQUE',
        i.state_ephemeral ? 'amber' : 'green',
        i.state_ephemeral ? 'perdu au redémarrage' : 'persistant'],
    ].map(([k, v, c, s]) => `
      <div class="stat"><div class="k">${k}</div>
        <div class="v ${c}">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join('');
  } catch (e) { toast(e.message, true); }
}

async function loadAgents() {
  try {
    const d = await admin('agents.list');
    $('ag-meta').textContent = `${d.online} en ligne sur ${d.known} connus`;
    const rows = $('ag-rows');
    if (!d.agents.length) { rows.innerHTML = '<tr><td colspan="7" class="empty">Aucun agent.</td></tr>'; return; }

    rows.innerHTML = d.agents.map(a => `
      <tr>
        <td><span class="mono" style="color:var(--cyan)">${esc(a.name)}</span></td>
        <td><span class="badge ${a.online ? 'on' : 'off'}">
          <span class="dot ${a.online ? 'up' : 'down'}"></span>${a.online ? 'EN LIGNE' : 'HORS LIGNE'}</span></td>
        <td>${(a.roles || []).map(r => `<span class="tag">${esc(r)}</span>`).join('') || '<span class="tag">standard</span>'}</td>
        <td style="color:var(--muted)">${esc((a.capabilities || []).join(', ') || '—')}</td>
        <td>${a.encrypted ? '🔒' : '<span style="color:var(--dim)">🔓</span>'}</td>
        <td class="mono" style="color:${a.pending_tasks ? 'var(--amber)' : 'var(--dim)'}">${a.pending_tasks}</td>
        <td style="text-align:right">${a.online
          ? `<button class="btn btn-danger btn-sm" data-kick="${esc(a.name)}">Déconnecter</button>` : ''}</td>
      </tr>`).join('');
  } catch (e) { toast(e.message, true); }
}

const TASK_BADGE = {
  pending:   ['wait', 'EN ATTENTE'], running: ['run', 'EN COURS'],
  completed: ['on', 'TERMINÉE'],     failed:  ['fail', 'ÉCHOUÉE'],
};

async function loadTasks() {
  try {
    const status = $('tk-filter').value;
    const d = await admin('tasks.list', status ? { status } : {});
    $('tk-meta').textContent = `${d.total} tâche(s)${status ? ` — filtre : ${status}` : ''}`;
    const rows = $('tk-rows');
    if (!d.tasks.length) { rows.innerHTML = '<tr><td colspan="6" class="empty">Aucune tâche.</td></tr>'; return; }

    rows.innerHTML = d.tasks.map(t => {
      const [cls, label] = TASK_BADGE[t.status] || ['off', t.status.toUpperCase()];
      const done = t.status === 'completed' || t.status === 'failed';
      return `<tr>
        <td>${esc(t.title)} ${t.encrypted_payload ? '<span title="Charge chiffrée E2E">🔒</span>' : ''}
          <div class="mono" style="font-size:10.5px;color:var(--dim)">${esc(t.task_id.slice(0, 8))}…</div></td>
        <td><span class="badge ${cls}">${label}</span>
          ${t.error_message ? `<div style="font-size:11px;color:var(--dim);max-width:220px">${esc(t.error_message)}</div>` : ''}</td>
        <td class="mono" style="font-size:12px">${esc(t.orchestrator)}</td>
        <td class="mono" style="font-size:12px">${esc(t.assignee)}</td>
        <td style="color:var(--muted);font-size:12px">${ago(t.updated_at)}</td>
        <td style="text-align:right;white-space:nowrap">
          ${done ? '' : `<button class="btn btn-danger btn-sm" data-cancel="${esc(t.task_id)}">Annuler</button> `}
          <button class="btn btn-ghost btn-sm" data-retry="${esc(t.task_id)}">Relancer</button></td>
      </tr>`;
    }).join('');
  } catch (e) { toast(e.message, true); }
}

async function loadAudit() {
  try {
    const d = await admin('audit.list', { limit: 200 });
    $('au-meta').textContent = `${d.chain_length} entrée(s) chaînée(s)`;
    $('au-status').innerHTML = d.intact
      ? `<div class="ok-banner">✓ Chaîne intègre — les ${d.chain_length} entrées se vérifient mutuellement.</div>`
      : `<div class="error">🚨 CHAÎNE ROMPUE — le journal a été modifié en dehors du Hub.
         Traitez-le comme compromis et enquêtez avant de poursuivre.</div>`;

    const rows = $('au-rows');
    rows.innerHTML = d.entries.map(e => `
      <tr>
        <td class="mono" style="color:var(--dim)">${e.index}</td>
        <td><span class="mono" style="color:var(--cyan);font-size:12px">${esc(e.event_type)}</span>
          ${Object.keys(e.metadata || {}).length
            ? `<div style="font-size:11px;color:var(--dim);max-width:280px;overflow:hidden;text-overflow:ellipsis">${esc(JSON.stringify(e.metadata))}</div>` : ''}</td>
        <td class="mono" style="font-size:12px">${esc(e.sender)}</td>
        <td class="mono" style="font-size:12px;color:var(--muted)">${esc(e.target || '—')}</td>
        <td style="color:var(--muted);font-size:12px">${clock(e.timestamp)}</td>
        <td class="mono" style="font-size:10.5px;color:var(--dim)">${esc(e.hash.slice(0, 12))}…</td>
      </tr>`).join('');
  } catch (e) { toast(e.message, true); }
}

async function loadKeys() {
  try {
    const d = await admin('apikeys.list');
    $('kt-meta').textContent = `${d.keys.length} clé(s) — ${d.source}`;
    const rows = $('kt-rows');

    if (!d.mutable) {
      toast('Clés en lecture seule : elles proviennent de l\'environnement.', true);
    }
    if (!d.keys.length) {
      rows.innerHTML = '<tr><td colspan="6" class="empty">Aucun compte de service.</td></tr>';
      return;
    }
    rows.innerHTML = d.keys.map(k => `
      <tr>
        <td class="mono" style="color:var(--cyan);font-size:12px">${esc(k.fingerprint)}…</td>
        <td>${esc(k.label || '—')}</td>
        <td class="mono" style="font-size:12px">${esc(k.org_id)}</td>
        <td>${(k.roles || []).map(r => `<span class="tag">${esc(r)}</span>`).join('')}</td>
        <td style="color:var(--muted);font-size:12px">${esc((k.permissions || []).join(', ') || '—')}</td>
        <td style="text-align:right">${d.mutable
          ? `<button class="btn btn-danger btn-sm" data-revoke="${esc(k.fingerprint)}">Révoquer</button>` : ''}</td>
      </tr>`).join('');
  } catch (e) { toast(e.message, true); }
}

const LOADERS = { overview: loadOverview, agents: loadAgents, tasks: loadTasks, audit: loadAudit, keys: loadKeys };

function render() {
  ['overview', 'agents', 'tasks', 'audit', 'keys'].forEach(v => {
    $('view-' + v).style.display = v === S.view ? '' : 'none';
  });
  document.querySelectorAll('#nav a').forEach(a =>
    a.classList.toggle('on', a.dataset.view === S.view));
  if (S.view === 'overview') drawFeed();
  LOADERS[S.view]();
}

// --------------------------------------------------------------- modales

const openModal = (id) => $(id).classList.add('on');
const closeModals = () => document.querySelectorAll('.modal').forEach(m => m.classList.remove('on'));

let confirmFn = null;
function confirmAction(title, text, fn) {
  $('cf-title').textContent = title;
  $('cf-text').textContent = text;
  confirmFn = fn;
  openModal('modal-confirm');
}

// ------------------------------------------------------------ événements

$('connect-btn').onclick = async () => {
  const url = $('hub-url').value.trim();
  const key = $('api-key').value.trim();
  const err = $('login-error');
  err.style.display = 'none';

  if (!key) { err.textContent = 'Une clé d\'API est requise.'; err.style.display = 'block'; return; }

  const btn = $('connect-btn');
  btn.disabled = true; btn.textContent = 'Connexion…';
  try {
    await connect(url, key);
    S.url = url; S.key = key;
    $('login').style.display = 'none';
    $('app').style.display = 'block';
    $('conn-dot').className = 'dot up';
    $('conn-txt').textContent = 'connecté';
    $('conn-as').textContent = S.name;

    // Sonde immédiate : une clé sans rôle admin passe l'enregistrement
    // mais échoue ici, et il vaut mieux le dire tout de suite.
    try { await admin('hub.info'); }
    catch (e) {
      $('app').style.display = 'none';
      $('login').style.display = 'flex';
      try { S.ws.close(); } catch (_) {}
      S.token = null;
      err.textContent = e.message;
      err.style.display = 'block';
      return;
    }
    render();
  } catch (e) {
    err.textContent = e.message;
    err.style.display = 'block';
  } finally {
    btn.disabled = false; btn.textContent = 'Se connecter';
  }
};

$('api-key').addEventListener('keydown', e => { if (e.key === 'Enter') $('connect-btn').click(); });

$('logout-btn').onclick = () => {
  if (S.reconnect) { clearInterval(S.reconnect); S.reconnect = null; }
  try { S.ws.close(); } catch (_) {}
  S.ws = null; S.token = null; S.key = null; S.events = [];
  $('app').style.display = 'none';
  $('login').style.display = 'flex';
  $('api-key').value = '';
};

$('nav').addEventListener('click', e => {
  const a = e.target.closest('a[data-view]');
  if (!a) return;
  S.view = a.dataset.view;
  render();
});

$('tk-filter').onchange = loadTasks;

document.addEventListener('click', async (e) => {
  const t = e.target;

  if (t.hasAttribute('data-close') || t.classList.contains('modal')) return closeModals();
  if (t.dataset.act === 'refresh') return LOADERS[S.view]();
  if (t.dataset.act === 'clear-feed') { S.events = []; return drawFeed(); }
  if (t.dataset.act === 'new-key') return openModal('modal-key');

  if (t.dataset.act === 'verify') {
    try {
      const v = await admin('audit.verify');
      toast(v.intact
        ? `Chaîne intègre : ${v.chain_length} entrées vérifiées.`
        : `CHAÎNE ROMPUE à l'entrée ${v.broken_at_index}.`, !v.intact);
      loadAudit();
    } catch (err) { toast(err.message, true); }
    return;
  }

  if (t.dataset.kick) {
    const name = t.dataset.kick;
    return confirmAction('Déconnecter cet agent ?',
      `${name} sera immédiatement déconnecté. Il pourra se reconnecter, et ses tâches inachevées lui seront alors réassignées.`,
      async () => {
        await admin('agent.disconnect', { name });
        toast(`${name} déconnecté.`); loadAgents();
      });
  }

  if (t.dataset.cancel) {
    const id = t.dataset.cancel;
    return confirmAction('Annuler cette tâche ?',
      'Elle sera marquée comme échouée. Son exécutant, s\'il travaille déjà dessus, ne sera pas interrompu.',
      async () => { await admin('task.cancel', { task_id: id }); toast('Tâche annulée.'); loadTasks(); });
  }

  if (t.dataset.retry) {
    const id = t.dataset.retry;
    try {
      const r = await admin('task.retry', { task_id: id });
      toast(r.delivered
        ? 'Tâche renvoyée à son exécutant.'
        : 'Exécutant hors ligne : la tâche lui sera poussée à sa reconnexion.');
      loadTasks();
    } catch (err) { toast(err.message, true); }
    return;
  }

  if (t.dataset.revoke) {
    const fp = t.dataset.revoke;
    return confirmAction('Révoquer cette clé ?',
      `La clé ${fp}… cessera immédiatement de fonctionner. Cette action est irréversible : une clé révoquée ne se restaure pas.`,
      async () => { await admin('apikey.revoke', { fingerprint: fp }); toast('Clé révoquée.'); loadKeys(); });
  }
});

$('cf-ok').onclick = async () => {
  closeModals();
  if (!confirmFn) return;
  try { await confirmFn(); } catch (e) { toast(e.message, true); }
  confirmFn = null;
};

$('nk-create').onclick = async () => {
  const org = $('nk-org').value.trim();
  if (!org) return toast('Organisation requise.', true);

  const split = (id) => $(id).value.split(',').map(s => s.trim()).filter(Boolean);
  try {
    const r = await admin('apikey.create', {
      org_id: org, label: $('nk-label').value.trim(),
      roles: split('nk-roles'), permissions: split('nk-perms'),
    });
    closeModals();
    $('rv-key').textContent = r.key;
    openModal('modal-reveal');
    ['nk-org', 'nk-label', 'nk-perms'].forEach(id => { $(id).value = ''; });
    loadKeys();
  } catch (e) { toast(e.message, true); }
};

$('rv-copy').onclick = async () => {
  try {
    await navigator.clipboard.writeText($('rv-key').textContent);
    toast('Clé copiée dans le presse-papiers.');
  } catch (_) { toast('Copie impossible — sélectionnez la clé manuellement.', true); }
};

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModals(); });

// Rafraîchissement périodique : la télémétrie couvre les événements, ce
// minuteur rattrape ce qui n'en produit pas (compteurs, expirations).
setInterval(() => { if (S.token && S.view !== 'audit') LOADERS[S.view](); }, 30000);
