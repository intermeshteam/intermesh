# Démonstration — InterMesh Action Assurance

```bash
python3 examples/assurance/demo.py
```

Trois actions, trois décisions, puis la vérification et une tentative de
falsification.

**L'agent de la démonstration ne contient aucune ligne d'InterMesh.**
C'est un script `requests` ordinaire ; seule la variable `HTTP_PROXY`
change. C'est l'objet même de la démonstration : l'assurance s'ajoute sans
toucher au code, donc sans dépendre du langage.

| Action | Risque | Décision | Preuve |
|---|---|---|---|
| `POST /delete/database` | R5 | bloquée | oui |
| `POST /transfer` | R4 | approbation requise | oui |
| `POST /items` | R2 | exécutée pour de vrai | oui |
| `GET /items` | R0 | exécutée | non — sous le seuil |

La politique est dans [`policy.yaml`](policy.yaml). L'ordre des règles
compte : la première qui correspond gagne, donc les interdits se placent
en tête.

## Vérifier soi-même

```bash
intermesh verify examples/assurance/evidence.jsonl
```

Hors ligne, sans compte, sans nous. Modifiez n'importe quel champ du
fichier et relancez : l'intégrité tombe.
