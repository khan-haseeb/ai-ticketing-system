from groq import AsyncGroq
from app.config import settings

client = AsyncGroq(api_key=settings.groq_api_key)

# openai/gpt-oss-120b is the current recommended model as of June 2026.
# llama3-70b-8192 and llama-3.3-70b-versatile are both decommissioned.
PRIMARY_MODEL = "openai/gpt-oss-120b"
FAST_MODEL = "openai/gpt-oss-20b"


async def ask_llm(prompt: str, system: str = "You are a helpful assistant that always returns a valid JSON object.") -> str:
    response = await client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )
    return response.choices[0].message.content


async def ask_llm_with_history(messages: list[dict], system: str) -> str:
    """Call LLM with full conversation history for context-aware responses."""
    full_messages = [{"role": "system", "content": system}] + messages
    response = await client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=full_messages,
        temperature=0.2
    )
    return response.choices[0].message.content