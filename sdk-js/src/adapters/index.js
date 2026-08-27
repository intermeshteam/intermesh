/**
 * Ponts vers les frameworks d'agents existants (JS/TS).
 *
 * Miroir de `nexus_sdk.adapters` côté Python. CrewAI et AutoGen n'ont pas
 * d'équivalent JS établi ; seuls LangChain.js et LlamaIndex.TS ont un
 * pont dédié ici. Tout autre objet exposant `invoke`, `run`, `call`,
 * `query`, `chat` ou `predict` — ou simplement appelable — fonctionne
 * avec `adapt()` sans pont spécifique.
 *
 *   import { adapt } from 'nexus-mesh/adapters';
 *
 *   const agent = adapt(monAgentExistant, {
 *     name: 'analyste', capabilities: ['market_analysis'],
 *   });
 *   await agent.connect();
 */

export { AdapterError, NexusAdapter, adapt, detectInvoker, toJsonable } from './base.js';
export { NexusLangChainAdapter } from './langchain.js';
export { NexusLlamaIndexAdapter } from './llamaindex.js';
