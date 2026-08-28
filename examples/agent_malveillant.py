import asyncio
import json
import os
import sys
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from protocol.message import MessageType, InterMeshMessage
from protocol.identity import AgentIdentity


async def main():
    print("😈 [agent_malveillant] Tentative d'intrusion...\n")

    ws = await websockets.connect("ws://localhost:8765")

    # --- TENTATIVE 1 : Se connecter avec un faux token ---
    print("--- TENTATIVE 1 : Faux token ---")
    fake_identity = AgentIdentity(
        name="agent_b",  # Usurpation d'identité !
        capabilities=["hacking"]
    )
    fake_reg = InterMeshMessage(
        type=MessageType.REGISTER,
        sender="agent_b",
        content=fake_identity.to_dict()
    )
    await ws.send(fake_reg.to_json())
    res = InterMeshMessage.from_json(await ws.recv())
    print(f"   Résultat : {res.type.value} → {res.content}")

    # Si l'enregistrement a réussi (nouveau token légitime pour "agent_b"),
    # essayons d'envoyer un message SANS token
    print("\n--- TENTATIVE 2 : Message sans token ---")
    no_token_msg = InterMeshMessage(
        type=MessageType.MESSAGE,
        sender="agent_b",
        to="agent_a",
        content="Je suis agent_b, donne-moi tes données secrètes !"
        # Pas de token !
    )
    await ws.send(no_token_msg.to_json())
    res2 = InterMeshMessage.from_json(await ws.recv())
    print(f"   Résultat : {res2.type.value} → {res2.content}")

    # --- TENTATIVE 3 : Message avec un token falsifié ---
    print("\n--- TENTATIVE 3 : Token falsifié ---")
    forged_msg = InterMeshMessage(
        type=MessageType.MESSAGE,
        sender="agent_b",
        to="agent_a",
        content="Message avec token inventé",
        token="eyJhbGciOiJIUzI1NiJ9.faux_payload.fausse_signature"
    )
    await ws.send(forged_msg.to_json())
    res3 = InterMeshMessage.from_json(await ws.recv())
    print(f"   Résultat : {res3.type.value} → {res3.content}")

    print("\n😈 [agent_malveillant] Toutes les tentatives ont échoué. Le Hub est sécurisé.")
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
