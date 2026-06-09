from typing import Dict, Any

# Global in-memory storage for active session traces
# Key: session_id
# Value: Dict containing status and agent trace badges
session_traces: Dict[str, Dict[str, Any]] = {}

def get_session_trace(session_id: str) -> Dict[str, Any]:
    """
    Get or initialize the trace details for a given session.
    """
    if session_id not in session_traces:
        session_traces[session_id] = {
            "status": "idle",
            "agent_trace": {
                "clarity": "pending",
                "research": "pending",
                "validator": "pending",
                "synthesis": "pending"
            },
            "confidence_score": 0.0,
            "research_attempts": 0
        }
    return session_traces[session_id]

def update_agent_status(session_id: str, agent: str, status: str):
    """
    Update the status badge for a single agent (e.g., 'running', 'done', 'skipped').
    """
    trace_data = get_session_trace(session_id)
    trace_data["agent_trace"][agent] = status

def reset_session_trace(session_id: str):
    """
    Reset all statuses to pending before starting a new run.
    """
    session_traces[session_id] = {
        "status": "running",
        "agent_trace": {
            "clarity": "pending",
            "research": "pending",
            "validator": "pending",
            "synthesis": "pending"
        },
        "confidence_score": 0.0,
        "research_attempts": 0
    }

def update_session_metadata(session_id: str, confidence_score: float = None, research_attempts: int = None, status: str = None):
    """
    Update confidence score, attempt count, or main session status.
    """
    trace_data = get_session_trace(session_id)
    if confidence_score is not None:
        trace_data["confidence_score"] = confidence_score
    if research_attempts is not None:
        trace_data["research_attempts"] = research_attempts
    if status is not None:
        trace_data["status"] = status

def finalize_skipped_agents(session_id: str):
    """
    Mark all agents that did not run as skipped when the synthesis agent completes or starts.
    """
    trace_data = get_session_trace(session_id)
    for agent in ["clarity", "research", "validator"]:
        if trace_data["agent_trace"][agent] == "pending":
            trace_data["agent_trace"][agent] = "skipped"

