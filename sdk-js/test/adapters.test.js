/**
 * Adaptateurs vers les frameworks d'agents (JS/TS).
 *
 * Les frameworks réels ne sont pas installés — les importer ferait de
 * LangChain.js et de ses dépendances transitives un prérequis de la
 * suite de tests, alors que le SDK est précisément conçu pour ne pas en
 * dépendre. Les doublures ci-dessous reproduisent la convention d'appel
 * exacte de chaque framework.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { InterMeshAgent } from '../src/index.js';
import { AdapterError, InterMeshAdapter, adapt, detectInvoker } from '../src/adapters/base.js';
import { InterMeshLangChainAdapter } from '../src/adapters/langchain.js';
import { InterMeshLlamaIndexAdapter } from '../src/adapters/llamaindex.js';

// ----------------------------------------------------------------------
// Doublures
// ----------------------------------------------------------------------

class FakeRunnable {
  // LangChain.js : `invoke(input)`, toujours promesse.
  async invoke(data) {
    return { output: `analysé: ${data.input}` };
  }
}

class FakeSyncRunnable {
  // Un Runnable dont l'appel est synchrone — cas limite, la plupart des
  // frameworks JS renvoient une Promise, mais rien ne l'impose.
  invoke(data) {
    return { output: data.input.toUpperCase() };
  }
}

class FakeQueryEngine {
  // LlamaIndex.TS : `query({ query })` renvoyant un objet à attribut `response`.
  async query({ query }) {
    return new FakeResponse(`trouvé : ${query}`);
  }
}

class FakeResponse {
  constructor(response) {
    this.response = response;
    this.sourceNodes = [{ huge: 'payload' }]; // ne doit pas fuiter dans la sortie
  }
}

class NotAnAgent {} // Ni méthode connue, ni appelable.

// ----------------------------------------------------------------------
// Détection
// ----------------------------------------------------------------------

test('invoke est détecté en priorité sur run/call/query', () => {
  const { fn, methodName } = detectInvoker(new FakeRunnable());
  assert.equal(methodName, 'invoke');
  assert.equal(typeof fn, 'function');
});

test('un objet inutilisable échoue avec une piste', () => {
  assert.throws(() => detectInvoker(new NotAnAgent()), /invokeMethod/);
});

test('invokeMethod explicite prime sur la détection', () => {
  class Multi {
    invoke() { return 'invoke'; }
    run() { return 'run'; }
  }
  const { methodName } = detectInvoker(new Multi(), 'run');
  assert.equal(methodName, 'run');

  assert.throws(() => detectInvoker(new Multi(), 'inexistante'), /inexistante/);
});

test('une fonction simple est acceptée directement', () => {
  const { fn } = detectInvoker((d) => ({ ok: true, d }));
  assert.deepEqual(fn({ x: 1 }), { ok: true, d: { x: 1 } });
});

// ----------------------------------------------------------------------
// Pontage
// ----------------------------------------------------------------------

test('un agent LangChain.js reçoit l\'objet de tâche', async () => {
  const a = new InterMeshLangChainAdapter(new FakeRunnable(), { name: 'lc', capabilities: ['analysis'] });
  const out = await a._handleTask({ input: 'marché' });
  assert.deepEqual(out, { output: 'analysé: marché' });
  assert.deepEqual(a.identity.capabilities, ['analysis']);
});

test('LlamaIndex.TS : inputKey="query" par défaut et réponse aplatie', async () => {
  const a = new InterMeshLlamaIndexAdapter(new FakeQueryEngine(), { name: 'li', capabilities: ['rag'] });
  const out = await a._handleTask({ query: 'quota' });
  assert.equal(out, 'trouvé : quota');
});

test('une sortie synchrone traverse le pont sans await manquant', async () => {
  const a = new InterMeshLangChainAdapter(new FakeSyncRunnable(), { name: 'sync', capabilities: ['x'] });
  const out = await a._handleTask({ input: 'test' });
  assert.deepEqual(out, { output: 'TEST' });
});

test('une sortie non sérialisable ne casse jamais le fil', async () => {
  class Opaque {
    constructor() { this.socket = {}; }
  }
  const a = adapt(() => new Opaque(), { name: 'op', capabilities: ['x'] });
  const out = await a._handleTask({});
  assert.doesNotThrow(() => JSON.stringify(out));
  assert.equal(typeof out, 'string');
});

test('inputAdapter et outputAdapter transforment la charge', async () => {
  const a = adapt((s) => ({ len: s.length }), {
    name: 'custom', capabilities: ['x'],
    inputAdapter: (d) => d.texte,
    outputAdapter: (r) => ({ longueur: r.len, unite: 'caracteres' }),
  });
  const out = await a._handleTask({ texte: 'bonjour' });
  assert.deepEqual(out, { longueur: 7, unite: 'caracteres' });
});

test('l\'adaptateur répond aussi bien aux requêtes directes qu\'aux tâches', async () => {
  const a = new InterMeshLangChainAdapter(new FakeRunnable(), { name: 'both', capabilities: ['x'] });
  const out = await a._handleRequest({ input: 'ping' });
  assert.deepEqual(out, { output: 'analysé: ping' });
});

test('l\'adaptateur est un agent InterMesh à part entière', () => {
  const a = adapt((d) => d, { name: 'x', capabilities: ['c'], roles: ['worker'] });
  assert.ok(a instanceof InterMeshAgent);
  assert.deepEqual(a.identity.capabilities, ['c']);
  assert.deepEqual(a.identity.roles, ['worker']);
});

test('AdapterError est bien le type levé par detectInvoker', () => {
  assert.throws(() => detectInvoker(new NotAnAgent()), AdapterError);
});
