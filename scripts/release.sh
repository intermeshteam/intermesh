#!/bin/bash
set -e

echo "========================================================"
echo "   INTERMESH PROTOCOL — BUILD & RELEASE AUTOMATION         "
echo "========================================================"

# 1. Validation de la suite de tests
echo -e "\n\033[33m1. Exécution des tests de conformité...\033[0m"
pytest -v

# 2. Construction du paquet Python (PyPI Wheel & Source)
echo -e "\n\033[33m2. Construction du package Python (Wheel)...\033[0m"
cd sdk-python
rm -rf dist/ build/ *.egg-info
python3 -m pip install --upgrade build
python3 -m build
echo -e "\033[32m✓ Package Python prêt dans sdk-python/dist/\033[0m"
cd ..

# 3. Validation du package Node.js (NPM)
echo -e "\n\033[33m3. Préparation du package Node.js (NPM)...\033[0m"
cd sdk-js
npm pack
echo -e "\033[32m✓ Package Node.js généré avec succès !\033[0m"
cd ..

echo -e "\n\033[32m🎉 TOUS LES ARTEFACTS SONT COMPILÉS ET PRÊTS POUR PUBLICATION !\033[0m"
echo "  • Pour publier sur PyPI : python3 -m twine upload sdk-python/dist/*"
echo "  • Pour publier sur NPM  : cd sdk-js && npm publish --access public"
