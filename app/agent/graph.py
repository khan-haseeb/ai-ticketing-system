from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.extract_slots import extract_slots
from app.agent.nodes.resolve_entities import resolve_entities
from app.agent.nodes.classify_intent import classify_intent
from app.agent.nodes.check_slots import check_slots
from app.agent.nodes.execute_tool import execute_tool


async def ask_resume_choice(state: dict) -> dict:
    session = state.get("session") or {}
    workflows = session.get("workflows") or {}
    lines = []
    for intent, wf in workflows.items():
        collected = wf.get("collected", {})
        summary = ", ".join(f"{k}={v}" for k, v in collected.items()) or "nothing yet"
        lines.append(f"- **{intent.replace('_', ' ')}** ({summary})")
    state["final_response"] = (
        "You've got a few things in progress:\n" + "\n".join(lines) +
        "\n\nWhich one should I continue?"
    )
    return state


async def handle_unknown(state: dict) -> dict:
    state["final_response"] = (
        "I'm not sure what you'd like to do. I can help you:\n"
        "- **Create** tickets, users, or projects\n"
        "- **Show** existing tickets, users, or projects\n\n"
        "What would you like to do?"
    )
    return state


graph = StateGraph(AgentState)

graph.add_node("classify_intent", classify_intent)
graph.add_node("ask_resume_choice", ask_resume_choice)
graph.add_node("handle_unknown", handle_unknown)
graph.add_node("extract_slots", extract_slots)
graph.add_node("resolve_entities", resolve_entities)   # NEW: name → UUID
graph.add_node("check_slots", check_slots)
graph.add_node("execute_tool", execute_tool)

graph.set_entry_point("classify_intent")


def route_after_classify(state: dict) -> str:
    if state.get("needs_resume_disambiguation"):
        return "ask_resume_choice"
    if state.get("is_helper_query"):
        return "execute_tool"
    if state.get("active_intent") == "unknown":
        return "handle_unknown"
    return "extract_slots"


graph.add_conditional_edges("classify_intent", route_after_classify, {
    "execute_tool": "execute_tool",
    "ask_resume_choice": "ask_resume_choice",
    "handle_unknown": "handle_unknown",
    "extract_slots": "extract_slots",
})

graph.add_edge("ask_resume_choice", END)
graph.add_edge("handle_unknown", END)

# After extracting slots, resolve any name→UUID references before checking
graph.add_edge("extract_slots", "resolve_entities")


def route_after_slots(state: dict) -> str:
    if state.get("missing_fields"):
        return END
    return "execute_tool"


graph.add_edge("resolve_entities", "check_slots")
graph.add_conditional_edges("check_slots", route_after_slots)
graph.add_edge("execute_tool", END)

app_graph = graph.compile()