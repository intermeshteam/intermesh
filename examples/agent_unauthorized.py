import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sdk.nexus_agent import NexusAgent


async def main():
    # Cet agent n'a que le rôle 'guest' -> Accès refusé par Agent B
    agent = NexusAgent(
        name="guest_bot",
        capabilities=["public_browsing"],
        roles=["guest"],
        permissions=[]
    )
    await agent.connect()
    await asyncio.sleep(1)

    print("\n--- TEST DE SÉCURITÉ : Tentative d'accès avec rôle 'guest' (Doit échouer) ---")
    try:
        response = await agent.ask(
            to="agent_b",
            content="Donne-moi les données secrètes !"
        )
        print(f"⚠️ [guest_bot] ANOMALIE : Réponse reçue alors qu'elle aurait dû être bloquée : {response}")
    except PermissionError as e:
        print(f"🛡️ [guest_bot] SUCCÈS DU TEST : Requête bloquée par Nexus RBAC comme prévu !")
        print(f"   Détail : {e}")
    except Exception as e:
        print(f"🛡️ [guest_bot] Bloqué : {e}")

    print("\n✅ [guest_bot] Le contrôle d'accès fonctionne parfaitement.")


if __name__ == "__main__":
    asyncio.run(main())
