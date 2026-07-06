"""
Session manager: Redis-backed conversation state with automatic history compression.

History is stored under "history" key as a list of {role, content} dicts.
When history exceeds COMPRESS_THRESHOLD turns, the oldest turns get summarized
by the LLM into a "history_summary" string. This keeps token usage low while
preserving full conversational context across long sessions.
"""
import json
import uuid
from app.redis_client import redis_client

COMPRESS_THRESHOLD = 20   # compress when history exceeds this many turns
KEEP_RECENT = 6           # always keep this many recent turns verbatim after compression


class SessionManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        initial_state = {
            "session_id": session_id,
            "history": [],
            "history_summary": None,   # compressed summary of older turns
            "active_intent": None,
            "workflows": {},
            "last_entity": None,
            "schema_context": None,    # injected once at session start
        }
        await self.redis.set(f"session:{session_id}", json.dumps(initial_state))
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        session_data = await self.redis.get(f"session:{session_id}")
        if session_data:
            return json.loads(session_data)
        return None

    async def update_session(self, session_id: str, updates: dict):
        session = await self.get_session(session_id)
        if session:
            session.update(updates)
            await self.redis.set(f"session:{session_id}", json.dumps(session))

    async def delete_session(self, session_id: str):
        await self.redis.delete(f"session:{session_id}")

    async def add_message(self, session_id: str, role: str, content: str):
        session = await self.get_session(session_id)
        if not session:
            return
        session["history"].append({"role": role, "content": content})

        # Auto-compress if history is getting long
        if len(session["history"]) > COMPRESS_THRESHOLD:
            session = await self._compress_history(session)

        await self.redis.set(f"session:{session_id}", json.dumps(session))

    async def _compress_history(self, session: dict) -> dict:
        """
        Summarize the oldest turns into history_summary, keep KEEP_RECENT recent turns.
        Uses the LLM to write the summary — lazy import to avoid circular deps.
        """
        from app.agent.llm import ask_llm

        history = session["history"]
        to_compress = history[:-KEEP_RECENT]
        to_keep = history[-KEEP_RECENT:]

        if not to_compress:
            return session

        turns_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in to_compress
        )

        existing_summary = session.get("history_summary") or ""
        summary_prefix = f"Previous summary: {existing_summary}\n\n" if existing_summary else ""

        prompt = (
            f"{summary_prefix}"
            f"Summarize the following conversation turns into 3-5 sentences. "
            f"Preserve: what the user was trying to do, any names/emails/project names mentioned, "
            f"any decisions made, and any pending tasks.\n\n{turns_text}"
        )

        try:
            new_summary = await ask_llm(prompt)
            session["history_summary"] = new_summary.strip()
            session["history"] = to_keep
        except Exception:
            # If compression fails, just truncate without summarizing
            session["history"] = to_keep

        return session

    def build_history_for_llm(self, session: dict) -> list[dict]:
        """
        Returns the message list to pass to the LLM, prepending the history
        summary as a system-style message when one exists.
        """
        messages = []
        summary = session.get("history_summary")
        if summary:
            messages.append({
                "role": "user",
                "content": f"[Earlier in this conversation: {summary}]"
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I have context from our earlier conversation."
            })
        messages.extend(session.get("history", []))
        return messages


session_manager = SessionManager(redis_client)