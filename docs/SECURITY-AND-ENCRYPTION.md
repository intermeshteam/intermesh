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

## 4. Limites connues

- **Aucune persistance de l'état** : agents, tâches et journal d'audit sont
  conservés en mémoire et disparaissent à l'arrêt du Hub. Le journal d'audit
  Merkle garantit l'intégrité pendant la vie du processus, pas au-delà.
- **Clés d'API entreprise en dur** dans `server/hub.py` — acceptable pour une
  démonstration, à remplacer par un magasin de secrets avant tout usage réel.
- **Pas de TLS** sur le transport WebSocket par défaut : le chiffrement E2E
  protège le contenu, mais les métadonnées (qui parle à qui) transitent en
  clair. Placez le Hub derrière un terminaison TLS en production.
