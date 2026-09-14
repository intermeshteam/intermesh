# Modèle de sécurité

Ce document dit ce qu'InterMesh Assurance protège, et surtout ce qu'il ne
protège pas. Un outil de sécurité qui survend est pire que pas d'outil du
tout : il déplace la confiance sans déplacer le risque.

Chaque ligne du tableau de contournement correspond à un test exécutable
dans `tests/test_assurance_paths.py`. Rien ici n'est une intention.

---

## 1. Ce que le produit garantit

| Garantie | Mécanisme | Test |
|---|---|---|
| Une action bloquée **ne part pas** | Décision avant relais | `test_chemin_block_n_atteint_jamais_l_api` |
| Une preuve modifiée **se voit** | SHA-256 sur corps canonique | `test_toute_modification_apres_coup_est_detectee` |
| Une preuve désigne **son émetteur** | Signature Ed25519 | `test_une_signature_etrangere_est_refusee` |
| Une preuve retirée d'une suite **se voit** | Chaînage `prev_hash` | `test_la_chaine_detecte_une_preuve_retiree` |
| Une approbation ne sert **qu'une fois** | Consommation du jeton | `test_une_approbation_ne_sert_qu_une_fois` |
| Une approbation ne vaut que **pour son action** | Méthode + cible enregistrées | `test_une_approbation_ne_sert_pas_pour_une_autre_action` |
| Les secrets **ne sont pas stockés** | Empreinte du corps uniquement | `test_le_corps_de_la_requete_n_est_jamais_stocke` |
| La vérification **n'a besoin de personne** | `intermesh verify` hors ligne | `test_verify_en_ligne_de_commande_tranche_dans_les_deux_sens` |

**Formulation admissible :** *cryptographically verifiable.*
**Formulation inadmissible aujourd'hui :** *legally valid.* Aucune
juridiction n'a examiné ce format ; aucun régulateur ne l'a reconnu. Le
dire serait un mensonge commercial.

---

## 2. Frontières de confiance

```text
┌──────────────────────────────────────────────┐
│  ZONE NON FIABLE — l'agent                   │
│  Peut mentir sur ce qu'il fait.              │
│  Peut tenter de contourner le proxy.         │
└───────────────────┬──────────────────────────┘
                    │ HTTP
┌───────────────────▼──────────────────────────┐
│  FRONTIÈRE — le proxy                        │
│  Observe ce qui SORT, pas ce qui est déclaré │
│  Détient la clé de signature                 │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│  ZONE VÉRIFIABLE — la preuve                 │
│  Vérifiable par un tiers, hors ligne         │
└──────────────────────────────────────────────┘
```

**Le proxy est dans la zone de confiance ; l'agent n'y est pas.** C'est
toute la thèse : un agent qui ment dans son propre code ne change rien à
ce que le proxy a vu passer sur le réseau.

**Corollaire inconfortable :** qui contrôle le proxy contrôle la preuve.
La clé de signature vit sur la même machine. Un attaquant ayant ce niveau
d'accès forge des preuves à volonté. Séparer la signature — HSM, service
distinct — n'est pas fait.

---

## 3. Contournements — l'état réel

### Non couvert : contournable sans effort

| Contournement | Pourquoi | Test |
|---|---|---|
| Appel direct sans proxy | La variable d'environnement est une convention, pas une contrainte | `test_contournement_appel_direct_sans_proxy` |
| Socket TCP brute | Le proxy ne voit que ce qu'on lui donne | `test_contournement_socket_brute` |
| Processus enfant sans l'environnement | Idem | non testé |
| Outil externe (`curl` lancé par l'agent) | Idem, sauf si l'environnement est hérité | non testé |
| Autre interface réseau | Le proxy n'est pas dans le chemin | non testé |

**La réponse n'est pas dans le produit.** Fermer ces portes suppose une
contrainte réseau : refuser tout trafic sortant sauf par le proxy —
règle de pare-feu, espace de noms réseau, conteneur sans route par
défaut. InterMesh ne peut pas s'imposer lui-même comme seul chemin ; il
peut seulement prouver ce qui passe par lui.

> **La phrase à retenir, et à ne pas dépasser :**
> *L'agent peut mentir dans son propre code ; InterMesh observe l'action
> réseau réellement interceptée.*
> **« Interceptée » fait tout le travail.** Ce qui n'est pas intercepté
> n'existe pas pour InterMesh — et **l'absence de preuve n'est pas une
> preuve d'absence.**

### Couvert

| Tentative | Résultat | Test |
|---|---|---|
| Déclarer GET et émettre DELETE | Le proxy voit DELETE | `test_couvert_le_proxy_voit_la_methode_reelle...` |
| Changer d'hôte ou de port | La politique porte sur l'action | `test_couvert_changer_d_hote_ou_de_port...` |
| Méthode hors politique | Refusée par défaut | `test_couvert_une_methode_hors_politique...` |
| Rejouer un jeton d'approbation | Consommé une seule fois | `test_une_approbation_ne_sert_qu_une_fois` |
| Détourner une approbation | Liée à méthode + cible | `test_une_approbation_ne_sert_pas_pour_une_autre_action` |
| Inventer un jeton | Refusé, et tracé | `test_un_jeton_d_approbation_invente_est_refuse` |
| Corps de 2 Mo | Traité, empreinte calculée | `test_couvert_un_corps_enorme...` |
| 20 requêtes simultanées | Chaînage intact | `test_couvert_le_journal_reste_chaine...` |

### Partiellement couvert

**HTTPS.** Le client envoie `CONNECT hôte:443` puis chiffre. Le proxy
voit l'hôte et le port, **jamais le chemin ni le corps**. Une règle
`path_contains` ne s'applique pas. La preuve porte `tls_opaque: true`
plutôt que de laisser croire à une classification sur pièces.

Lever cette limite suppose d'interrompre le TLS avec une autorité de
certification installée sur le client. C'est courant en entreprise, mais
cela **change le modèle de menace** : le proxy voit alors tout en clair,
y compris les jetons d'API. Hors périmètre du MVP, et ce n'est pas un
oubli.

---

## 4. Surface d'attaque

| Surface | État |
|---|---|
| Port du proxy | `127.0.0.1` par défaut. Exposé = n'importe qui fait signer des preuves |
| Fichier de preuves | `0600`. Effaçable par qui a l'accès disque — le chaînage rend la troncature visible, pas impossible |
| Fichier d'approbations | `0600`. **Qui l'écrit accorde des approbations.** Aucune authentification |
| Clé de signature | Dérivée du secret du Hub, sur disque. Pas de HSM |
| Politique | Lue au démarrage. Un changement en cours d'exécution n'est pas rechargé |
| `intermesh approve` | **Aucune authentification.** Qui peut lancer la commande peut approuver |

Ces trois derniers points sont les plus graves pour un usage réel. Ils
sont assumés dans un MVP dont l'objet est de prouver la primitive, pas de
tenir en production.

---

## 5. Modes de défaillance

| Situation | Comportement | Est-ce le bon ? |
|---|---|---|
| Cible injoignable | 502, preuve `failed` | Oui |
| Disque plein | L'écriture échoue, l'action **a déjà eu lieu** | **Non.** Il faudrait refuser l'action si la preuve ne peut pas s'écrire |
| Proxy tué en pleine écriture | Dernière ligne tronquée, chaînage le signale | Acceptable |
| Politique illisible | Refus de démarrer | Oui |
| Horloge décalée | Approbations expirées à tort | Acceptable |

La deuxième ligne est le défaut le plus sérieux connu : **une action peut
s'exécuter sans que sa preuve soit écrite.** Pour un produit dont la
thèse est « toute action critique laisse une preuve », c'est une
contradiction à corriger avant tout usage sérieux.

---

## 6. Ce qui reste à construire

Aucun de ces points n'est implémenté ; ils sont listés pour que leur
absence soit explicite plutôt que découverte.

- Authentification de `intermesh approve`
- Refus d'exécuter si la preuve ne peut pas être écrite
- Séparation de la clé de signature (HSM, service dédié)
- Rechargement de politique à chaud
- Ancrage externe du journal — sans quoi qui contrôle le fichier peut
  le tronquer et re-signer l'ensemble
- Interception hors HTTP : gRPC, WebSocket, appels système, systèmes
  physiques
