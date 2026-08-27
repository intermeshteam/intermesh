/**
 * `NexusPipeline`/`fanOut` composent `discover()`/`submitTask()` sans
 * toucher au fil : un orchestrateur factice suffit à les tester.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { NexusPipeline, PipelineError, fanOut } from '../src/pipeline.js';

class FakeOrchestrator {
  constructor(agentsByCapability, outputsByTitle) {
    this.agentsByCapability = agentsByCapability;
    this.outputsByTitle = outputsByTitle;
    this.calls = [];
  }

  async discover({ capabilities = [] }) {
    for (const cap of capabilities) {
      if (this.agentsByCapability[cap]) {
        return { count: 1, agents: [{ name: this.agentsByCapability[cap] }] };
      }
    }
    return { count: 0, agents: [] };
  }

  async submitTask(title, assignee, inputData) {
    this.calls.push([title, assignee, inputData]);
    if (!(title in this.outputsByTitle)) {
      throw new Error(`pas de sortie configurée pour '${title}'`);
    }
    const result = this.outputsByTitle[title];
    if (result instanceof Error) throw result;
    return result;
  }
}

// ----------------------------------------------------------------------
// NexusPipeline
// ----------------------------------------------------------------------

test('la sortie d\'une étape alimente l\'entrée de la suivante', async () => {
  const orch = new FakeOrchestrator(
    { translate: 'traducteur', calculate: 'calculateur' },
    { Traduire: { translated_text: '42 * 2' }, Calculer: { result: 84 } },
  );
  const pipeline = new NexusPipeline(orch)
    .step('Traduire', { capabilities: ['translate'] })
    .step('Calculer', {
      capabilities: ['calculate'],
      inputFn: (prev) => ({ expression: prev.translated_text }),
    });

  const out = await pipeline.run({ text: 'compute forty two doubled' });

  assert.deepEqual(out.output, { result: 84 });
  assert.deepEqual(out.history.map((s) => s.title), ['Traduire', 'Calculer']);
  assert.deepEqual(orch.calls[1], ['Calculer', 'calculateur', { expression: '42 * 2' }]);
});

test('la découverte est différée jusqu\'à l\'exécution', async () => {
  const orch = new FakeOrchestrator({}, { Étape: 'ok' });
  const pipeline = new NexusPipeline(orch).step('Étape', { capabilities: ['x'] });

  orch.agentsByCapability.x = 'venu_en_retard';
  const out = await pipeline.run();

  assert.equal(out.output, 'ok');
  assert.equal(out.history[0].agent, 'venu_en_retard');
});

test('un agent explicite court-circuite la découverte', async () => {
  const orch = new FakeOrchestrator({}, { Étape: 'ok' });
  const pipeline = new NexusPipeline(orch).step('Étape', { agent: 'nommé_directement' });
  await pipeline.run();

  assert.equal(orch.calls[0][1], 'nommé_directement');
});

test('aucun agent trouvé lève une PipelineError explicite', async () => {
  const orch = new FakeOrchestrator({}, {});
  const pipeline = new NexusPipeline(orch).step('Étape', { capabilities: ['introuvable'] });

  await assert.rejects(() => pipeline.run(), PipelineError);
});

test('l\'échec d\'une étape arrête les suivantes', async () => {
  const orch = new FakeOrchestrator(
    { a: 'agent_a', b: 'agent_b' },
    { A: new Error('échec distant') },
  );
  const pipeline = new NexusPipeline(orch)
    .step('A', { capabilities: ['a'] })
    .step('B', { capabilities: ['b'] });

  await assert.rejects(() => pipeline.run(), /échec distant/);
  assert.equal(orch.calls.length, 1, 'B ne doit jamais être soumise');
});

test('une étape sans agent ni critère est rejetée à la déclaration', () => {
  assert.throws(() => new NexusPipeline(new FakeOrchestrator({}, {})).step('Étape'), PipelineError);
});

test('un pipeline vide est rejeté à l\'exécution', async () => {
  await assert.rejects(() => new NexusPipeline(new FakeOrchestrator({}, {})).run(), PipelineError);
});

// ----------------------------------------------------------------------
// fanOut
// ----------------------------------------------------------------------

test('fanOut regroupe les branches parallèles par clé', async () => {
  const orch = new FakeOrchestrator({}, { fr: { revenue: 1 }, de: { revenue: 2 } });
  const results = await fanOut(orch, [['fr', { region: 'FR' }], ['de', { region: 'DE' }]], {
    agents: { fr: 'marché_fr', de: 'marché_de' },
  });
  assert.deepEqual(results, { fr: { revenue: 1 }, de: { revenue: 2 } });
});

test('fanOut isole une branche en échec', async () => {
  const orch = new FakeOrchestrator({}, { ok: 'résultat', ko: new Error('boom') });
  const results = await fanOut(orch, [['ok', {}], ['ko', {}]], {
    agents: { ok: 'a', ko: 'b' },
  });
  assert.equal(results.ok, 'résultat');
  assert.ok(results.ko instanceof Error);
});

test('fanOut découvre par capacité, par branche', async () => {
  const orch = new FakeOrchestrator({ cap_a: 'agent_a', cap_b: 'agent_b' }, { a: 'ra', b: 'rb' });
  const results = await fanOut(orch, [['a', {}], ['b', {}]], {
    capabilities: { a: ['cap_a'], b: ['cap_b'] },
  });
  assert.deepEqual(results, { a: 'ra', b: 'rb' });
});
