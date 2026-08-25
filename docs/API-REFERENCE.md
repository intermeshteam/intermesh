# Référence des Méthodes SDK Nexus (Python & Node.js)

- connect() : Établit la liaison WebSocket et récupère le token JWT.
- send(to, content) : Envoie un message chiffré sans attendre de réponse.
- ask(to, content, timeout) : Envoie une requête chiffrée et attend la réponse déchiffrée.
- discover(capabilities, roles) : Découvre les agents par critères.
- submit_task(title, assignee, input_data) : Délègue une tâche et attend sa résolution.
- who_is(agent_name) : Récupère l'identité et la clé publique d'un tiers.
