import test from 'node:test';
import assert from 'node:assert/strict';
import { InterMeshAgent } from '../src/index.js';

test('InterMeshAgent - instanciation et calcul du fingerprint d identité', () => {
  const agent = new InterMeshAgent({
    name: 'analyste',
    orgId: 'globex',
    capabilities: ['analytics', 'nlp'],
    roles: ['worker']
  });

  assert.equal(agent.name, 'analyste');
  assert.equal(agent.orgId, 'globex');
  assert.equal(agent.qualifiedName, 'globex/analyste');
  assert.ok(agent.publicKeyPem.includes('BEGIN PUBLIC KEY'));
  assert.ok(typeof agent.identity.fingerprint === 'string');
  assert.equal(agent.identity.fingerprint.length, 64);
});
