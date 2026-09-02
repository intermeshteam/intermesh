# Spécification Cryptographique et Modèle de Sécurité InterMesh

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
| 1 | Variable d'environnement `INTERMESH_HUB_SECRET` | Production, Docker, Kubernetes — la clé ne touche jamais le disque |
| 2 | Fichier `~/.intermesh/hub_secret` (créé en `0600` au premier démarrage) | Développement local, déploiement simple |
| 3 | Clé éphémère, uniquement via `--ephemeral-secret` | Tests et CI |

Le chemin du fichier est surchargeable par `--secret-file`, et son répertoire
parent par la variable `INTERMESH_HOME`.

### Contraintes

- Une clé fournie via `INTERMESH_HUB_SECRET` doit faire **au moins 32 caractères**.
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
export INTERMESH_HUB_SECRET="<64 caractères hexadécimaux>"
python3 server/hub.py --port 8765 --org acme

# Développement — clé persistée automatiquement dans ~/.intermesh/hub_secret
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

Le Hub conserve son état dans une base SQLite (`~/.intermesh/hub_state.db` par
défaut, créée en `0600`) :

| Donnée | Persistée | Raison |
|---|---|---|
| Registre d'identités | ✅ | `who_is` et `discover` restent utilisables pour un agent hors ligne |
| Tâches et leur statut | ✅ | Une tâche en cours au moment de l'arrêt n'est pas perdue |
| Journal d'audit | ✅ | Un journal qui disparaît ne prouve rien à un auditeur |
| Connexions actives | ❌ | Être « en ligne » est une propriété du processus, pas un fait durable |
| Peering fédéré | ❌ | Les liens inter-Hubs sont rétablis à la reconnexion |

Chemin surchargeable par `--state-file`, répertoire parent par `INTERMESH_HOME`.
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

### Reprise des tâches interrompues

Une tâche `pending` ou `running` est réassignée à son exécutant dès qu'il se
reconnecte — qu'elle ait été interrompue par un arrêt du Hub ou par la
déconnexion de l'agent. L'orchestrateur n'a rien à resoumettre.

Une tâche `running` repasse à `pending` avant réémission : le travail engagé
est perdu, et prétendre le contraire induirait l'orchestrateur en erreur.
**Les exécutants doivent donc être idempotents** — une tâche peut être
exécutée plus d'une fois.

Chaque reprise est consignée au journal sous l'événement `TASK_RESUMED`.

## 5. Comptes de service (clés d'API)

Les clés d'API étaient écrites en clair dans `server/hub.py`, donc publiées
avec le dépôt. Une clé versionnée dans Git est une clé compromise : elle reste
lisible dans l'historique même après suppression.

Elles sont désormais chargées depuis une source externe, et le Hub **n'en
conserve que l'empreinte SHA-256**. Il peut vérifier une clé, jamais la
révéler — même si sa configuration fuit.

### Sources, par ordre de priorité

| Priorité | Source | Usage visé |
|---|---|---|
| 1 | `INTERMESH_API_KEYS` (JSON inline) | Kubernetes, CI |
| 2 | `INTERMESH_API_KEYS_FILE` | Chemin explicite |
| 3 | `~/.intermesh/api_keys.json` | Développement local |
| 4 | aucune | Comptes de service **désactivés** |

Sans configuration, aucune clé ne fonctionne. Il n'existe aucune valeur par
défaut devinable.

### Créer une clé

```bash
intermesh apikey --org acme --roles admin,service_account --permissions "admin:*"
```

La commande affiche la clé une seule fois et l'entrée JSON à ajouter. Le Hub
ne pourra jamais la retrouver.

### Clés de démonstration

`--dev-api-keys` active deux clés publiques, uniquement pour les tests. Le Hub
affiche un avertissement en rouge à chaque démarrage dans ce mode. Ne jamais
l'utiliser en production.

### Comparaison à temps constant

La vérification utilise `secrets.compare_digest`. Comparer des empreintes avec
`==` laisse fuir, par le temps de réponse, le nombre d'octets corrects en
tête — de quoi reconstruire une empreinte valide octet par octet.

Une clé refusée n'est jamais écrite au journal d'audit : celui-ci est lisible
par plus de monde que la clé elle-même.

## 6. Console d'administration

### Le problème que résout le modèle d'autorisation

À l'enregistrement, un agent sans clé d'API **choisit lui-même ses rôles** :

```python
roles = d.get("roles", ["standard"])
```

C'est acceptable pour un maillage où les agents s'échangent des messages.
C'est inacceptable pour une console capable de révoquer des clés et de
déconnecter des agents : n'importe qui pourrait se déclarer `admin`.

### Double condition

Toute commande `admin_request` exige :

1. une identité **authentifiée par clé d'API** — jamais des rôles déclarés
   par le client ;
2. le rôle `admin` ou `org_admin`.

La première condition repose sur le champ `auth_method` du JWT, **signé par
le Hub** : un client ne peut ni le forger ni le modifier. Un token émis avant
l'introduction de ce champ n'ouvre pas l'administration.

### Cloisonnement par organisation (`org_admin`)

`admin` administre tout le Hub, organisations confondues — c'est le rôle de
l'opérateur qui héberge le Hub lui-même, inchangé depuis l'origine.

`org_admin` est plus étroit : il ne voit et n'agit que sur l'organisation
portée par `org_id` dans sa propre clé d'API — un champ signé dans le JWT,
donc lui aussi infalsifiable par le client. C'est le rôle à distribuer
lorsqu'un Hub sert plusieurs entreprises et qu'un portail web laisse chacune
générer ses propres clés : sans ce cloisonnement, la clé admin d'une
entreprise verrait les agents, les tâches et le journal d'audit de toutes
les autres.

Le cloisonnement s'applique à `agents.list`, `agent.disconnect`,
`tasks.list`, `task.cancel`, `task.retry`, `audit.list`, `apikeys.list`,
`apikey.create` (refuse un `org_id` différent du sien) et `apikey.revoke`
(refuse une empreinte hors de son organisation). Les évènements purement
hub-wide (`PEERING_ESTABLISHED`, `PEERING_ACCEPTED`, `GENESIS`) restent
invisibles à `org_admin` même s'ils portaient par accident son `org_id`.

Ce cloisonnement porte sur les **métadonnées** (qui a parlé à qui, statut
d'une tâche, historique d'audit) : le contenu chiffré de bout en bout des
tâches et des messages reste invisible à toute console, `admin` compris —
voir « Chiffrement Hybride E2E » plus haut. Un portail qui doit afficher ce
contenu doit détenir la clé privée de l'agent concerné et déchiffrer
localement, pas lire l'audit du Hub.

### Commandes

| Commande | Effet |
|---|---|
| `hub.info` | État global : agents, tâches, audit, fédération |
| `agents.list` | Inventaire, **y compris les agents hors ligne** |
| `agent.disconnect` | Ferme la connexion d'un agent |
| `tasks.list` | Tâches filtrables par statut et exécutant |
| `task.cancel` | Marque une tâche comme échouée |
| `task.retry` | Repasse en attente et repousse à l'exécutant |
| `audit.list` | Entrées du journal, avec état d'intégrité |
| `audit.verify` | Revérifie la chaîne et localise une rupture |
| `apikeys.list` | Inventaire des clés, **empreintes uniquement** |
| `apikey.create` | Crée une clé ; valeur affichée une seule fois |
| `apikey.revoke` | Révoque une clé par son empreinte |

### Traçabilité

Chaque mutation est journalisée en `ADMIN_ACTION` avec son auteur et ses
paramètres. Chaque tentative refusée est journalisée en `ADMIN_DENIED`.
La valeur d'une clé créée n'est jamais écrite au journal.

### La console web

La console (`sdk-python/intermesh/console/`) est une page statique sans aucune
dépendance externe : elle
fonctionne sur un réseau fermé, devant un Hub sans accès à Internet.

La clé d'API saisie **n'est jamais écrite dans le navigateur** — ni
`localStorage`, ni `sessionStorage`. Elle vit dans une variable, le temps de
l'onglet. Un rechargement la redemande : un jeton d'administration qui
survit dans le stockage du navigateur survit aussi à l'utilisateur qui
s'éloigne de son poste.

Les empreintes affichées sont tronquées à 12 caractères — assez pour
identifier une clé, trop peu pour aider une attaque hors ligne si l'écran
est capturé.

## 7. Limites connues

- **Un seul Hub par base** : SQLite convient à un Hub unique. Plusieurs Hubs
  partageant un état demanderont PostgreSQL.
- **Exécutants supposés idempotents** : une tâche reprise peut être exécutée
  deux fois (voir §4).
- **Pas de TLS** sur le transport WebSocket par défaut : le chiffrement E2E
  protège le contenu, mais les métadonnées (qui parle à qui) transitent en
  clair. Placez le Hub derrière une terminaison TLS en production.
- **Pas de rotation de clé sans coupure** : changer `INTERMESH_HUB_SECRET` éjecte
  toute la flotte.
- **Pas de TLS sur la console** : elle transite par le même WebSocket que les
  agents. Derrière une terminaison TLS (`wss://`) en production, sans quoi la
  clé d'administration circule en clair sur le réseau.
- **Pas d'expiration de session de console** : la page reste connectée tant
  que l'onglet est ouvert.
