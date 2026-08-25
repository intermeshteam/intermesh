let taskCount = 0;
let agentsMap = {};

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function logEvent(text, type = 'info') {
  const feed = document.getElementById('event-feed');
  const el = document.createElement('div');
  
  const time = new Date().toLocaleTimeString();
  let color = 'text-slate-400';
  let badge = 'INFO';

  if (type === 'connect') { color = 'text-nexus-cyan'; badge = 'JOIN'; }
  if (type === 'disconnect') { color = 'text-red-400'; badge = 'LEFT'; }
  if (type === 'task') { color = 'text-nexus-emerald'; badge = 'TASK'; }
  if (type === 'msg') { color = 'text-nexus-amber'; badge = 'MESG'; }

  el.className = 'p-2 rounded bg-nexus-bg/60 border border-nexus-border/50 flex flex-col space-y-1';
  el.innerHTML = `
    <div class="flex justify-between items-center text-[10px] text-slate-500">
      <span class="font-bold ${color}">[${badge}]</span>
      <span>${time}</span>
    </div>
    <div class="${color}">${text}</div>
  `;

  feed.prepend(el);
}

function updateAgentsTable() {
  const tbody = document.getElementById('agents-table-body');
  const countBadge = document.getElementById('agent-count-badge');
  const statAgents = document.getElementById('stat-agents');
  
  const agents = Object.values(agentsMap);
  statAgents.textContent = agents.length;
  countBadge.textContent = `${agents.length} en ligne`;

  if (agents.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-600">En attente de connexion d\'agents...</td></tr>';
    return;
  }

  tbody.innerHTML = agents.map(a => `
    <tr class="hover:bg-nexus-border/30 transition-colors">
      <td class="py-3 font-semibold text-nexus-cyan">${a.name}</td>
      <td class="py-3"><span class="px-2 py-0.5 rounded bg-nexus-border text-slate-300">${a.roles.join(', ') || 'standard'}</span></td>
      <td class="py-3 text-slate-400">${a.capabilities.join(', ') || 'aucune'}</td>
      <td class="py-3 text-slate-500 font-mono text-[10px]">${a.fingerprint ? a.fingerprint.substring(0, 16) + '...' : 'N/A'}</td>
      <td class="py-3 text-right">
        <span class="inline-flex items-center space-x-1 text-nexus-emerald font-semibold">
          <span class="w-1.5 h-1.5 rounded-full bg-nexus-emerald"></span>
          <span>ONLINE</span>
        </span>
      </td>
    </tr>
  `).join('');
}

function connectToHub() {
  const ws = new WebSocket('ws://localhost:8765');

  ws.onopen = () => {
    // S'enregistrer en tant qu'observateur du dashboard
    ws.send(JSON.stringify({
      id: crypto.randomUUID(),
      version: 'nexus/v1',
      type: 'register',
      sender: 'nexus_dashboard_observer',
      content: {
        agent_id: 'dashboard-observer',
        name: 'nexus_dashboard_observer',
        roles: ['admin', 'observer'],
        capabilities: ['telemetry_read']
      }
    }));
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);

      if (msg.type === 'telemetry_event') {
        const ev = msg.content;
        
        if (ev.event === 'agent_connected') {
          agentsMap[ev.agent.name] = ev.agent;
          updateAgentsTable();
          logEvent(`Agent connecté : ${ev.agent.name} (${ev.agent.roles.join(', ')})`, 'connect');
        } 
        else if (ev.event === 'agent_disconnected') {
          delete agentsMap[ev.agent_name];
          updateAgentsTable();
          logEvent(`Agent déconnecté : ${ev.agent_name}`, 'disconnect');
        }
        else if (ev.event === 'task_submitted') {
          taskCount++;
          document.getElementById('stat-tasks').textContent = taskCount;
          logEvent(`Tâche : '${ev.title}' (${ev.orchestrator} ➜ ${ev.assignee})`, 'task');
        }
        else if (ev.event === 'task_completed') {
          logEvent(`✓ Tâche terminée : ID ${ev.task_id.substring(0, 8)}...`, 'task');
        }
        else if (ev.event === 'message_routed') {
          logEvent(`Message E2E : ${ev.sender} ➜ ${ev.to}`, 'msg');
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  ws.onclose = () => {
    document.getElementById('connection-status').innerHTML = `
      <span class="w-2 h-2 rounded-full bg-red-500"></span>
      <span class="text-red-400">HUB DÉCONNECTÉ (Tentative reconnexion...)</span>
    `;
    setTimeout(connectToHub, 2000);
  };
}

document.addEventListener('DOMContentLoaded', () => {
  initIcons();
  connectToHub();
});
