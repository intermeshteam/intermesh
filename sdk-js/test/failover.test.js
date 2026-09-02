/**
 * Reconnexion et bascule vers un Hub frère.
 *
 * Le SDK JavaScript n'avait aucune logique de reconnexion : `hubUrl` était
 * une adresse unique, et un agent dont le Hub mourait s'arrêtait là. Le SDK
 * Python savait déjà basculer ; l'écart portait précisément sur le scénario
 * qui compte en production, la perte d'un nœud.
 *
 * Les tests ci-dessous ne montent pas de Hub : ils vérifient la logique de
 * décision, seule partie qu'on peut éprouver sans réseau. La bascule
 * elle-même a été mesurée contre une grappe réelle de cinq Hubs — 0,14 s,
 * une seule bascule annoncée — et cette mesure vit dans docs/BENCHMARKS.md
 * plutôt qu'ici, un test qui démarre PostgreSQL et cinq processus n'ayant
 * pas sa place dans une suite qui tourne en une seconde.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { InterMeshAgent } from '../src/index.js';

function agent(hubUrl, options = {}) {
  return new InterMeshAgent({ name: 'a', hubUrl, encrypt: false, ...options });
}

test('une adresse unique reste acceptée', () => {
  const a = agent('ws://seul:8765');
  assert.deepEqual(a._hubCandidates, ['ws://seul:8765']);
  assert.equal(a.hubUrl, 'ws://seul:8765');
});

test('plusieurs adresses sont conservées dans l’ordre donné', () => {
  const a = agent(['ws://un:8765', 'ws://deux:8765']);
  assert.deepEqual(a._hubCandidates, ['ws://un:8765', 'ws://deux:8765']);
  assert.equal(a.hubUrl, 'ws://un:8765');
});

test('les frères sont ajoutés, jamais substitués', () => {
  // L'adresse qu'a écrite l'exploitant reste la première essayée : c'est
  // souvent celle qui est la plus proche, ou la seule autorisée par un
  // pare-feu.
  const a = agent('ws://principal:8765');
  a._learnSiblings(['ws://frere-1:8765', 'ws://frere-2:8765']);
  assert.equal(a._hubCandidates[0], 'ws://principal:8765');
  assert.ok(a._hubCandidates.includes('ws://frere-1:8765'));
  assert.ok(a._hubCandidates.includes('ws://frere-2:8765'));
});

test('doublons et valeurs aberrantes sont ignorés', () => {
  const a = agent('ws://principal:8765');
  a._learnSiblings(['ws://principal:8765', '', null, 42, {}, 'ws://frere:8765']);
  assert.deepEqual(a._hubCandidates, ['ws://principal:8765', 'ws://frere:8765']);
});

test('un Hub hors grappe n’annonce rien, et rien ne change', () => {
  const a = agent('ws://seul:8765');
  a._learnSiblings(undefined);
  a._learnSiblings(null);
  a._learnSiblings([]);
  assert.deepEqual(a._hubCandidates, ['ws://seul:8765']);
});

test('la reconnexion est désactivée par défaut', () => {
  // L'activer d'office changerait le comportement des agents existants
  // sans qu'ils l'aient demandé : un agent qui s'arrêtait à la
  // déconnexion se mettrait soudain à réessayer indéfiniment.
  assert.equal(agent('ws://x:8765').autoReconnect, false);
  assert.equal(agent('ws://x:8765', { autoReconnect: true }).autoReconnect, true);
});

test('les échanges en cours sont abandonnés à la rupture du lien', async () => {
  // Sans cela, l'appelant reste suspendu sur une socket qui ne répondra
  // jamais — l'agent paraît fonctionner alors qu'il est déconnecté.
  const a = agent('ws://x:8765');
  const pending = new Promise((resolve, reject) => {
    a.pendingRequests['abc'] = { resolve, reject };
  });
  a._failPending(new Error('lien interrompu'));

  await assert.rejects(pending, /lien interrompu/);
  assert.deepEqual(Object.keys(a.pendingRequests), []);
});

test('close() interdit toute reconnexion ultérieure', async () => {
  const a = agent('ws://x:8765', { autoReconnect: true });
  assert.equal(a._closing, false);
  await a.close();
  assert.equal(a._closing, true);
});
