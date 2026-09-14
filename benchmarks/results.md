# Latence du proxy d'assurance — résultats

```bash
python3 benchmarks/proxy_latency.py --requests 3000
```

Boucle locale, sans TLS, Python 3.14.4, 8 cœurs. 3 000 requêtes mesurées
après 300 de préchauffe, connexion maintenue, Nagle désactivé côté client.

## Latence

### Corps de 100 octets

| | moy | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| **A. direct** | 0,25 | 0,22 | 0,35 | 0,39 | 0,52 |
| **B. via InterMesh** | 1,13 | 1,11 | 1,40 | 1,55 | 1,76 |
| **surcoût** | **0,88** | **0,89** | 1,05 | 1,16 | — |

### Corps de 10 ko

| | moy | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| **A. direct** | 0,29 | 0,30 | 0,38 | 0,42 | 0,51 |
| **B. via InterMesh** | 1,21 | 1,18 | 1,51 | 1,79 | 2,32 |
| **surcoût** | **0,92** | **0,88** | 1,13 | 1,37 | — |

**Le surcoût ne dépend pas de la taille du corps** — seule son empreinte
est calculée, jamais son contenu stocké.

| Objectif MVP | Mesuré | |
|---|---|---|
| < 10 ms | **0,89 ms** p50, **1,55 ms** p99 | ✅ tenu avec un facteur 10 de marge |

Le surcoût relatif (+405 %) est spectaculaire et sans intérêt : il
compare à un aller-retour en boucle locale de 0,22 ms. Sur un appel réel
vers un service distant à 50 ms, 0,89 ms représente **1,8 %**.

## Débit

| | direct | via InterMesh | ratio |
|---|---|---|---|
| 8 fils, corps 100 o | 3 317 req/s | 676 req/s | 20 % |
| 8 fils, corps 10 ko | 3 027 req/s | 751 req/s | 25 % |

**C'est la vraie limite du MVP, et elle est assumée.** Cause identifiée :
`_send_upstream` ouvre et ferme une connexion TCP par requête vers la
cible — aucun pool. Le coût interne du proxy est de 1,2 ms (politique
0,002 ms, signature 0,29 ms, relais 0,93 ms), donc le relais domine.

Un pool de connexions amont quadruplerait probablement ce chiffre. Ce
n'est **pas** fait, pour deux raisons : 676 req/s dépasse largement ce
qu'un agent LLM produit — quelques appels par seconde au plus —, et
optimiser avant d'avoir un utilisateur serait exactement l'optimisation
prématurée que le cahier des charges interdit. La mesure est là pour que
la décision soit reprise quand un cas réel l'exigera.

## Ressources

| | |
|---|---|
| CPU | 0,99 ms par requête |
| Mémoire | 43,8 Mo RSS |

Mesure banc + proxy dans le même processus : elle **majore** le coût réel
du proxy seul.

## Ce que ce banc ne mesure pas

- **TLS.** En `CONNECT`, le proxy ne fait que relayer des octets ; le
  coût attendu est plus faible, faute de classification et de preuve.
- **Réseau réel.** Tout est en boucle locale. La latence d'un vrai
  service noierait ce surcoût.
- **Écriture des preuves sur disque lent.** Le banc écrit en mémoire.
  Sur disque, le verrou d'écriture devient le facteur limitant.
- **Montée en charge au-delà de 8 fils.**

## Correction d'une mesure antérieure

Une première campagne annonçait **82 ms**, puis **42 ms** de surcoût, et
trois correctifs ont été tentés sur le proxy. C'était faux : le client
`requests` en mode proxy découpe sa requête en deux segments TCP et paie
un acquittement différé. Avec `curl`, le même proxy montrait 1,15 ms.

La mesure des composants internes donnait 1,2 ms **avant** ces trois
tentatives — la bonne réponse était déjà là. La leçon tient en une
phrase : **mesurer les composants avant de corriger le tout.**

Conséquence pratique pour les utilisateurs : un client Python `requests`
verra environ 40 ms de surcoût tant qu'il ne désactive pas Nagle.
`curl`, Node et Go ne sont pas concernés.
