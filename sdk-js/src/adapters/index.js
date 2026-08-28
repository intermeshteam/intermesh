/**
 * Ponts vers les frameworks d'agents existants (JS/TS).
 *
 * Miroir de `intermesh.adapters` côté Python. CrewAI et AutoGen n'ont pas
 * d'équivalent JS établi ; seuls LangChain.js et LlamaIndex.TS ont un
 * pont dédié ici. Tout autre objet exposant `invoke`, `run`, `call`,
 * `query`, `chat` ou `predict` — ou simplement appelable — fonctionne
 * avec `adapt()` sans pont spécifique.
 *
 *   import { adapt } from 'intermesh/adapters';
 *
 *   const agent = adapt(monAgentExistant, {
 *     name: 'analyste', capabilities: ['market_analysis'],
 *   });
 *   await agent.connect();
 */

export { AdapterError, InterMeshAdapter, adapt, detectInvoker, toJsonable } from './base.js';
export { InterMeshLangChainAdapter } from './langchain.js';
export { InterMeshLlamaIndexAdapter } from './llamaindex.js';
