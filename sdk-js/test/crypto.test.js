import test from 'node:test';
import assert from 'node:assert/strict';
import { InterMeshCrypto } from '../src/index.js';

test('InterMeshCrypto - cycle de génération et chiffrement RSA-OAEP + AES-GCM', () => {
  const alice = InterMeshCrypto.generateKeyPair();
  const bob = InterMeshCrypto.generateKeyPair();

  const secretMessage = { message: 'Données secrètes inter-agents', valeur: 42 };

  // Chiffrement pour Bob
  const encrypted = InterMeshCrypto.encryptFor(bob.publicKey, JSON.stringify(secretMessage));
  assert.ok(typeof encrypted === 'string');
  assert.ok(encrypted.length > 0);

  // Déchiffrement réussi avec la clé privée de Bob
  const decrypted = InterMeshCrypto.decryptWith(bob.privateKey, encrypted);
  const parsed = JSON.parse(decrypted);
  assert.deepEqual(parsed, secretMessage);

  // Échec attendu du déchiffrement avec la mauvaise clé privée (Alice)
  assert.throws(() => {
    InterMeshCrypto.decryptWith(alice.privateKey, encrypted);
  });
});
