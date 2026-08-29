#!/usr/bin/env python3
"""
Point d'entrée historique du Hub, conservé pour compatibilité.

L'implémentation vit désormais dans `intermesh.hub`, à l'intérieur du
paquet : hors du paquet, `pip install intermesh` livrait le SDK et le CLI
mais pas le serveur, et le Quick start du README ne pouvait pas fonctionner.

Ce fichier reste valable — `python3 server/hub.py --port 8765` fonctionne
comme avant, avec les mêmes options.
"""

import asyncio

from intermesh.hub import main

if __name__ == "__main__":
    asyncio.run(main())
