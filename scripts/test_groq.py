"""Test Groq client."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(override=True)

from src.llm.remote_clients import GroqClient
from src.api.config import config


async def test_groq():
    if not config.GROQ_API_KEY:
        print("No Groq API key found")
        return

    client = GroqClient(config.GROQ_API_KEY)
    print(f"Testing Groq with key: {config.GROQ_API_KEY[:5]}...")

    try:
        response = await client.generate(
            prompt="Hello, say hi!", model="llama-3.3-70b-versatile"
        )
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Details: {e.response.text}")


if __name__ == "__main__":
    asyncio.run(test_groq())
