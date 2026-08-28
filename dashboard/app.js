/**
 * InterMesh — Mission Control.
 *
 * Parle le protocole intermesh/v1 directement en WebSocket : la console est un
 * agent comme un autre, simplement porteur d'une clé d'API admin.
 *
 * La clé n'est jamais écrite dans localStorage ni sessionStorage. Elle vit
 * dans une variable, le temps de l'onglet. Un rechargement la redemande —
 * c'est volontaire : un jeton d'administration qui survit dans le stockage
 * du navigateur survit aussi à l'opérateur qui s'éloigne de son poste.
 */
'use strict';

const S = {
  ws: null, key: null, url: null, token: null, name: null, org: null,
  view: 'overview', pending: new Map(), reconnect: null,
  logs: [], logsPaused: false, info: null,
  // Séries temporelles échantillonnées côté client : le Hub renvoie un
  // état instantané, pas un historique. Les courbes démarrent donc à
  // l'ouverture de la console, ce qui est honnête et suffisant.
  series: { agents: [], tasks: [], audit: [], keys: [] },
  page: { agents: 0, tasks: 0, audit: 0 },
  PER_PAGE: 14,
};

const $ = (id) => document.getElementById(id);
const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
  : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 3 | 8)).toString(16);
    }));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const hhmmss = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString('fr-FR', { hour12: false }) : '—';
const ago = (ts) => {
  if (!ts) return '—';
  const d = Date.now() / 1000 - ts;
  if (d < 60) return `${Math.max(0, Math.round(d))}s`;
  if (d < 3600) return `${Math.round(d / 60)}min`;
  if (d < 86400) return `${Math.round(d / 3600)}h`;
  return `${Math.round(d / 86400)}j`;
};

function toast(msg, bad = false) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast on' + (bad ? ' bad' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = 'toast'; }, 4200);
}

/** Sparkline SVG, tracée à la main — aucune librairie de graphes. */
function sparkline(values, color, w = 74, h = 26) {
  if (!values || values.length < 2) return `<svg width="${w}" height="${h}"></svg>`;
  const min = Math.min(...values), max = Math.max(...values);
  const span = (max - min) || 1;
  const step = w / (values.length - 1);
  const pts = values.map((v, i) => [i * step, h - 2 - ((v - min) / span) * (h - 4)]);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${w},${h} L0,${h} Z`;
  const gid = 'g' + Math.random().toString(36).slice(2, 8);
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity=".28"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${area}" fill="url(#${gid})"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="1.4"
      stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${pts[pts.length-1][0].toFixed(1)}" cy="${pts[pts.length-1][1].toFixed(1)}"
      r="1.8" fill="${color}"/>
  </svg>`;
}

const trend = (arr) => {
  if (arr.length < 2) return '';
  const d = arr[arr.length - 1] - arr[0];
  if (d === 0) return '<span style="color:var(--dim)">stable</span>';
  return d > 0 ? `<span class="up">▲ +${d}</span>` : `<span class="down">▼ ${d}</span>`;
};

// ----------------------------------------------------------------- réseau

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
      id: uuid(), version: 'intermesh/v1', type: 'register', sender: 'admin_console',
      content: {
        name: 'admin_console', api_key: key,
        roles: ['admin', 'observer'], capabilities: ['administration'],
        metadata: { client: 'mission-control' },
      },
    }));

    ws.onmessage = (raw) => {
      let m; try { m = JSON.parse(raw.data); } catch (_) { return; }
      if (!S.token) {
        clearTimeout(guard);
        if (m.type === 'registered') {
          S.ws = ws; S.token = m.content.token;
          S.name = m.content.qualified_name; S.org = m.content.org_id;
          ws.onmessage = (r) => { try { handle(JSON.parse(r.data)); } catch (_) {} };
          return resolve(m.content);
        }
        if (m.type === 'error') { try { ws.close(); } catch (_) {} return reject(new Error(m.content)); }
        return;
      }
      handle(m);
    };
    ws.onerror = () => { clearTimeout(guard); if (!S.token) reject(new Error('Connexion impossible.')); };
    ws.onclose = () => { clearTimeout(guard); if (S.token) offline(); };
  });
}

function handle(m) {
  if (m.type === 'admin_result' && S.pending.has(m.reply_to)) {
    const { resolve, reject } = S.pending.get(m.reply_to);
    S.pending.delete(m.reply_to);
    m.content.ok ? resolve(m.content.result) : reject(new Error(m.content.error));
    return;
  }
  if (m.type === 'telemetry_event') onTelemetry(m.content);
}

function admin(command, params = {}) {
  return new Promise((resolve, reject) => {
    if (!S.ws || S.ws.readyState !== WebSocket.OPEN) return reject(new Error('Hub déconnecté.'));
    const id = uuid();
    S.pending.set(id, { resolve, reject });
    setTimeout(() => {
      if (S.pending.has(id)) { S.pending.delete(id); reject(new Error('Délai dépassé.')); }
    }, 12000);
    S.ws.send(JSON.stringify({
      id, version: 'intermesh/v1', type: 'admin_request',
      sender: S.name, content: { command, params }, token: S.token,
    }));
  });
}

function offline() {
  $('health').className = 'health bad';
  $('health-txt').textContent = 'Hub déconnecté';
  if (S.reconnect) return;
  toast('Connexion au Hub perdue. Reconnexion…', true);
  S.reconnect = setInterval(async () => {
    try {
      S.token = null;
      await connect(S.url, S.key);
      clearInterval(S.reconnect); S.reconnect = null;
      $('health').className = 'health';
      $('health-txt').textContent = 'Opérationnel';
      toast('Reconnecté au Hub.');
      render();
    } catch (_) {}
  }, 4000);
}

// ------------------------------------------------------------- télémétrie

const EV = {
  agent_connected:    { lv: 'info',  src: 'registry',     m: e => `Agent ${e.name} enregistré — rôles ${(e.roles||[]).join(', ')||'standard'} (${e.auth_method === 'api_key' ? 'clé d\'API' : 'auto-déclaré'})` },
  agent_disconnected: { lv: 'warn',  src: 'registry',     m: e => `Agent ${e.name} déconnecté` },
  task_submitted:     { lv: 'task',  src: 'scheduler',    m: e => `Tâche « ${e.title} » ${e.orchestrator} → ${e.assignee}` },
  task_updated:       { lv: 'task',  src: 'scheduler',    m: e => `Tâche ${(e.title || e.task_id || '').toString().slice(0,28)} → ${String(e.status).toUpperCase()}${e.error_message ? ' : ' + e.error_message : ''}` },
  message_routed:     { lv: 'info',  src: 'router',       m: e => `${e.type} routé ${e.sender} → ${e.to}` },
  admin_action:       { lv: 'admin', src: 'admin',        m: e => `${e.actor} a exécuté ${e.command}` },
  admin_denied:       { lv: 'error', src: 'admin',        m: e => `${e.actor} REFUSÉ sur ${e.command}` },
};

function onTelemetry(ev) {
  const spec = EV[ev.event];
  if (spec) {
    S.logs.unshift({ lv: spec.lv, src: spec.src, m: spec.m(ev), at: ev.at || Date.now()/1000 });
    if (S.logs.length > 400) S.logs.length = 400;
    if (S.view === 'overview' && !S.logsPaused) drawLogs();
  }
  // Les vues concernées se rafraîchissent d'elles-mêmes.
  if (ev.event.startsWith('agent_') && (S.view === 'agents' || S.view === 'overview')) loadAgents();
  if (ev.event.startsWith('task_') && S.view === 'tasks') loadTasks();
}

function drawLogs() {
  const box = $('logs');
  const want = $('log-level').value;
  const rows = want ? S.logs.filter(l => l.lv === want) : S.logs;
  if (!rows.length) { box.innerHTML = '<div class="empty">Aucun événement.</div>'; return; }
  box.innerHTML = rows.slice(0, 200).map(l => `
    <div class="log">
      <span class="t">${hhmmss(l.at)}</span>
      <span class="lv ${l.lv}">${l.lv.toUpperCase()}</span>
      <span class="src">${esc(l.src)}</span>
      <span class="m">${esc(l.m)}</span>
    </div>`).join('');
}

// ------------------------------------------------------------------ vues

async function loadOverview() {
  try {
    const i = await admin('hub.info');
    S.info = i;

    const unfinished = (i.tasks_by_status.pending || 0) + (i.tasks_by_status.running || 0);
    const push = (k, v) => {
      // Au tout premier relevé, on double le point : une ligne plate est
      // vraie (aucune variation encore observée) et vaut mieux qu'une
      // carte vide le temps du second échantillon.
      if (!S.series[k].length) S.series[k].push(v);
      S.series[k].push(v);
      if (S.series[k].length > 40) S.series[k].shift();
    };
    push('agents', i.agents_online); push('tasks', i.tasks_total);
    push('audit', i.audit_entries);  push('keys', i.api_keys);

    const cards = [
      ['Agents connectés', i.agents_online, 'cyan',   S.series.agents, '#22D3EE', `${i.agents_known} connus`],
      ['Tâches',           i.tasks_total,   'teal',   S.series.tasks,  '#2DD4BF', `${unfinished} inachevée(s)`],
      ['Journal d\'audit', i.audit_entries, i.audit_intact ? 'green' : 'red', S.series.audit,
        i.audit_intact ? '#10B981' : '#EF4444', i.audit_intact ? 'chaîne vérifiée' : '🚨 CHAÎNE ROMPUE'],
      ['Comptes de service', i.api_keys,    'violet', S.series.keys,   '#A78BFA',
        i.api_keys_mutable ? 'modifiables' : 'lecture seule'],
    ];
    $('kpis').innerHTML = cards.map(([k, v, c, ser, col, s]) => `
      <div class="kpi">
        <div class="k">${k}</div>
        <div class="row"><div class="v ${c}">${v}</div>${sparkline(ser, col)}</div>
        <div class="s">${trend(ser)} <span style="color:var(--dim)">· ${esc(s)}</span></div>
      </div>`).join('');

    $('sb-version').textContent = 'v' + i.version;
    $('sb-org').textContent = i.org;
    $('sb-state').textContent = i.state_ephemeral ? 'ÉPHÉMÈRE' : 'PERSISTANT';
    $('sb-audit').textContent = i.audit_intact ? 'INTÈGRE' : 'ROMPU';
    $('sb-peers').textContent = i.federation_peers.length + ' pair(s)';
    $('sb-as').textContent = S.name;

    if (!i.audit_intact) {
      $('health').className = 'health bad';
      $('health-txt').textContent = 'Audit compromis';
    }

    const ag = await admin('agents.list');
    $('ov-agent-count').textContent = `${ag.online} / ${ag.known}`;
    const online = ag.agents.filter(a => a.online);
    $('ov-agents').innerHTML = online.length ? online.map(a => `
      <tr>
        <td><span class="name">${esc(a.name)}</span></td>
        <td><span class="st on"><span class="dot up"></span>ONLINE</span></td>
        <td>${(a.roles||[]).map(r => `<span class="tag">${esc(r)}</span>`).join('') || '—'}</td>
        <td style="color:var(--muted)">${esc((a.capabilities||[]).join(', ') || '—')}</td>
        <td class="num" style="color:${a.pending_tasks ? 'var(--amber)' : 'var(--dim)'}">${a.pending_tasks}</td>
      </tr>`).join('') : '<tr><td colspan="5" class="empty">Aucun agent connecté.</td></tr>';

    drawLogs();
  } catch (e) { toast(e.message, true); }
}

function pager(id, total, key, reload) {
  const pages = Math.max(1, Math.ceil(total / S.PER_PAGE));
  if (S.page[key] >= pages) S.page[key] = pages - 1;
  const from = total ? S.page[key] * S.PER_PAGE + 1 : 0;
  const to = Math.min(total, (S.page[key] + 1) * S.PER_PAGE);
  $(id).innerHTML = `
    <span>${from}–${to} sur ${total}</span>
    <span class="right">
      <button class="btn btn-xs" data-page="${key}:0" ${S.page[key] ? '' : 'disabled'}>«</button>
      <button class="btn btn-xs" data-page="${key}:${S.page[key]-1}" ${S.page[key] ? '' : 'disabled'}>‹</button>
      <span style="padding:0 6px">${S.page[key]+1} / ${pages}</span>
      <button class="btn btn-xs" data-page="${key}:${S.page[key]+1}" ${S.page[key] >= pages-1 ? 'disabled' : ''}>›</button>
      <button class="btn btn-xs" data-page="${key}:${pages-1}" ${S.page[key] >= pages-1 ? 'disabled' : ''}>»</button>
    </span>`;
}

async function loadAgents() {
  try {
    const d = await admin('agents.list');
    if (S.view === 'overview') { $('ov-agent-count').textContent = `${d.online} / ${d.known}`; return; }

    const q = ($('ag-search').value || '').toLowerCase();
    const st = $('ag-status').value;
    let rows = d.agents.filter(a => {
      if (st === 'online' && !a.online) return false;
      if (st === 'offline' && a.online) return false;
      if (!q) return true;
      return (a.name + (a.capabilities||[]).join(' ') + (a.roles||[]).join(' ')).toLowerCase().includes(q);
    });

    $('ag-meta').textContent = `${d.online} en ligne · ${d.known} connus`;
    const page = rows.slice(S.page.agents * S.PER_PAGE, (S.page.agents + 1) * S.PER_PAGE);

    $('ag-rows').innerHTML = page.length ? page.map(a => `
      <tr>
        <td><span class="name">${esc(a.name)}</span><div class="sub-id">${esc((a.agent_id||'').slice(0,8))}</div></td>
        <td><span class="st ${a.online ? 'on' : 'off'}"><span class="dot ${a.online ? 'up' : 'down'}"></span>${a.online ? 'ONLINE' : 'OFFLINE'}</span></td>
        <td class="mono" style="color:var(--muted)">${esc(a.org_id || '—')}</td>
        <td>${(a.roles||[]).map(r => `<span class="tag">${esc(r)}</span>`).join('') || '—'}</td>
        <td style="color:var(--muted)">${esc((a.capabilities||[]).join(', ') || '—')}</td>
        <td>${a.encrypted ? '🔒' : '<span style="color:var(--dim)">🔓</span>'}</td>
        <td class="mono" style="font-size:10.5px;color:var(--dim)">${(a.roles||[]).includes('service_account') ? 'clé' : 'déclaré'}</td>
        <td class="num" style="color:${a.pending_tasks ? 'var(--amber)' : 'var(--dim)'}">${a.pending_tasks}</td>
        <td style="text-align:right">${a.online ? `<button class="btn btn-danger btn-xs" data-kick="${esc(a.name)}">Déconnecter</button>` : ''}</td>
      </tr>`).join('') : '<tr><td colspan="9" class="empty">Aucun agent.</td></tr>';

    pager('ag-pager', rows.length, 'agents');
  } catch (e) { toast(e.message, true); }
}

const TASK_ST = { pending: ['wait','PENDING'], running: ['run','RUNNING'],
                  completed: ['on','COMPLETED'], failed: ['fail','FAILED'] };

async function loadTasks() {
  try {
    const status = $('tk-filter').value;
    const d = await admin('tasks.list', Object.assign({ limit: 500 }, status ? { status } : {}));
    const q = ($('tk-search').value || '').toLowerCase();
    let rows = q ? d.tasks.filter(t => (t.title + t.assignee + t.orchestrator).toLowerCase().includes(q)) : d.tasks;

    $('tk-meta').textContent = `${rows.length} tâche(s)${status ? ' · ' + status : ''}`;
    const page = rows.slice(S.page.tasks * S.PER_PAGE, (S.page.tasks + 1) * S.PER_PAGE);

    $('tk-rows').innerHTML = page.length ? page.map(t => {
      const [cls, lbl] = TASK_ST[t.status] || ['off', String(t.status).toUpperCase()];
      const done = t.status === 'completed' || t.status === 'failed';
      return `<tr>
        <td>${esc(t.title)} ${t.encrypted_payload ? '<span title="Charge chiffrée E2E">🔒</span>' : ''}
          <div class="sub-id">${esc(t.task_id.slice(0,8))}</div></td>
        <td><span class="st ${cls}">${lbl}</span>${t.error_message
          ? `<div class="sub-id" style="color:var(--red);max-width:190px;white-space:normal">${esc(t.error_message)}</div>` : ''}</td>
        <td class="mono" style="font-size:11px">${esc(t.orchestrator)}</td>
        <td class="mono" style="font-size:11px">${esc(t.assignee)}</td>
        <td class="num" style="color:var(--dim)">${ago(t.created_at)}</td>
        <td class="num" style="color:var(--muted)">${ago(t.updated_at)}</td>
        <td style="text-align:right">
          ${done ? '' : `<button class="btn btn-danger btn-xs" data-cancel="${esc(t.task_id)}">Annuler</button> `}
          <button class="btn btn-xs" data-retry="${esc(t.task_id)}">Relancer</button></td>
      </tr>`;
    }).join('') : '<tr><td colspan="7" class="empty">Aucune tâche.</td></tr>';

    pager('tk-pager', rows.length, 'tasks');
  } catch (e) { toast(e.message, true); }
}

async function loadAudit() {
  try {
    const d = await admin('audit.list', { limit: 1000 });
    const q = ($('au-search').value || '').toLowerCase();
    let rows = q ? d.entries.filter(e => (e.event_type + e.sender + (e.target||'')).toLowerCase().includes(q)) : d.entries;

    $('au-meta').textContent = `${d.chain_length} entrée(s) chaînée(s)`;
    $('au-banner').innerHTML = d.intact
      ? `<div class="banner ok">✓ Chaîne intègre — les ${d.chain_length} entrées se vérifient mutuellement.</div>`
      : `<div class="banner bad">🚨 CHAÎNE ROMPUE — le journal a été modifié en dehors du Hub.
         Traitez-le comme compromis et enquêtez avant de poursuivre.</div>`;

    const page = rows.slice(S.page.audit * S.PER_PAGE, (S.page.audit + 1) * S.PER_PAGE);
    $('au-rows').innerHTML = page.length ? page.map(e => {
      const lv = e.event_type.includes('DENIED') || e.event_type.includes('FAILED') ? 'error'
               : e.event_type.startsWith('ADMIN') ? 'admin'
               : e.event_type.startsWith('TASK') ? 'task'
               : e.event_type.includes('DISCONNECT') ? 'warn' : 'info';
      const meta = JSON.stringify(e.metadata || {});
      return `<tr>
        <td class="num" style="color:var(--dim)">${e.index}</td>
        <td class="num" style="color:var(--muted)">${hhmmss(e.timestamp)}</td>
        <td><span class="lv ${lv}" style="display:inline-block;width:auto;padding:1px 7px">${esc(e.event_type)}</span></td>
        <td class="mono" style="font-size:11px">${esc(e.sender)}</td>
        <td class="mono" style="font-size:11px;color:var(--muted)">${esc(e.target || '—')}</td>
        <td class="mono" style="font-size:10.5px;color:var(--dim);max-width:280px;overflow:hidden;text-overflow:ellipsis"
            title="${esc(meta)}">${esc(meta === '{}' ? '—' : meta)}</td>
        <td class="mono" style="font-size:10px;color:var(--dim)">${esc(e.hash.slice(0,12))}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="7" class="empty">Aucune entrée.</td></tr>';

    pager('au-pager', rows.length, 'audit');
  } catch (e) { toast(e.message, true); }
}

async function loadKeys() {
  try {
    const d = await admin('apikeys.list');
    $('kt-meta').textContent = `${d.keys.length} clé(s) · ${d.source}`;
    if (!d.mutable) toast("Clés en lecture seule : elles viennent de l'environnement.", true);

    $('kt-rows').innerHTML = d.keys.length ? d.keys.map(k => `
      <tr>
        <td class="name">${esc(k.fingerprint)}</td>
        <td>${esc(k.label || '—')}</td>
        <td class="mono" style="font-size:11px">${esc(k.org_id)}</td>
        <td>${(k.roles||[]).map(r => `<span class="tag">${esc(r)}</span>`).join('')}</td>
        <td style="color:var(--muted)">${esc((k.permissions||[]).join(', ') || '—')}</td>
        <td class="num" style="color:var(--dim)">${k.created_at ? ago(k.created_at) : '—'}</td>
        <td style="text-align:right">${d.mutable
          ? `<button class="btn btn-danger btn-xs" data-revoke="${esc(k.fingerprint)}">Révoquer</button>` : ''}</td>
      </tr>`).join('') : '<tr><td colspan="7" class="empty">Aucun compte de service.</td></tr>';
  } catch (e) { toast(e.message, true); }
}

const LOADERS = { overview: loadOverview, agents: loadAgents, tasks: loadTasks, audit: loadAudit, keys: loadKeys };

function render() {
  for (const v of Object.keys(LOADERS)) $('view-' + v).style.display = v === S.view ? '' : 'none';
  document.querySelectorAll('#tabs a').forEach(a => a.classList.toggle('on', a.dataset.view === S.view));
  LOADERS[S.view]();
}

// --------------------------------------------------------------- modales

const openModal = (id) => $(id).classList.add('on');
const closeModals = () => document.querySelectorAll('.modal').forEach(m => m.classList.remove('on'));
let confirmFn = null;
function confirmAction(title, text, fn) {
  $('cf-title').textContent = title; $('cf-text').textContent = text;
  confirmFn = fn; openModal('modal-confirm');
}

// ------------------------------------------------------------ événements

$('connect-btn').onclick = async () => {
  const url = $('hub-url').value.trim(), key = $('api-key').value.trim(), err = $('login-error');
  err.style.display = 'none';
  if (!key) { err.textContent = "Une clé d'API est requise."; err.style.display = 'block'; return; }

  const btn = $('connect-btn');
  btn.disabled = true; btn.textContent = 'Connexion…';
  try {
    await connect(url, key);
    S.url = url; S.key = key;

    // Sonde immédiate : une clé sans rôle admin passe l'enregistrement mais
    // échoue ici. Mieux vaut le dire tout de suite qu'après trois clics.
    try { await admin('hub.info'); }
    catch (e) {
      try { S.ws.close(); } catch (_) {}
      S.token = null;
      err.textContent = e.message; err.style.display = 'block';
      return;
    }

    $('login').style.display = 'none';
    $('app').classList.add('on');
    $('avatar').textContent = (S.org || 'NX').slice(0, 2).toUpperCase();
    render();
  } catch (e) {
    err.textContent = e.message; err.style.display = 'block';
  } finally { btn.disabled = false; btn.textContent = 'Se connecter'; }
};

$('api-key').addEventListener('keydown', e => { if (e.key === 'Enter') $('connect-btn').click(); });

$('logout-btn').onclick = () => {
  if (S.reconnect) { clearInterval(S.reconnect); S.reconnect = null; }
  try { S.ws.close(); } catch (_) {}
  S.ws = null; S.token = null; S.key = null; S.logs = [];
  S.series = { agents: [], tasks: [], audit: [], keys: [] };
  $('app').classList.remove('on');
  $('login').style.display = 'flex';
  $('api-key').value = '';
};

$('tabs').addEventListener('click', e => {
  const a = e.target.closest('a[data-view]');
  if (a) { S.view = a.dataset.view; render(); }
});

['ag-search','ag-status','tk-search','tk-filter','au-search'].forEach(id => {
  const el = $(id);
  const key = id.startsWith('ag') ? 'agents' : id.startsWith('tk') ? 'tasks' : 'audit';
  el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
    S.page[key] = 0; LOADERS[S.view]();
  });
});

$('log-level').onchange = drawLogs;
$('log-pause').onclick = () => {
  S.logsPaused = !S.logsPaused;
  $('log-pause').textContent = S.logsPaused ? '▶' : '❚❚';
  if (!S.logsPaused) drawLogs();
};

document.addEventListener('click', async (e) => {
  const t = e.target;
  if (t.hasAttribute('data-close') || t.classList.contains('modal')) return closeModals();
  if (t.dataset.act === 'refresh') return LOADERS[S.view]();
  if (t.dataset.act === 'clear-logs') { S.logs = []; return drawLogs(); }
  if (t.dataset.act === 'new-key') return openModal('modal-key');

  if (t.dataset.page) {
    const [key, n] = t.dataset.page.split(':');
    S.page[key] = Math.max(0, parseInt(n, 10));
    return LOADERS[S.view]();
  }

  if (t.dataset.act === 'verify') {
    try {
      const v = await admin('audit.verify');
      toast(v.intact ? `Chaîne intègre : ${v.chain_length} entrées vérifiées.`
                     : `CHAÎNE ROMPUE à l'entrée ${v.broken_at_index}.`, !v.intact);
      loadAudit();
    } catch (err) { toast(err.message, true); }
    return;
  }

  if (t.dataset.kick) {
    const name = t.dataset.kick;
    return confirmAction('Déconnecter cet agent ?',
      `${name} sera immédiatement déconnecté. Il pourra revenir, et ses tâches inachevées lui seront alors réassignées.`,
      async () => { await admin('agent.disconnect', { name }); toast(`${name} déconnecté.`); loadAgents(); });
  }
  if (t.dataset.cancel) {
    const id = t.dataset.cancel;
    return confirmAction('Annuler cette tâche ?',
      "Elle sera marquée comme échouée. Son exécutant, s'il travaille déjà dessus, ne sera pas interrompu.",
      async () => { await admin('task.cancel', { task_id: id }); toast('Tâche annulée.'); loadTasks(); });
  }
  if (t.dataset.retry) {
    try {
      const r = await admin('task.retry', { task_id: t.dataset.retry });
      toast(r.delivered ? 'Tâche renvoyée à son exécutant.'
                        : 'Exécutant hors ligne : la tâche lui sera poussée à sa reconnexion.');
      loadTasks();
    } catch (err) { toast(err.message, true); }
    return;
  }
  if (t.dataset.revoke) {
    const fp = t.dataset.revoke;
    return confirmAction('Révoquer cette clé ?',
      `La clé ${fp}… cessera immédiatement de fonctionner. Irréversible : une clé révoquée ne se restaure pas.`,
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
    ['nk-org','nk-label','nk-perms'].forEach(id => { $(id).value = ''; });
    loadKeys();
  } catch (e) { toast(e.message, true); }
};

$('rv-copy').onclick = async () => {
  try { await navigator.clipboard.writeText($('rv-key').textContent); toast('Clé copiée.'); }
  catch (_) { toast('Copie impossible — sélectionnez la clé manuellement.', true); }
};

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModals(); });

setInterval(() => {
  $('sb-clock').textContent = new Date().toLocaleTimeString('fr-FR', { hour12: false }) + ' ' +
    Intl.DateTimeFormat().resolvedOptions().timeZone;
}, 1000);

// Échantillonnage des séries + rattrapage de ce que la télémétrie ne couvre
// pas (compteurs, expirations). L'audit est exclu : trop coûteux à recharger.
setInterval(() => {
  if (!S.token) return;
  if (S.view === 'overview') loadOverview();
  else if (S.view !== 'audit') LOADERS[S.view]();
}, 15000);
