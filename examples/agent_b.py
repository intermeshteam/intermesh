import asyncio
import os
from nexus_sdk import NexusAgent

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


async def compute_handler(input_data, task):
    await asyncio.sleep(0.5)
    expr = input_data.get("expression", "0")
    print(f"📊 [agent_b] Calcul : {expr}")
    return {"result": eval(expr, {"__builtins__": None}, {}), "status": "computed"}


async def main():
    agent = NexusAgent(name="agent_b", capabilities=["calculate"], roles=["worker"], hub_url=HUB_URL)
    agent.on_task(compute_handler)
    await agent.connect()
    print(f"⏳ [agent_b] En écoute sur {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
