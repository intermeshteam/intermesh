/**
 * Pont LlamaIndex.TS → InterMesh.
 *
 *   import { InterMeshLlamaIndexAdapter } from 'intermesh/adapters/llamaindex';
 *
 *   const agent = new InterMeshLlamaIndexAdapter(index.asQueryEngine(), {
 *     name: 'base_documentaire', capabilities: ['document_search', 'rag'],
 *   });
 *   await agent.connect();
 *
 * Un moteur de requête attend un objet `{ query: "..." }`, pas une chaîne
 * brute : contrairement à l'API Python (`query(str)`), LlamaIndex.TS
 * exige la forme objet. `inputKey` vaut `'query'` par défaut, de sorte
 * qu'une tâche InterMesh `{ query: "..." }` est extraite puis reconditionnée
 * dans la même forme avant l'appel. Pour un moteur de chat
 * (`chat({ message })`), passez `inputKey: 'message'`.
 *
 * Ce module n'importe pas `llamaindex` : voir `adapters/base.js`.
 */

import { InterMeshAdapter } from './base.js';

export class InterMeshLlamaIndexAdapter extends InterMeshAdapter {
  /**
   * @param {*} engine Résultat de `index.asQueryEngine()`,
   *   `index.asChatEngine()`, ou un agent LlamaIndex.TS.
   * @param {object} opts
   * @param {string} [opts.inputKey='query'] Clé extraite de l'objet de
   *   tâche, puis utilisée pour reconstruire l'objet attendu par le moteur.
   * @param {(data:*)=>*} [opts.inputAdapter] Transformation complète de
   *   l'entrée ; prime sur `inputKey` et son reconditionnement automatique.
   */
  constructor(engine, opts) {
    const { inputKey = 'query', inputAdapter, ...rest } = opts;
    const adapter = inputAdapter || ((data) => ({
      [inputKey]: (data !== null && typeof data === 'object') ? data[inputKey] : data,
    }));
    super(engine, { inputAdapter: adapter, ...rest });
  }
}
