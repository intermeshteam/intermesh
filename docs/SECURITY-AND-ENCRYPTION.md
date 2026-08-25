# Spécification Cryptographique et Modèle de Sécurité Nexus

## 1. Chiffrement Hybride E2E
- Asymétrique : RSA-2048 avec padding OAEP (SHA-256)
- Symétrique : AES-256-GCM (IV 12 octets, Tag 16 octets)

Le Hub ne peut pas lire le contenu des flux.

## 2. Intégrité des Identités

Chaque agent calcule une empreinte SHA-256 de ses privilèges. Toute altération locale entraîne le rejet immédiat.

## 3. Clé de signature JWT du Hub

Le Hub signe les tokens d'agents en HS256 avec une clé unique. Cette clé doit
rester **stable d'un démarrage à l'autre** : si elle change, tous les tokens
déjà distribués deviennent invalides et l'intégralité de la flotte est éjectée.

### Ordre de résolution

Le Hub résout sa clé selon la première source disponible :

| Priorité | Source | Usage visé |
|---|---|---|
| 1 | Variable d'environnement `NEXUS_HUB_SECRET` | Production, Docker, Kubernetes — la clé ne touche jamais le disque |
| 2 | Fichier `~/.nexus/hub_secret` (créé en `0600` au premier démarrage) | Développement local, déploiement simple |
| 3 | Clé éphémère, uniquement via `--ephemeral-secret` | Tests et CI |

Le chemin du fichier est surchargeable par `--secret-file`, et son répertoire
parent par la variable `NEXUS_HOME`.

### Contraintes

- Une clé fournie via `NEXUS_HUB_SECRET` doit faire **au moins 32 caractères**.
  En deçà, le Hub refuse de démarrer plutôt que de signer avec une clé faible.
- Le fichier de clé est créé via `os.open(..., 0o600)` : il n'existe à aucun
  instant avec des permissions plus larges.
- Si le fichier existe avec des permissions lisibles par le groupe ou les
  autres, le Hub démarre mais émet un avertissement explicite.
- Si deux Hubs démarrent simultanément sur le même fichier, ils convergent sur
  la même clé : sans cela, chacun signerait différemment et rejetterait les
  agents de l'autre.

### Génération d'une clé

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Déploiement

```bash
# Production — clé injectée, rien sur disque
export NEXUS_HUB_SECRET="<64 caractères hexadécimaux>"
python3 server/hub.py --port 8765 --org acme

# Développement — clé persistée automatiquement dans ~/.nexus/hub_secret
python3 server/hub.py --port 8765 --org acme

# Tests — clé jetable, tokens perdus à l'arrêt
python3 server/hub.py --port 8765 --org acme --ephemeral-secret
```

Le Hub affiche au démarrage si sa clé est `PERSISTANTE` ou `ÉPHÉMÈRE`, ainsi
que la source retenue.

### Rotation

Changer la clé invalide immédiatement tous les tokens en circulation ; les
agents doivent se reconnecter. Il n'existe pas encore de rotation sans coupure
(deux clés acceptées pendant une fenêtre de transition) — c'est une évolution
prévue.

## 4. Persistance de l'état

Le Hub conserve son état dans une base SQLite (`~/.nexus/hub_state.db` par
défaut, créée en `0600`) :

| Donnée | Persistée | Raison |
|---|---|---|
| Registre d'identités | ✅ | `who_is` et `discover` restent utilisables pour un agent hors ligne |
| Tâches et leur statut | ✅ | Une tâche en cours au moment de l'arrêt n'est pas perdue |
| Journal d'audit | ✅ | Un journal qui disparaît ne prouve rien à un auditeur |
| Connexions actives | ❌ | Être « en ligne » est une propriété du processus, pas un fait durable |
| Peering fédéré | ❌ | Les liens inter-Hubs sont rétablis à la reconnexion |

Chemin surchargeable par `--state-file`, répertoire parent par `NEXUS_HOME`.
`--ephemeral-state` bascule sur une base en mémoire pour les tests.

### Le journal d'audit protège désormais son propre fichier

Le chaînage Merkle ne garantissait jusqu'ici l'intégrité que pendant la vie du
processus. Le journal étant persisté, la vérification s'applique maintenant au
fichier sur disque : le Hub recharge la chaîne au démarrage et la vérifie.

Si quelqu'un modifie une entrée directement dans la base, la chaîne est rompue
et le Hub l'annonce explicitement au démarrage :

```
🚨 ALERTE : la chaîne d'audit persistée est rompue.
   Le journal a été modifié en dehors du Hub.
```

### Tâches interrompues

Les tâches `pending` ou `running` au moment de l'arrêt sont rechargées et
signalées au démarrage, mais **ne sont pas réassignées automatiquement**.
Leurs exécutants doivent se reconnecter. Une reprise automatique reste à faire.

## 5. Limites connues

- **Un seul Hub par base** : SQLite convient à un Hub unique. Plusieurs Hubs
  partageant un état demanderont PostgreSQL.
- **Pas de reprise des tâches interrompues** (voir ci-dessus).
- **Clés d'API entreprise en dur** dans `server/hub.py` — acceptable pour une
  démonstration, à remplacer par un magasin de secrets avant tout usage réel.
- **Pas de TLS** sur le transport WebSocket par défaut : le chiffrement E2E
  protège le contenu, mais les métadonnées (qui parle à qui) transitent en
  clair. Placez le Hub derrière une terminaison TLS en production.
- **Pas de rotation de clé sans coupure** : changer `NEXUS_HUB_SECRET` éjecte
  toute la flotte.
