import asyncio
import os
import sys
import subprocess


async def run_all():
    print("=" * 60)
    print("   LANCEMENT DU WORKFLOW COMPLET INTERMESH PROTOCOL")
    print("=" * 60)

    # 1. Libérer le port 8765
    print("\n1. Nettoyage des anciens processus sur le port 8765...")
    os.system("fuser -k 8765/tcp || true")
    await asyncio.sleep(1.0)

    # 2. Démarrer le nouveau Hub de télémétrie en arrière-plan
    print("2. Démarrage du Hub (server/hub.py)...")
    hub = subprocess.Popen([sys.executable, "server/hub.py"])
    await asyncio.sleep(1.5)

    # 3. Démarrer l'Agent Traducteur (agent_c)
    print("3. Connexion de l'Agent Traducteur (translator_french)...")
    agent_c = subprocess.Popen([sys.executable, "examples/agent_c.py"])
    await asyncio.sleep(1.0)

    # 4. Démarrer l'Agent Calculateur (agent_b)
    print("4. Connexion de l'Agent Calculateur (agent_b)...")
    agent_b = subprocess.Popen([sys.executable, "examples/agent_b.py"])
    await asyncio.sleep(1.0)

    # 5. Exécuter l'Agent Orchestrateur (agent_a)
    print("\n5. Exécution du Workflow par l'Orchestrateur (agent_a) :\n")
    agent_a = subprocess.Popen([sys.executable, "examples/agent_a.py"])
    agent_a.wait()

    # Nettoyage
    print("\n6. Arrêt propre des agents et du Hub...")
    agent_b.terminate()
    agent_c.terminate()
    hub.terminate()
    print("✅ WORKFLOW TERMINÉ AVEC SUCCÈS !")


if __name__ == "__main__":
    asyncio.run(run_all())
