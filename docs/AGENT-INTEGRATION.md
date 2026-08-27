# Connecter et orchestrer des agents

Ce guide couvre les deux mécanismes qui servent à faire travailler ensemble des
agents écrits dans des frameworks différents : les **adaptateurs**, qui exposent
un agent existant sur le réseau Nexus sans en changer une ligne, et les
**helpers d'orchestration**, qui composent plusieurs agents déjà connectés en
workflows. Les deux existent en Python et en JavaScript/TypeScript, avec la même
sémantique.

---

## Adaptateurs : brancher un agent déjà écrit

Un développeur ne réécrit pas son agent LangChain, CrewAI, AutoGen ou LlamaIndex
pour essayer un protocole. Les adaptateurs détectent la convention d'appel de
l'objet qu'on leur confie — méthode connue (`invoke`, `run`, `kickoff`,
`execute_task`, `query`, `chat`…) ou simple fonction appelable — plutôt que
d'imposer une interface. Aucun d'eux n'importe le framework qu'il pontage :
installer le SDK n'entraîne jamais LangChain et ses dépendances transitives.

### Python

Frameworks couverts : **LangChain**, **CrewAI**, **AutoGen**, **LlamaIndex**.

```python
from nexus_sdk.adapters.langchain import NexusLangChainAdapter

agent = NexusLangChainAdapter(
    mon_agent_executor,
    name="analyste",
    capabilities=["market_analysis"],
)
await agent.connect()
```

Un framework inconnu fonctionne quand même avec `adapt()`, tant qu'il expose une
méthode d'invocation reconnaissable :

```python
from nexus_sdk.adapters import adapt

agent = adapt(mon_agent_existant, name="x", capabilities=["c"])
```

Options utiles à toute classe d'adaptateur (`**kwargs` transmis à `NexusAgent`) :

| Paramètre | Rôle |
|---|---|
| `input_key` | Extrait une seule valeur du dict de tâche avant l'appel (ex. `"query"` pour LlamaIndex, `"message"` pour AutoGen) |
| `input_adapter` | Transformation complète de l'entrée ; prime sur `input_key` |
| `output_adapter` | Transformation de la sortie avant renvoi |
| `invoke_method` | Force la méthode d'invocation si la détection se trompe |
| `run_in_thread` | `True` par défaut — les appels synchrones partent dans un thread pour ne pas geler la boucle asyncio de l'agent |

Les méthodes synchrones (`invoke`, `kickoff`, `run`…) sont exécutées hors de la
boucle événementielle : un appel LLM qui bloque plusieurs secondes ne fige pas le
routage des autres tâches de l'agent.

### JavaScript / TypeScript

Frameworks couverts : **LangChain.js**, **LlamaIndex.TS**. CrewAI et AutoGen
n'ont pas de port JS établi — pour ces deux-là, restez côté Python.

```javascript
import { NexusLangChainAdapter } from 'nexus-mesh/adapters/langchain';

const agent = new NexusLangChainAdapter(monRunnable, {
  name: 'analyste',
  capabilities: ['market_analysis'],
});
await agent.connect();
```

```javascript
import { NexusLlamaIndexAdapter } from 'nexus-mesh/adapters/llamaindex';

const agent = new NexusLlamaIndexAdapter(index.asQueryEngine(), {
  name: 'base_documentaire',
  capabilities: ['document_search', 'rag'],
});
```

Un framework sans pont dédié fonctionne via `adapt()`, comme en Python :

```javascript
import { adapt } from 'nexus-mesh/adapters';

const agent = adapt(monAgentExistant, { name: 'x', capabilities: ['c'] });
```

Différence à connaître : l'API JS de LlamaIndex.TS attend un objet
(`query({ query: "..." })`), pas une chaîne brute comme la version Python
(`query(str)`). `NexusLlamaIndexAdapter` reconditionne automatiquement l'entrée
extraite dans la forme attendue ; ce détail ne concerne que qui écrit un pont
personnalisé pour un autre framework JS.

Il n'y a pas d'équivalent JS à `run_in_thread` : les frameworks JS d'agents sont
construits sur des Promises (I/O réseau), donc un appel bloquant de manière
purement synchrone est rare. Un adaptateur qui envelopperait un framework
réellement bloquant gèlerait la boucle événementielle Node — à éviter, faute de
mécanisme de délégation à un thread aussi direct que côté Python.

---

## Orchestration : composer plusieurs agents

`discover()` et `submit_task()`/`submitTask()` suffisent à écrire un workflow à
la main — chercher un agent, soumettre, lire le résultat, recommencer (voir
`examples/agent_a.py`). `NexusPipeline` et `fan_out`/`fanOut` capturent ce
patron pour ne plus le réécrire à chaque fois.

### Enchaîner des étapes : `NexusPipeline`

Chaque étape peut nommer un agent explicitement, ou le rechercher par capacité —
la recherche a lieu à l'exécution, pas à la déclaration, donc un agent qui
rejoint le réseau entre-temps compte.

**Python**

```python
from nexus_sdk import NexusPipeline

pipeline = (
    NexusPipeline(orchestrateur)
    .step("Traduire", capabilities=["translate"])
    .step("Calculer", capabilities=["calculate"],
          input_fn=lambda prev: {"expression": prev["translated_text"]})
)
result = await pipeline.run({"text": "compute forty two doubled"})
result.output    # sortie de la dernière étape
result.history   # [StepResult(title, agent, output), ...]
```

**JavaScript**

```javascript
import { NexusPipeline } from 'nexus-mesh';

const pipeline = new NexusPipeline(orchestrateur)
  .step('Traduire', { capabilities: ['translate'] })
  .step('Calculer', {
    capabilities: ['calculate'],
    inputFn: (prev) => ({ expression: prev.translated_text }),
  });
const result = await pipeline.run({ text: 'compute forty two doubled' });
```

Une étape en échec (timeout, erreur distante, aucun agent trouvé) interrompt le
pipeline immédiatement — les étapes suivantes ne s'exécutent jamais sur une
sortie invalide. L'erreur d'origine (`TimeoutError`, `RuntimeError`,
`PipelineError`) se propage telle quelle.

### Interroger plusieurs agents en parallèle : `fan_out`

Le pendant du pipeline séquentiel : plusieurs branches indépendantes, agrégées
sous une clé de votre choix.

**Python**

```python
from nexus_sdk import fan_out

results = await fan_out(
    orchestrateur,
    [("fr", {"region": "FR"}), ("de", {"region": "DE"})],
    capabilities={"fr": ["market_analysis"], "de": ["market_analysis"]},
)
results["fr"]  # sortie de la branche, ou l'exception levée
```

**JavaScript**

```javascript
import { fanOut } from 'nexus-mesh';

const results = await fanOut(orchestrateur, [
  ['fr', { region: 'FR' }],
  ['de', { region: 'DE' }],
], { capabilities: { fr: ['market_analysis'], de: ['market_analysis'] } });
```

Une branche en échec n'empêche pas de lire les autres : son entrée dans le
résultat est l'exception elle-même, jamais levée directement. Vérifiez le type
(`instanceof Error` / `isinstance(v, Exception)`) avant d'utiliser une valeur de
branche.

---

## Exemples exécutables

`examples/frameworks/` contient des démos qui enveloppent de vrais objets de
framework (un `Runnable` LangChain, un moteur LlamaIndex, un `Crew` CrewAI, un
`ConversableAgent` AutoGen) plutôt que des agents Nexus faits main — voir
[`examples/frameworks/README.md`](../examples/frameworks/README.md) pour les
dépendances à installer et l'ordre de lancement.

## Voir aussi

- [RFC-001 — spécification du protocole cœur](RFC-001-CORE-PROTOCOL.md)
- [Modèle de sécurité et de chiffrement](SECURITY-AND-ENCRYPTION.md)
- [Référence des méthodes SDK](API-REFERENCE.md)
