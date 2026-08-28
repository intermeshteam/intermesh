import { InterMeshAgent } from '../sdk-js/src/index.js';

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  console.log("🚀 Lancement de l'agent Node.js...");

  // Création de l'agent Node.js avec des rôles et capacités
  const agent = new InterMeshAgent({
    name: "node_orchestrator",
    capabilities: ["js_orchestration"],
    roles: ["admin"]
  });

  await agent.connect();

  // Attendre que les agents Python se connectent
  await delay(2000);

  console.log("\n========================================================");
  print("      DÉBUT DU WORKFLOW INTEROPÉRABLE : NODE.JS ➜ PYTHON  ");
  print("========================================================\n");

  // 1. Découvrir l'agent traducteur Python par ses capacités
  console.log("🔍 Node.js recherche un service de traduction...");
  const searchTranslator = await agent.discover({ capabilities: ["translate"] });

  if (searchTranslator.count === 0) {
    console.log("❌ Aucun traducteur trouvé.");
    process.exit(1);
  }

  const translatorName = searchTranslator.agents[0].name;
  console.log(`✓ Traducteur Python identifié : ${translatorName}`);

  // 2. Lui déléguer une tâche de traduction chiffrée E2E
  const translationResult = await agent.submitTask(
    "Traduction Node.js",
    translatorName,
    { text: "Execute double of twenty", target_lang: "fr" }
  );

  const translatedText = translationResult.translated_text;
  console.log(`🎯 [Résultat traducteur Python] : '${translatedText}'\n`);

  // 3. Découvrir l'agent calculateur Python
  console.log("🔍 Node.js recherche un calculateur...");
  const searchCalculator = await agent.discover({ capabilities: ["calculate"] });

  if (searchCalculator.count === 0) {
    console.log("❌ Aucun calculateur trouvé.");
    process.exit(1);
  }

  const calculatorName = searchCalculator.agents[0].name;
  console.log(`✓ Calculateur Python identifié : ${calculatorName}`);

  const expression = translatedText.replace("calculer ", "").trim();
  console.log(`📊 Expression extraite par Node.js : ${expression}`);

  // 4. Lui déléguer la tâche de calcul chiffrée E2E
  const calculationResult = await agent.submitTask(
    "Calcul Node.js",
    calculatorName,
    { expression: expression }
  );

  console.log(`🎯 [Résultat calculateur Python] : ${calculationResult.result}\n`);

  console.log("========================================================");
  console.log("      BILAN DU WORKFLOW MULTI-LANGAGE VALIDÉ            ");
  console.log("========================================================");
  console.log(`  • Émetteur : Node.js (V8 Engine)`);
  console.log(`  • Traducteur : Python (translator_french)`);
  console.log(`  • Calculateur : Python (agent_b)`);
  console.log(`  🔒 Flux complet sécurisé par RSA-OAEP + AES-GCM (E2E)`);
  console.log("========================================================\n");

  process.exit(0);
}

function print(str) { console.log(str); }

main().catch(console.error);
