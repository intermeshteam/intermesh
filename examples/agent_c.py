import asyncio
import os
from nexus_sdk import NexusAgent

HUB_URL = os.getenv("HUB_URL", "ws://localhost:8765")


async def translate_handler(input_data, task):
    await asyncio.sleep(0.5)
    text = input_data.get("text", "")
    print(f"[translator_french] Translating: '{text}'")
    t = {
        "execute double of twenty": "calculer 2 * 20",
        "calculate five times five": "calculer 5 * 5"
    }
    return {
        "translated_text": t.get(text.lower(), f"calculer {text}"),
        "target_lang": input_data.get("target_lang", "fr")
    }


async def main():
    agent = NexusAgent(name="translator_french", capabilities=["translate"], roles=["worker"], hub_url=HUB_URL)
    agent.on_task(translate_handler)
    await agent.connect()
    print(f"[translator_french] Listening on {HUB_URL}...")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
