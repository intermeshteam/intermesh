/**
 * Orchestration déclarative de plusieurs agents. Miroir de
 * `intermesh.pipeline` côté Python — voir ce module pour le contexte.
 *
 *   import { InterMeshPipeline } from 'intermesh';
 *
 *   const pipeline = new InterMeshPipeline(orchestrator)
 *     .step('Traduire', { capabilities: ['translate'] })
 *     .step('Calculer', {
 *       capabilities: ['calculate'],
 *       inputFn: (prev) => ({ expression: prev.translated_text }),
 *     });
 *   const result = await pipeline.run({ text: 'compute forty two' });
 */

export class PipelineError extends Error {}

class Step {
  constructor(title, { agent = null, capabilities = [], roles = [], metadata = {}, inputFn = null, timeout = 15.0 } = {}) {
    if (!agent && capabilities.length === 0 && roles.length === 0) {
      throw new PipelineError(
        `Étape '${title}' : précisez 'agent' ou un critère de découverte (capabilities/roles).`
      );
    }
    this.title = title;
    this.agent = agent;
    this.capabilities = capabilities;
    this.roles = roles;
    this.metadata = metadata;
    this.inputFn = inputFn;
    this.timeout = timeout;
  }
}

/**
 * Enchaîne des tâches sur plusieurs agents, chacun trouvé par capacité ou
 * nommé explicitement. La sortie d'une étape est l'entrée de la suivante,
 * via `inputFn` si la forme doit changer.
 */
export class InterMeshPipeline {
  constructor(orchestrator) {
    this.orchestrator = orchestrator;
    this._steps = [];
  }

  /**
   * Ajoute une étape et retourne le pipeline, pour enchaîner les appels.
   *
   * @param {string} title Titre de la tâche InterMesh, visible dans le dashboard.
   * @param {object} opts
   * @param {string} [opts.agent] Nom exact de l'agent visé. Omis, l'agent
   *   est recherché par `capabilities`/`roles` au moment de l'exécution —
   *   pas à la déclaration, donc un agent qui rejoint le réseau
   *   entre-temps compte.
   * @param {string[]} [opts.capabilities] Critère de découverte, toutes requises.
   * @param {string[]} [opts.roles] Critère de découverte, un seul suffit.
   * @param {(prev:*)=>*} [opts.inputFn] Reçoit la sortie de l'étape
   *   précédente (ou l'entrée initiale pour la première) et produit
   *   l'entrée de celle-ci. Par défaut, transmise telle quelle.
   * @param {number} [opts.timeout=15.0] Délai d'attente de cette étape, en secondes.
   */
  step(title, opts = {}) {
    this._steps.push(new Step(title, opts));
    return this;
  }

  async _resolveAgent(step) {
    if (step.agent) return step.agent;
    const found = await this.orchestrator.discover({
      capabilities: step.capabilities, roles: step.roles, metadata: step.metadata,
    });
    if (!found.count) {
      throw new PipelineError(
        `Étape '${step.title}' : aucun agent disponible pour ` +
        `capabilities=${JSON.stringify(step.capabilities)} roles=${JSON.stringify(step.roles)}.`
      );
    }
    return found.agents[0].name;
  }

  /**
   * Exécute les étapes dans l'ordre déclaré, en série.
   *
   * Une étape en échec interrompt le pipeline sans exécuter les
   * suivantes, plutôt que de continuer sur une sortie invalide ; l'erreur
   * de `submitTask` (timeout ou échec distant) se propage telle quelle.
   *
   * @returns {Promise<{output:*, history:Array<{title:string, agent:string, output:*}>}>}
   */
  async run(initialInput = null) {
    if (this._steps.length === 0) {
      throw new PipelineError("Le pipeline n'a aucune étape.");
    }

    let result = initialInput;
    const history = [];

    for (const step of this._steps) {
      const target = await this._resolveAgent(step);
      const payload = step.inputFn ? step.inputFn(result) : result;
      result = await this.orchestrator.submitTask(step.title, target, payload);
      history.push({ title: step.title, agent: target, output: result });
    }

    return { output: result, history };
  }
}

/**
 * Soumet plusieurs tâches en parallèle et attend toutes les réponses.
 *
 * Le pendant du pipeline séquentiel : là où `InterMeshPipeline` enchaîne,
 * `fanOut` interroge plusieurs agents à la fois.
 *
 *   const results = await fanOut(orchestrator, [
 *     ['fr', { region: 'FR' }],
 *     ['de', { region: 'DE' }],
 *   ], { agents: { fr: 'marché_fr', de: 'marché_de' } });
 *
 * @param {*} orchestrator Agent InterMesh dont `discover`/`submitTask` porte
 *   les branches.
 * @param {Array<[string, *]>} branches Paires `[clé, entrée]`. La clé
 *   identifie la branche dans le résultat.
 * @param {object} [opts]
 * @param {Record<string,string[]>} [opts.capabilities] Critère de
 *   découverte par clé de branche.
 * @param {Record<string,string>} [opts.agents] Nom d'agent exact par clé
 *   de branche — prime sur `capabilities` pour cette branche.
 * @returns {Promise<Record<string,*>>} Une branche en échec y figure
 *   comme l'erreur levée, jamais levée elle-même : les branches saines
 *   restent exploitables même si une autre a échoué.
 */
export async function fanOut(orchestrator, branches, { capabilities = {}, agents = {} } = {}) {
  const runBranch = async (key, payload) => {
    let target = agents[key];
    if (!target) {
      const found = await orchestrator.discover({ capabilities: capabilities[key] || [] });
      if (!found.count) throw new PipelineError(`Branche '${key}' : aucun agent disponible.`);
      target = found.agents[0].name;
    }
    return orchestrator.submitTask(key, target, payload);
  };

  const keys = branches.map(([k]) => k);
  const settled = await Promise.allSettled(branches.map(([k, payload]) => runBranch(k, payload)));

  const results = {};
  settled.forEach((outcome, i) => {
    results[keys[i]] = outcome.status === 'fulfilled' ? outcome.value : outcome.reason;
  });
  return results;
}
