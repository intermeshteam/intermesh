/**
 * Cœur des adaptateurs JS : détection de la convention d'appel et pontage.
 *
 * Miroir du module Python `nexus_sdk.adapters.base`, pour la même raison :
 * un développeur ne réécrira pas son agent LangChain.js ou LlamaIndex.TS
 * pour essayer un protocole. Ce module détecte comment appeler l'objet
 * qu'on lui confie plutôt que d'imposer une interface.
 *
 * Il n'importe aucun framework — voir `adapters/index.js`.
 */

import { NexusAgent } from '../index.js';

export class AdapterError extends Error {}

// Méthodes d'invocation connues, par ordre de préférence. Contrairement au
// SDK Python, le JS n'a pas de distinction syntaxique sync/async : une
// méthode `invoke` peut très bien renvoyer une Promise. `_call` gère les
// deux cas au lieu de choisir la méthode sur ce critère.
const INVOKERS = ['invoke', 'run', 'call', 'query', 'chat', 'predict'];

export function detectInvoker(obj, prefer = null) {
  const typeName = obj?.constructor?.name || typeof obj;

  if (prefer) {
    const fn = obj?.[prefer];
    if (typeof fn !== 'function') {
      throw new AdapterError(`'${prefer}' n'existe pas ou n'est pas une fonction sur ${typeName}.`);
    }
    return { fn: fn.bind(obj), methodName: prefer };
  }

  for (const name of INVOKERS) {
    const fn = obj?.[name];
    // Toute fonction JS hérite de `call`/`apply`/`bind` via
    // `Function.prototype` : sans cette exclusion, une simple fonction
    // passée à `adapt()` se ferait « détecter » sa propre méthode `call`
    // héritée, invoquée avec le payload comme `this` au lieu du premier
    // argument.
    if (typeof fn === 'function' && fn !== Function.prototype[name]) {
      return { fn: fn.bind(obj), methodName: name };
    }
  }

  if (typeof obj === 'function') {
    return { fn: obj, methodName: obj.name || '<anonymous>' };
  }

  throw new AdapterError(
    `${typeName} n'expose aucune méthode d'invocation connue ` +
    `(${INVOKERS.join(', ')}) et n'est pas appelable. ` +
    `Précisez-la avec invokeMethod.`
  );
}

// Attributs où les frameworks rangent le texte utile de leur objet de
// sortie, quand celui-ci n'est pas un littéral directement exploitable.
const OUTPUT_ATTRS = ['raw', 'content', 'output', 'text', 'result', 'response', 'answer'];

function isPlain(value) {
  if (value === null || typeof value !== 'object') return true;
  if (Array.isArray(value)) return true;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

/**
 * Ramène une sortie de framework à quelque chose qui passe sur le fil.
 *
 * `JSON.stringify` ne lève pas sur les instances de classe comme le ferait
 * `json.dumps` en Python : il sérialise leurs propriétés énumérables sans
 * se plaindre. Sans traitement, un `Response` LlamaIndex.TS partirait donc
 * avec ses `sourceNodes` complets plutôt que son texte. On cherche
 * l'attribut porteur du texte sur toute instance qui n'est pas déjà un
 * littéral (objet, tableau, primitive).
 */
export function toJsonable(value) {
  if (isPlain(value)) {
    if (Array.isArray(value)) return value.map(toJsonable);
    if (value !== null && typeof value === 'object') {
      const out = {};
      for (const k of Object.keys(value)) out[k] = toJsonable(value[k]);
      return out;
    }
    return value;
  }

  for (const attr of OUTPUT_ATTRS) {
    if (attr in value && typeof value[attr] !== 'function') {
      return toJsonable(value[attr]);
    }
  }

  if (typeof value.toJSON === 'function') {
    try {
      return toJsonable(value.toJSON());
    } catch {
      // se rabat sur la conversion en chaîne ci-dessous
    }
  }

  return String(value);
}

/**
 * Un `NexusAgent` dont le travail est délégué à un agent étranger.
 *
 * S'utilise exactement comme un agent Nexus natif : il se connecte, se
 * fait découvrir par ses capacités, reçoit des tâches et des requêtes, et
 * rend ses résultats chiffrés de bout en bout.
 */
export class NexusAdapter extends NexusAgent {
  /**
   * @param {*} wrapped L'agent existant à exposer.
   * @param {object} opts
   * @param {string} opts.name Nom de l'agent sur le réseau Nexus.
   * @param {string[]} [opts.capabilities] Ce qu'il sait faire.
   * @param {string} [opts.inputKey] Extrait une seule valeur du dict de la
   *   tâche avant l'appel — utile pour les agents qui attendent une
   *   chaîne, pas un objet.
   * @param {(data:*)=>*} [opts.inputAdapter] Transformation complète de
   *   l'entrée. Prime sur `inputKey`.
   * @param {(result:*)=>*} [opts.outputAdapter] Transformation de la
   *   sortie avant renvoi.
   * @param {string} [opts.invokeMethod] Force la méthode d'invocation si
   *   la détection se trompe.
   * @param {...*} opts.rest Passés tels quels à `NexusAgent` (hubUrl,
   *   roles, permissions, metadata, encrypt…).
   */
  constructor(wrapped, opts) {
    const {
      name, capabilities, inputKey = null, inputAdapter = null,
      outputAdapter = null, invokeMethod = null, ...agentOpts
    } = opts;

    super({ name, capabilities: capabilities || [], ...agentOpts });

    this.wrapped = wrapped;
    this.inputKey = inputKey;
    this.inputAdapter = inputAdapter;
    this.outputAdapter = outputAdapter;

    const { fn, methodName } = detectInvoker(wrapped, invokeMethod);
    this._fn = fn;
    this.invokeMethod = methodName;

    // Le même pont sert aux tâches déléguées et aux requêtes directes.
    this.onTask((input, task) => this._handleTask(input, task));
    this.onRequest((content, sender) => this._handleRequest(content, sender));
  }

  _prepare(data) {
    if (this.inputAdapter) return this.inputAdapter(data);
    if (this.inputKey && data !== null && typeof data === 'object' && !Array.isArray(data)) {
      return data[this.inputKey];
    }
    return data;
  }

  _finalize(result) {
    const out = this.outputAdapter ? this.outputAdapter(result) : result;
    return toJsonable(out);
  }

  async _call(payload) {
    const result = this._fn(payload);
    return result instanceof Promise ? await result : result;
  }

  async _handleTask(inputData) {
    return this._finalize(await this._call(this._prepare(inputData)));
  }

  async _handleRequest(content) {
    return this._finalize(await this._call(this._prepare(content)));
  }
}

/**
 * Expose un agent existant sur le réseau Nexus.
 *
 *   import { adapt } from 'nexus-mesh/adapters';
 *
 *   const agent = adapt(maChaineLangChain, {
 *     name: 'analyste', capabilities: ['market_analysis'],
 *   });
 *   await agent.connect();
 */
export function adapt(wrapped, opts) {
  return new NexusAdapter(wrapped, opts);
}
