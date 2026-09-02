# Connecter et orchestrer des agents

Ce guide couvre les deux mécanismes qui servent à faire travailler ensemble des
agents écrits dans des frameworks différents : les **adaptateurs**, qui exposent
un agent existant sur le réseau InterMesh sans en changer une ligne, et les
**helpers d'orchestration**, qui composent plusieurs agents déjà connectés en
workflows. Les deux existent en Python et en JavaScript/TypeScript, avec la même
sémantique.

---

## Adaptateurs : brancher un agent déjà écrit

Un développeur ne réécrit pas son agent LangChain, CrewAI, AutoGen ou LlamaIndex
pour essayer un protocole. Aucun adaptateur n'importe le framework qu'il ponte :
installer le SDK n'entraîne jamais LangChain et ses dépendances transitives.

Les deux SDK ne fonctionnent pas de la même manière, et c'est important à
connaître avant de lire la suite :

- **JavaScript** détecte la convention d'appel de l'objet qu'on lui confie —
  méthode connue (`invoke`, `run`, `kickoff`, `query`…) ou fonction appelable.
- **Python** ne fait cette détection que pour LangChain (`from_langchain`).
  Pour tout le reste, vous écrivez la fonction d'adaptation vous-même et la
  passez à `from_callable` — quelques lignes, mais explicites.

### Python

Trois fonctions, toutes exportées depuis `intermesh`. Chacune renvoie un
`InterMeshAgent` prêt à `connect()`.

**`from_langchain`** — pour un `Runnable`/chaîne LangChain. Il essaie
`ainvoke`, puis `invoke`, puis `run`, puis l'objet lui-même s'il est appelable,
et renvoie `{"output": <résultat>, "adapter": "langchain_intermesh_v1"}` :

```python
from intermesh import from_langchain

agent = from_langchain(ma_chaine, name="analyste", capabilities=["market_analysis"])
agent.run()          # se connecte et reste en service
```

**`from_callable`** — pour tout le reste : un `Crew` CrewAI, un agent AutoGen,
un moteur LlamaIndex, ou une simple fonction. La fonction reçoit le dict de
tâche tel quel ; c'est à elle d'adapter la convention du framework :

```python
import asyncio
from intermesh import from_callable

async def run_crew(data):
    result = await asyncio.to_thread(lambda: mon_crew.kickoff(inputs=data))
    return {"output": getattr(result, "raw", str(result))}

agent = from_callable(run_crew, name="recherche", capabilities=["research"])
```

**`@intermesh_service`** — le même mécanisme sous forme de décorateur. Attention :
il **remplace** la fonction par l'agent, `mon_service` n'est plus appelable
comme une fonction ordinaire ensuite :

```python
from intermesh import intermesh_service

@intermesh_service(name="resumeur", capabilities=["summarize"])
def mon_service(data):
    return {"summary": mon_modele(data["text"])}

mon_service.run()    # se connecte et reste en service
```

`InterMeshAgent.from_callable(...)` et `InterMeshAgent.from_langchain(...)` existent
aussi comme méthodes de classe — même comportement, autre point d'entrée.

⚠️ **Appels bloquants.** `from_callable` exécute votre fonction telle quelle :
si elle est synchrone, elle s'exécute *dans* la boucle asyncio et gèle l'agent
pendant toute sa durée — plus aucune tâche reçue, plus aucun message routé.
Un appel LLM bloque plusieurs secondes. Enveloppez-le dans `asyncio.to_thread`,
comme ci-dessus. Même remarque pour `from_langchain` si votre chaîne n'expose
que `invoke` sans `ainvoke`.

### JavaScript / TypeScript

Frameworks couverts : **LangChain.js**, **LlamaIndex.TS**. CrewAI et AutoGen
n'ont pas de port JS établi — pour ces deux-là, restez côté Python.

```javascript
import { InterMeshLangChainAdapter } from 'intermesh/adapters/langchain';

const agent = new InterMeshLangChainAdapter(monRunnable, {
  name: 'analyste',
  capabilities: ['market_analysis'],
});
await agent.connect();
```

```javascript
import { InterMeshLlamaIndexAdapter } from 'intermesh/adapters/llamaindex';

const agent = new InterMeshLlamaIndexAdapter(index.asQueryEngine(), {
  name: 'base_documentaire',
  capabilities: ['document_search', 'rag'],
});
```

Un framework sans pont dédié fonctionne via `adapt()`, qui détecte la méthode
d'invocation de l'objet (côté JS uniquement — l'équivalent Python est
`from_callable`, avec une fonction que vous écrivez vous-même) :

```javascript
import { adapt } from 'intermesh/adapters';

const agent = adapt(monAgentExistant, { name: 'x', capabilities: ['c'] });
```

Différence à connaître : l'API JS de LlamaIndex.TS attend un objet
(`query({ query: "..." })`), pas une chaîne brute comme la version Python
(`query(str)`). `InterMeshLlamaIndexAdapter` reconditionne automatiquement l'entrée
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
`examples/agent_a.py`). `InterMeshPipeline` et `fan_out`/`fanOut` capturent ce
patron pour ne plus le réécrire à chaque fois.

### Enchaîner des étapes : `InterMeshPipeline`

Chaque étape peut nommer un agent explicitement, ou le rechercher par capacité —
la recherche a lieu à l'exécution, pas à la déclaration, donc un agent qui
rejoint le réseau entre-temps compte.

**Python**

```python
from intermesh import InterMeshPipeline

pipeline = (
    InterMeshPipeline(orchestrateur)
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
import { InterMeshPipeline } from 'intermesh';

const pipeline = new InterMeshPipeline(orchestrateur)
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
from intermesh import fan_out

results = await fan_out(
    orchestrateur,
    [("fr", {"region": "FR"}), ("de", {"region": "DE"})],
    capabilities={"fr": ["market_analysis"], "de": ["market_analysis"]},
)
results["fr"]  # sortie de la branche, ou l'exception levée
```

**JavaScript**

```javascript
import { fanOut } from 'intermesh';

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
`ConversableAgent` AutoGen) plutôt que des agents InterMesh faits main — voir
[`examples/frameworks/README.md`](../examples/frameworks/README.md) pour les
dépendances à installer et l'ordre de lancement.

## Voir aussi

- [RFC-001 — spécification du protocole cœur](RFC-001-CORE-PROTOCOL.md)
- [Modèle de sécurité et de chiffrement](SECURITY-AND-ENCRYPTION.md)
- [Référence des méthodes SDK](API-REFERENCE.md)
