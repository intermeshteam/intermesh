# Action Evidence Record — spécification v0.1

**Statut :** brouillon. Rien ici n'est stable tant qu'une implémentation
indépendante n'a pas vérifié une preuve produite par celle-ci.

Un journal dit ce qu'un système se souvient d'avoir fait. Une preuve
permet à quelqu'un qui ne fait pas confiance à ce système de le vérifier
lui-même. Cette spécification décrit le second.

---

## 1. Ce que la preuve garantit

| Propriété | Mécanisme | Ce qui est détecté |
|---|---|---|
| Intégrité | SHA-256 sur le corps canonique | Un champ modifié après coup |
| Non-répudiation | Signature Ed25519 | Une preuve qui ne vient pas de la clé annoncée |
| Chaînage | `prev_hash` | Une preuve retirée ou insérée dans une suite |

## 2. Ce que la preuve ne garantit pas

À dire aussi clairement que le reste, sans quoi la spécification ment par
omission :

- **L'absence de preuve n'est pas une preuve d'absence.** Un agent qui
  contourne le point d'interception n'apparaît nulle part.
- **La clé n'est pas authentifiée par la preuve.** Une preuve intacte et
  signée l'est *par la clé qu'elle transporte*. Que cette clé appartienne
  bien à l'émetteur annoncé s'établit hors bande — annuaire, certificat,
  échange préalable.
- **La preuve n'atteste pas du résultat métier.** Elle atteste qu'une
  requête est partie, avec quelle décision et quelle réponse. Ce que le
  système distant en a fait lui échappe.
- **En TLS, la preuve ne porte que sur l'hôte.** Voir §6.

---

## 3. Structure

```json
{
  "version": "0.1",
  "action_id": "uuid4",
  "timestamp": 1789223128261,
  "agent_id": "devops-bot",
  "organization_id": "acme",
  "action": {
    "method": "POST",
    "target": "http://api.interne/v1/delete/database",
    "type": "http_request",
    "payload_hash": "sha256 hex du corps, jamais le corps"
  },
  "risk":          { "level": "R5", "label": "R5", "value": 5 },
  "authorization": { "policy": "devops-v1@a1b2c3d4", "rule": "destructive_action",
                     "decision": "block" },
  "execution":     { "status": "blocked", "reason": "irréversible" },
  "prev_hash":     "empreinte de la preuve précédente, ou 64 zéros",
  "evidence": {
    "hash": "sha256 hex du corps canonique",
    "algorithm": "Ed25519",
    "signature": "base64url sans remplissage",
    "issuer": "acme",
    "public_key": "-----BEGIN PUBLIC KEY-----…",
    "key_fingerprint": "16 hex"
  }
}
```

Les champs à `null` sont **omis**. Un `null` signé n'apporte rien et
alourdit la chaîne.

### Champs obligatoires

`version`, `action_id`, `timestamp`, `agent_id`, `organization_id`,
`action`, `risk`, `authorization`, `execution`, `prev_hash`, `evidence`.

### `execution.status`

| Valeur | Sens |
|---|---|
| `executed` | Partie sur le réseau, réponse reçue |
| `blocked` | Refusée par la politique, jamais émise |
| `pending_approval` | Retenue en attente d'une validation humaine |
| `tunnelled` | Tunnel TLS ouvert — contenu non observable |
| `failed` | Autorisée, mais la cible était injoignable |

---

## 4. Sérialisation canonique

Deux parties ne vérifient la même signature que si elles obtiennent les
mêmes octets. Trois règles, toutes nécessaires :

1. **clés triées** par ordre lexicographique ;
2. **séparateurs `,` et `:`**, sans espace ;
3. **aucun flottant**.

La troisième n'est pas une préférence de style. Python sérialise
`1788459123.0` en `1788459123.0`, JavaScript en `1788459123` : octets
différents, signature différente. Le désaccord ne survient que lorsque
l'horodatage tombe sur une seconde ronde — une fois sur mille environ —
et passerait donc toutes les suites de tests avant de casser en
production. **Tous les horodatages sont des entiers en millisecondes.**

Une implémentation conforme **doit** refuser de signer un objet
contenant un flottant.

## 5. Vérification

```
1. tous les champs obligatoires sont présents      → schema
2. sha256(canonical(corps)) == evidence.hash       → integrity
3. Ed25519.verify(signature, evidence.hash)        → signature
4. pour une suite : prev_hash[n] == hash[n-1]      → chaînage
```

Les quatre résultats sont rapportés **séparément**. « INVALIDE » sans
préciser laquelle des quatre a échoué n'aide personne à diagnostiquer.

La vérification **ne doit ouvrir aucune connexion réseau**. Une preuve
qu'il faut demander à quelqu'un de valider ne vaut rien.

## 6. Limite du TLS

En `https://`, un proxy reçoit `CONNECT hôte:443` puis un flux chiffré.
Le chemin, les en-têtes et le corps lui sont inaccessibles. La preuve
porte alors `execution.tls_opaque: true` et ne doit pas laisser croire à
une classification sur le chemin.

Lever cette limite suppose d'interrompre le TLS avec une autorité de
certification installée sur le client. C'est faisable et courant en
entreprise, mais cela change le modèle de menace : le proxy voit alors
tout le trafic en clair, y compris les secrets. Hors périmètre de v0.

## 7. Versionnement

`version` suit la spécification, pas l'implémentation. Un vérificateur
qui rencontre une version inconnue **doit** refuser plutôt que de tenter
une lecture partielle : une preuve à moitié comprise est pire qu'une
preuve rejetée.

## 8. Conformité

Une implémentation est conforme si elle produit une preuve que
`intermesh verify` valide, **et** si elle valide une preuve produite par
lui. La réciprocité est le seul test qui compte pour un standard.
