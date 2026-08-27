/**
 * Pont LangChain.js → Nexus.
 *
 *   import { NexusLangChainAdapter } from 'nexus-mesh/adapters/langchain';
 *
 *   const agent = new NexusLangChainAdapter(monRunnable, {
 *     name: 'analyste', capabilities: ['market_analysis'],
 *   });
 *   await agent.connect();
 *
 * Ce module n'importe pas `@langchain/core` : voir `adapters/base.js` pour
 * la raison. Il fonctionne avec tout objet respectant l'interface
 * `Runnable` (`invoke`), donc aussi bien un `AgentExecutor` qu'une chaîne
 * LCEL ou un modèle de chat.
 */

import { NexusAdapter } from './base.js';

export class NexusLangChainAdapter extends NexusAdapter {
  /**
   * @param {*} runnable `AgentExecutor`, chaîne LCEL, `Runnable`…
   * @param {object} opts
   * @param {string} [opts.inputKey] Clé à extraire de l'objet de tâche.
   *   Un `AgentExecutor` attend typiquement `{ input: "..." }`, auquel cas
   *   laissez `undefined` et envoyez cet objet tel quel.
   */
  constructor(runnable, opts) {
    super(runnable, opts);
  }
}
