# RFC 001 : Spécification du Protocole InterMesh (v1)

- **Statut** : Standard Proposé
- **Version du Protocole** : intermesh/v1
- **Auteurs** : InterMesh Architecture Working Group
- **Date** : 2026

## 1. Résumé (Abstract)
Le protocole InterMesh (intermesh/v1) est un standard de communication et de coordination sécurisé, asynchrone et chiffré de bout en bout (E2E), conçu pour l'interopérabilité universelle des agents IA.

## 2. Enveloppe du Message
Chaque unité d'information transmise sur le réseau DOIT respecter la structure standard :
- id: UUID-v4 unique
- version: intermesh/v1
- type: Type de message (register, message, request, response, discover, task_submit, task_assign, task_update)
- sender: Nom de l'émetteur
- to: Nom du destinataire
- content: Charge utile en clair ou chiffrée E2E
- reply_to: ID du message parent si réponse
- timestamp: Timestamp UNIX UTC
- token: Token JWT signé par le Hub
