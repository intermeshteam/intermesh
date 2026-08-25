# Spécification Cryptographique et Modèle de Sécurité Nexus

## 1. Chiffrement Hybride E2E
- Asymétrique : RSA-2048 avec padding OAEP (SHA-256)
- Symétrique : AES-256-GCM (IV 12 octets, Tag 16 octets)
Le Hub ne peut pas lire le contenu des flux.

## 2. Intégrité des Identités
Chaque agent calcule une empreinte SHA-256 de ses privilèges. Toute altération locale entraîne le rejet immédiat.
