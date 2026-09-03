# Formation InterMesh — français

Formation complète en français, du niveau junior au niveau expert :
[`InterMesh-Formation-Junior-a-Expert.pdf`](InterMesh-Formation-Junior-a-Expert.pdf)
(63 pages).

| Partie | Contenu |
|---|---|
| I — Débutant | Concepts, installation, premier agent, CLI, console |
| II — Intermédiaire | SDK Python et JavaScript, adaptateurs de frameworks, orchestration, chiffrement, identité |
| III — Expert | Hub distant, fédération, grappe, capacité, mTLS, réseau fermé, pièges connus |

## Régénérer le PDF

Le PDF est produit depuis `formation-source.html` par
[WeasyPrint](https://weasyprint.org/) :

```bash
pip install weasyprint
python3 -c "import weasyprint; weasyprint.HTML('formation-source.html').write_pdf('InterMesh-Formation-Junior-a-Expert.pdf')"
```

La mise en page (couverture, pages de partie, encadrés, blocs de code) vit
entièrement dans le `<style>` du fichier source — il n'y a pas de feuille de
style externe ni d'image à fournir, ce qui rend la régénération possible hors
ligne.

## Ce que le document promet, et ce qu'il ne promet pas

Le contenu technique — commandes, options, valeurs par défaut, comportements —
a été relevé dans le code source, dans la sortie de `--help` de chaque
sous-commande, et dans les guides de `docs/`. Les chiffres de performance
cités viennent de [BENCHMARKS.md](../BENCHMARKS.md) et
[CAPACITY.md](../CAPACITY.md), et sont signalés comme mesurés plutôt que
présentés comme des généralités.

**La couverture date la version `0.4.5`.** Le document ne se met pas à jour
tout seul : après un changement de protocole ou d'interface en ligne de
commande, il faut relire les chapitres concernés avant de régénérer. En cas
de divergence, le dépôt fait foi — le protocole évolue plus vite qu'un
document imprimé.
