/**
 * Désaccord de chiffrement entre deux agents.
 *
 * Trouvé en suivant le parcours de démarrage depuis un environnement neuf :
 * un agent JS avec `encrypt: false`, sollicité par un orchestrateur Python
 * qui chiffre, recevait le texte chiffré **comme s'il s'agissait de
 * données**. Le gestionnaire le traitait, la tâche se terminait en succès,
 * et le résultat était faux — « bonjour undefined » au lieu de « bonjour
 * Adrien ».
 *
 * C'est le pire mode de défaillance pour un produit dont l'argument est le
 * chiffrement de bout en bout : silencieux, et il produit des données
 * fausses plutôt qu'un échec.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { EncryptionMismatch, InterMeshAgent, InterMeshCrypto } from '../src/index.js';

function agent(options = {}) {
  return new InterMeshAgent({ name: 'a', hubUrl: 'ws://x:8765', ...options });
}

/** Une charge chiffrée pour quelqu'un d'autre. */
function blobForSomeoneElse() {
  const other = agent({ encrypt: true });
  return InterMeshCrypto.encryptFor(other.publicKeyPem, JSON.stringify({ nom: 'Adrien' }));
}

test('une charge chiffrée est reconnue', () => {
  assert.equal(InterMeshCrypto.looksEncrypted(blobForSomeoneElse()), true);
});

test('les valeurs ordinaires ne sont pas prises pour du chiffré', () => {
  // Un faux positif serait pire que le défaut corrigé : il refuserait des
  // données parfaitement valides.
  for (const ordinary of [
    'bonjour',
    '{"a":1}',
    '',
    'aGVsbG8gd29ybGQgdGVzdCBzdHJpbmcgbG9uZw==',   // base64 valide, pas une enveloppe
    null,
    42,
    { a: 1 },
  ]) {
    assert.equal(InterMeshCrypto.looksEncrypted(ordinary), false,
      `${JSON.stringify(ordinary)} ne doit pas passer pour du chiffré`);
  }
});

test('un objet JSON aux autres clés n’est pas une enveloppe', () => {
  const payload = Buffer.from(JSON.stringify({ ek: 1, n: 2, autre: 3 })).toString('base64');
  assert.equal(InterMeshCrypto.looksEncrypted(payload), false);
});

test('un agent en clair refuse le texte chiffré au lieu de le transmettre', () => {
  const a = agent({ encrypt: false });
  assert.throws(
    () => a._unwrapIncoming(blobForSomeoneElse(), 'Contenu de tâche'),
    (err) => {
      assert.ok(err instanceof EncryptionMismatch);
      // Le message doit porter le remède : sans lui, l'utilisateur sait que
      // quelque chose ne va pas, sans savoir quoi changer.
      assert.match(err.message, /encrypt: false/);
      assert.match(err.message, /émetteur/);
      return true;
    },
  );
});

test('un agent en clair reçoit toujours les données ordinaires', () => {
  const a = agent({ encrypt: false });
  assert.deepEqual(a._unwrapIncoming({ nom: 'Adrien' }, 'x'), { nom: 'Adrien' });
  assert.equal(a._unwrapIncoming('bonjour', 'x'), 'bonjour');
});

test('un agent chiffrant refuse une charge destinée à une autre clé', () => {
  // Cas voisin : le chiffrement est bien actif, mais la charge a été
  // chiffrée pour quelqu'un d'autre. Rendre le texte chiffré serait le
  // même piège.
  const a = agent({ encrypt: true });
  assert.throws(() => a._unwrapIncoming(blobForSomeoneElse(), 'Contenu de tâche'),
    (err) => err instanceof EncryptionMismatch);
});

test('un agent chiffrant ouvre sa propre charge', () => {
  const a = agent({ encrypt: true });
  const blob = InterMeshCrypto.encryptFor(a.publicKeyPem, JSON.stringify({ nom: 'Adrien' }));
  assert.deepEqual(a._unwrapIncoming(blob, 'Contenu de tâche'), { nom: 'Adrien' });
});
