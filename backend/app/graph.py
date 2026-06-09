from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import AgentState
from app.agents import clarity_agent, research_agent, validator_agent, synthesis_agent


def route_after_clarity(state: AgentState) -> str:
    """
    Clear requests continue to research. Unclear requests are normally paused by interrupt.
    """
    if state.get("clarity_status") == "clear":
        return "research_agent"
    return "end"


def route_after_research(state: AgentState) -> str:
    """
    Low-confidence research goes to validation; confident research can be synthesized.
    """
    if state.get("confidence_score", 0) < 6:
        return "validator_agent"
    return "synthesis_agent"


def route_after_validation(state: AgentState) -> str:
    """
    Loop back for another research attempt when validation fails, up to 3 attempts.
    """
    if (
        state.get("validation_result") == "insufficient"
        and state.get("research_attempts", 0) < 3
    ):
        return "research_agent"
    return "synthesis_agent"


def build_checkpointer():
    """
    Use SQLite checkpointing for persistent local LangGraph memory.
    Otherwise fall back to in-memory sessions for local development.
    """
    import os
    import sqlite3

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sqlite_path = os.getenv(
        "SQLITE_DATABASE_PATH",
        os.path.join("scratch", "langgraph_checkpoints.sqlite")
    )
    if not os.path.isabs(sqlite_path):
        sqlite_path = os.path.join(backend_dir, sqlite_path)

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        if hasattr(checkpointer, "setup"):
            checkpointer.setup()
        return checkpointer
    except Exception as exc:
        print(f"[CHECKPOINTER] SQLite unavailable, using MemorySaver: {exc}")
        return MemorySaver()

# Define the state graph
workflow = StateGraph(AgentState)

# Add agent nodes
workflow.add_node("clarity_agent", clarity_agent)
workflow.add_node("research_agent", research_agent)
workflow.add_node("validator_agent", validator_agent)
workflow.add_node("synthesis_agent", synthesis_agent)

# Define graph structure & transitions
workflow.add_edge(START, "clarity_agent")
workflow.add_conditional_edges(
    "clarity_agent",
    route_after_clarity,
    {
        "research_agent": "research_agent",
        "end": END
    }
)
workflow.add_conditional_edges(
    "research_agent",
    route_after_research,
    {
        "validator_agent": "validator_agent",
        "synthesis_agent": "synthesis_agent"
    }
)
workflow.add_conditional_edges(
    "validator_agent",
    route_after_validation,
    {
        "research_agent": "research_agent",
        "synthesis_agent": "synthesis_agent"
    }
)
workflow.add_edge("synthesis_agent", END)

# Persistent state by session_id (thread_id)
checkpointer = build_checkpointer()

# Compile the graph
app_graph = workflow.compile(checkpointer=checkpointer)
