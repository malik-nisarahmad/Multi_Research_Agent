from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # full conversation history
    query: str
    clarity_status: str          # "clear" | "needs_clarification"
    research_findings: str
    confidence_score: float      # 0–10
    validation_result: str       # "sufficient" | "insufficient"
    validation_notes: str
    research_attempts: int       # max 3
    final_response: str
    awaiting_clarification: bool
    company: str
