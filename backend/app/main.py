import os
from dotenv import load_dotenv

# Load local environment configuration first, before other imports
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphInterrupt
from app.graph import app_graph
from app.trace import (
    session_traces, 
    get_session_trace, 
    reset_session_trace, 
    update_session_metadata
)


app = FastAPI(title="Multi-Agent Business Research Assistant API")

# Setup CORS
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ClarifyRequest(BaseModel):
    session_id: str
    clarification: str

def has_env_value(*names: str) -> bool:
    return any(os.getenv(name) for name in names)

def active_llm_key_name() -> str:
    if has_env_value("GROQ_API_KEY", "groqapikey", "GROQAPIKEY"):
        return "GROQ_API_KEY / groqapikey"
    if os.getenv("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY"
    return "GEMINI_API_KEY"

def serialize_messages(messages) -> List[Dict[str, Any]]:
    """
    Format message objects and dicts to a clean serializable list for the frontend.
    """
    serialized = []
    for msg in messages:
        # Determine role
        if hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
            content = getattr(msg, "content", "")
            # Check if there is an agent name associated
            name = getattr(msg, "name", None)
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            name = msg.get("name")
        else:
            role = "user"
            content = str(msg)
            name = None
            
        if role == "assistant" and not name:
            name = "Synthesis Agent"
            
        serialized.append({
            "role": role,
            "content": content,
            "name": name
        })
    return serialized

@app.post("/chat")
async def chat_endpoint(payload: ChatRequest):
    session_id = payload.session_id
    message = payload.message
    
    # 1. Reset trace tracking states for this session run
    reset_session_trace(session_id)
    update_session_metadata(session_id, status="running")
    trace = get_session_trace(session_id)
    
    config = {"configurable": {"thread_id": session_id}}
    
    # 2. Append new user query to messages and state run
    # LangGraph automerges new messages through the state reducer
    initial_input = {
        "messages": [HumanMessage(content=message)],
        "query": message
    }
    
    try:
        # Execute the LangGraph workflow
        async for _ in app_graph.astream(initial_input, config, stream_mode="values"):
            pass
    except GraphInterrupt:
        pass
    except Exception as e:
        print(f"[GRAPH RUN] Error: {str(e)}")
        update_session_metadata(session_id, status="idle")
        active_key = active_llm_key_name()
        err_msg = f"⚠️ **Backend Execution Error**\n\n```\n{str(e)}\n```\n\n**Troubleshooting Checklist:**\n1. Verify that **`{active_key}`** is set correctly in your `/backend/.env` file.\n2. Ensure you **restarted your backend terminal (uvicorn)** after saving the key, as environment changes do not take effect in already running processes."
        app_graph.update_state(config, {"messages": [{"role": "assistant", "content": err_msg, "name": "System"}]})
        return {
            "response": err_msg,
            "status": "error",
            "awaiting_clarification": False,
            "agent_trace": trace["agent_trace"]
        }
        
    # 3. Retrieve final state post-run to check for pauses or completions
    updated_state = app_graph.get_state(config)
    state_values = updated_state.values if updated_state else {}
    next_steps = updated_state.next if updated_state else []
    
    # Determine if graph is suspended awaiting clarity agent clarification
    is_awaiting = len(next_steps) > 0 and next_steps[0] == "clarity_agent"
    trace = get_session_trace(session_id)
    
    if is_awaiting:
        # Retrieve the interrupt prompt message from LangGraph tasks
        interrupt_prompt = "Which company are you asking about? Please clarify."
        if updated_state and updated_state.tasks:
            for task in updated_state.tasks:
                if task.interrupts:
                    interrupt_prompt = task.interrupts[0].value.get("prompt", interrupt_prompt)
                    
        update_session_metadata(session_id, status="awaiting_clarification")
        
        # Save clarity agent question to message history so it aligns with standard chat
        # LangGraph allows adding messages when in suspended state
        # We can append it to checkpointer state by updating state
        app_graph.update_state(
            config,
            {"messages": [{"role": "assistant", "content": interrupt_prompt, "name": "Clarity Agent"}]}
        )
        
        return {
            "response": interrupt_prompt,
            "status": "awaiting_clarification",
            "awaiting_clarification": True,
            "agent_trace": trace["agent_trace"]
        }
    else:
        # If successfully compiled down to final response
        response = state_values.get("final_response", "Failed to compile research summary.")
        update_session_metadata(session_id, status="idle")
        
        # Save final report to message history so history endpoint returns it
        app_graph.update_state(
            config,
            {"messages": [{"role": "assistant", "content": response, "name": "Synthesis Agent"}]}
        )
        
        return {
            "response": response,
            "status": "completed",
            "awaiting_clarification": False,
            "agent_trace": trace["agent_trace"]
        }

@app.post("/clarify")
async def clarify_endpoint(payload: ClarifyRequest):
    session_id = payload.session_id
    clarification = payload.clarification
    
    config = {"configurable": {"thread_id": session_id}}
    
    # Verify the thread is actually paused
    current_state = app_graph.get_state(config)
    if not current_state or not current_state.next:
        raise HTTPException(status_code=400, detail="No active clarification request found for this session.")
        
    update_session_metadata(session_id, status="running")
    trace = get_session_trace(session_id)
    
    # Save the user clarification to message history
    app_graph.update_state(
        config,
        {"messages": [{"role": "user", "content": clarification}]}
    )
    
    try:
        # Resume the graph from the clarification interrupt
        # Pass the resume value inside the Command
        from langgraph.types import Command
        async for _ in app_graph.astream(Command(resume=clarification), config, stream_mode="values"):
            pass
    except GraphInterrupt:
        pass
    except Exception as e:
        print(f"[GRAPH CLARIFY] Error: {str(e)}")
        update_session_metadata(session_id, status="idle")
        active_key = active_llm_key_name()
        err_msg = f"⚠️ **Backend Execution Error**\n\n```\n{str(e)}\n```\n\n**Troubleshooting Checklist:**\n1. Verify that **`{active_key}`** is set correctly in your `/backend/.env` file.\n2. Ensure you **restarted your backend terminal (uvicorn)** after saving the key, as environment changes do not take effect in already running processes."
        app_graph.update_state(config, {"messages": [{"role": "assistant", "content": err_msg, "name": "System"}]})
        return {
            "response": err_msg,
            "status": "error",
            "awaiting_clarification": False,
            "agent_trace": trace["agent_trace"]
        }
        
    # Check post-resume state
    updated_state = app_graph.get_state(config)
    state_values = updated_state.values if updated_state else {}
    next_steps = updated_state.next if updated_state else []
    
    is_awaiting = len(next_steps) > 0 and next_steps[0] == "clarity_agent"
    trace = get_session_trace(session_id)
    
    if is_awaiting:
        interrupt_prompt = "Which company are you asking about? Please clarify."
        if updated_state and updated_state.tasks:
            for task in updated_state.tasks:
                if task.interrupts:
                    interrupt_prompt = task.interrupts[0].value.get("prompt", interrupt_prompt)
                    
        update_session_metadata(session_id, status="awaiting_clarification")
        
        # Save new clarification prompt to history
        app_graph.update_state(
            config,
            {"messages": [{"role": "assistant", "content": interrupt_prompt, "name": "Clarity Agent"}]}
        )
        
        return {
            "response": interrupt_prompt,
            "status": "awaiting_clarification",
            "awaiting_clarification": True,
            "agent_trace": trace["agent_trace"]
        }
    else:
        response = state_values.get("final_response", "Failed to compile research summary.")
        update_session_metadata(session_id, status="idle")
        
        # Save final report to message history
        app_graph.update_state(
            config,
            {"messages": [{"role": "assistant", "content": response, "name": "Synthesis Agent"}]}
        )
        
        return {
            "response": response,
            "status": "completed",
            "awaiting_clarification": False,
            "agent_trace": trace["agent_trace"]
        }

@app.get("/history/{session_id}")
async def get_history_endpoint(session_id: str):
    config = {"configurable": {"thread_id": session_id}}
    state = app_graph.get_state(config)
    
    messages = []
    if state and state.values:
        messages = state.values.get("messages", [])
        
    serialized = serialize_messages(messages)
    trace = get_session_trace(session_id)
    
    return {
        "messages": serialized,
        "agent_trace": trace["agent_trace"],
        "confidence_score": trace["confidence_score"],
        "research_attempts": trace["research_attempts"],
        "status": trace["status"],
        "awaiting_clarification": trace["status"] == "awaiting_clarification"
    }

@app.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    # Clear checkpointer state
    config = {"configurable": {"thread_id": session_id}}
    try:
        if hasattr(app_graph.checkpointer, "storage"):
            app_graph.checkpointer.storage.pop(session_id, None)
        elif hasattr(app_graph.checkpointer, "store") and hasattr(app_graph.checkpointer.store, "pop"):
            app_graph.checkpointer.store.pop(session_id, None)
    except Exception as e:
        print(f"[DELETE SESSION] Failed to clear MemorySaver checkpointer: {e}")
        
    # Clear trace memory
    session_traces.pop(session_id, None)
    
    return {"status": "success", "message": f"Session {session_id} successfully deleted."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
