import os
import json
import asyncio
import httpx
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from app.state import AgentState
from app.tools import get_company_research
from app.trace import update_agent_status, update_session_metadata, finalize_skipped_agents
from langgraph.types import interrupt


def get_env_value(*names: str) -> str | None:
    """
    Read the first configured environment variable from a list of accepted names.
    """
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None

async def call_openrouter(system_instruction: str, prompt: str, response_mime_type: str = None) -> str:
    """
    Call OpenRouter API directly via its chat completions REST endpoint.
    Retries up to 3 times on HTTP 429 (rate limits) with exponential backoff.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash:free")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1
    }
    
    if response_mime_type == "application/json":
        payload["response_format"] = {"type": "json_object"}
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Business Research Assistant"
    }
    
    max_retries = 3
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            response = await client.post(url, json=payload, headers=headers, timeout=45.0)
            
            if response.status_code in (429, 500, 502, 503, 504):
                wait_time = 2 ** attempt * 3  # 3s, 6s, 12s
                print(f"[OPENROUTER] Transient error ({response.status_code}). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                await asyncio.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as parse_err:
                raise Exception(f"Failed to parse OpenRouter response: {data}")
                
    raise Exception(f"OpenRouter API rate limit exceeded after {max_retries} retries. Please wait a minute and try again.")

async def call_gemini(system_instruction: str, prompt: str, response_mime_type: str = None) -> str:
    """
    Call Google Gemini API directly via its v1beta REST endpoint.
    Retries up to 3 times on HTTP 429 (rate limits) with exponential backoff.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }
        
    generation_config = {
        "temperature": 0.1
    }
    if response_mime_type == "application/json":
        generation_config["responseMimeType"] = "application/json"
        
    payload["generationConfig"] = generation_config
    
    headers = {
        "Content-Type": "application/json"
    }
    
    max_retries = 3
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            response = await client.post(url, json=payload, headers=headers, timeout=45.0)
            
            if response.status_code in (429, 500, 502, 503, 504):
                wait_time = 2 ** attempt * 3  # 3s, 6s, 12s
                print(f"[GEMINI] Transient error ({response.status_code}). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                await asyncio.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as parse_err:
                raise Exception(f"Failed to parse Gemini API response: {data}")
                
    raise Exception(f"Gemini API rate limit exceeded after {max_retries} retries. Please wait a minute and try again.")

async def call_groq(system_instruction: str, prompt: str, response_mime_type: str = None) -> str:
    """
    Call Groq's OpenAI-compatible chat completions endpoint.
    """
    api_key = get_env_value("GROQ_API_KEY", "groqapikey", "GROQAPIKEY")
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1
    }

    if response_mime_type == "application/json":
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    max_retries = 3

    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=45.0
            )

            if response.status_code in (429, 500, 502, 503, 504):
                wait_time = 2 ** attempt * 3
                print(f"[GROQ] Transient error ({response.status_code}). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise Exception(f"Failed to parse Groq response: {data}")

    raise Exception(f"Groq API rate limit exceeded after {max_retries} retries. Please wait a minute and try again.")

async def call_llm(system_instruction: str, prompt: str, response_mime_type: str = None) -> str:
    """
    Routes LLM calls to Groq, OpenRouter, or Gemini API. Falls back to mock simulation if no key is set.
    """
    groq_key = get_env_value("GROQ_API_KEY", "groqapikey", "GROQAPIKEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if groq_key:
        return await call_groq(system_instruction, prompt, response_mime_type)
    elif openrouter_key:
        return await call_openrouter(system_instruction, prompt, response_mime_type)
    elif gemini_key:
        return await call_gemini(system_instruction, prompt, response_mime_type)

    # Simulated Fallback Mock (no API key configured)
    print("[LLM MOCK] No API key configured. Returning simulated mock response.")
    
    if response_mime_type == "application/json":
        if "clarity" in system_instruction.lower():
            lower_prompt = prompt.lower()
            detected_company = None
            for c in ["tesla", "apple", "nvidia", "google", "microsoft", "amazon", "openai"]:
                if c in lower_prompt:
                    detected_company = c.capitalize()
                    break
            
            if detected_company:
                return json.dumps({
                    "clarity_status": "clear",
                    "company": detected_company,
                    "clarification_prompt": None
                })
            else:
                return json.dumps({
                    "clarity_status": "needs_clarification",
                    "company": None,
                    "clarification_prompt": "Which company are you asking about? Please specify the company name (e.g., Apple, Tesla, Nvidia)."
                })
        
        elif "confidence" in system_instruction.lower() or "evaluator" in system_instruction.lower():
            return json.dumps({
                "confidence_score": 8.0,
                "justification": "Mock Evaluator: Gathered news and metrics correctly.",
                "company_name": "MockCompany"
            })
        
        elif "validator" in system_instruction.lower():
            return json.dumps({
                "validation_result": "sufficient",
                "missing_aspects": ""
            })
        
        # Default JSON fallback
        return json.dumps({"result": "mock"})
    else:
        company = "Tesla"
        for c in ["Apple", "Nvidia", "Google", "Microsoft", "Amazon", "Openai"]:
            if c.lower() in prompt.lower():
                company = c
                break
                
        return f"""# Business Research Report: {company} Inc. (Simulated)
 
## Overview
{company} is a leading global technology developer known for its innovation and strong market presence.
 
> **Note:** This is a simulated report because no API keys were configured. Add your key to `/backend/.env` for live results.
 
## Key Financials
- **Estimated Revenue**: $150B+ (LTM)
- **Market Standing**: Tier-1 technology sector leader
 
## Recent News
- Announced plans to expand data center capacities.
- Strategic partnerships formed with hardware providers.
 
## Key People
- **CEO**: John Doe (Simulated)
- **CTO**: Jane Smith (Simulated)
 
## Competitors
- **Competitor A**: Major industry alternative.
- **Competitor B**: Direct product competitor.
"""



def format_history(messages: list) -> str:
    """
    Format message history safely, replacing large research reports
    with small placeholders to prevent token limit (TPM) issues on the free tier.
    """
    history_str = ""
    for msg in messages:
        role = "User" if getattr(msg, "type", "") == "human" or (isinstance(msg, dict) and msg.get("role") == "user") else "Assistant"
        content = getattr(msg, "content", "") or (isinstance(msg, dict) and msg.get("content")) or str(msg)
        
        # If it's a long assistant report, replace it with a brief placeholder
        if role == "Assistant" and len(content) > 500:
            content = "[Synthesized Research Report]"
            
        history_str += f"{role}: {content}\n"
    return history_str


def parse_json_response(response_text: str) -> Dict[str, Any]:
    """
    Parse JSON even when a model wraps it in a fenced code block.
    """
    text = (response_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def infer_company_from_text(text: str) -> str | None:
    """
    Small deterministic fallback for common company names when the LLM JSON is malformed.
    """
    known_companies = {
        "tesla": "Tesla",
        "apple": "Apple",
        "nvidia": "Nvidia",
        "google": "Google",
        "alphabet": "Alphabet",
        "microsoft": "Microsoft",
        "amazon": "Amazon",
        "openai": "OpenAI",
        "meta": "Meta",
        "facebook": "Meta",
        "netflix": "Netflix",
        "uber": "Uber",
        "airbnb": "Airbnb",
        "walmart": "Walmart",
        "coca-cola": "Coca-Cola",
        "coca cola": "Coca-Cola"
    }
    lower_text = text.lower()
    for needle, company in known_companies.items():
        if needle in lower_text:
            return company
    return None

async def clarity_agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Clarity Agent checks if the query has a company name and clear intent.
    If ambiguous -> Interrupt and await user clarification.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    update_agent_status(session_id, "clarity", "running")
    
    query = state.get("query", "")
    
    messages = state.get("messages", [])
    history_str = format_history(messages)

    system_prompt = (
        "You are a business research clarity assistant. Your task is to analyze the conversation history and the latest user query to determine if they want to research a specific company.\n"
        "If the company name is explicitly mentioned or can be clearly inferred from the preceding messages (e.g. if the user says 'what about their CEO?' after researching Apple, the company is 'Apple'), set clarity_status to 'clear' and company to the name of that company.\n"
        "If the company name is not mentioned and cannot be inferred, or if the request is ambiguous, set clarity_status to 'needs_clarification' and write a polite clarification prompt asking the user to name the company they want to research.\n"
        "Return a JSON object with: \n"
        "1. 'clarity_status': 'clear' or 'needs_clarification'\n"
        "2. 'company': 'The name of the company' (string or null)\n"
        "3. 'clarification_prompt': 'A polite message asking the user to specify which company they mean' (string or null)"
    )
    
    user_prompt = f"Conversation History:\n{history_str}\n\nLatest Query:\n{query}"
    
    response_text = await call_llm(system_prompt, user_prompt, response_mime_type="application/json")
    try:
        data = parse_json_response(response_text)
    except Exception:
        inferred_company = infer_company_from_text(f"{history_str}\n{query}")
        data = {
            "clarity_status": "clear" if inferred_company else "needs_clarification",
            "company": inferred_company,
            "clarification_prompt": None if inferred_company else "Which company are you asking about? Please specify the company name."
        }
        
    if data.get("clarity_status") == "needs_clarification":
        update_session_metadata(session_id, status="awaiting_clarification")
        
        # LangGraph interrupt - execution pauses here.
        # When resumed, the resume value (user clarification) is returned.
        user_clarification = interrupt({
            "prompt": data.get("clarification_prompt") or "Which company are you asking about? Please clarify.",
            "status": "needs_clarification"
        })
        
        # When execution resumes, update trace status back to running
        update_session_metadata(session_id, status="running")
        update_agent_status(session_id, "clarity", "done")
        
        # Process clarification query
        new_query = f"Query: {query}. User clarified: {user_clarification}"
        
        # Run a quick check to extract the company name from the clarified input
        extract_prompt = "Extract the company name from this input. Return a JSON with field 'company'."
        extract_res = await call_llm(extract_prompt, f"Input: {new_query}", response_mime_type="application/json")
        try:
            extracted_company = parse_json_response(extract_res).get("company") or user_clarification
        except:
            extracted_company = user_clarification
            
        return {
            "query": f"Research company: {extracted_company}",
            "clarity_status": "clear",
            "awaiting_clarification": False,
            "company": extracted_company
        }
        
    update_agent_status(session_id, "clarity", "done")
    return {
        "clarity_status": "clear",
        "awaiting_clarification": False,
        "company": data.get("company") or "Tesla"
    }

async def research_agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Research Agent extracts the company name from state, and runs parallel Tavily searches.
    It assigns a confidence score so routing can decide whether validation is needed.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    update_agent_status(session_id, "research", "running")
    
    attempts = state.get("research_attempts", 0) + 1
    update_session_metadata(session_id, research_attempts=attempts)
    
    company = state.get("company") or "Tesla"
    latest_query = state.get("query", "")
    validation_notes = state.get("validation_notes", "")
        
    tavily_key = os.getenv("TAVILY_API_KEY")
    findings = await get_company_research(company, tavily_key, latest_query, validation_notes, attempts)

    evaluator_prompt = (
        "You are a business research evaluator. Score whether the search findings are specific, current, sourced, "
        "and adequate for the user's question. Return JSON only with these fields: "
        "confidence_score (number from 0 to 10), justification (string), company_name (string)."
    )
    evaluator_input = (
        f"Company: {company}\n"
        f"Latest user query: {latest_query}\n"
        f"Research attempt: {attempts}\n"
        f"Prior validation notes: {validation_notes or 'None'}\n\n"
        f"Search findings:\n{findings}"
    )

    try:
        confidence_data = parse_json_response(
            await call_llm(evaluator_prompt, evaluator_input, response_mime_type="application/json")
        )
        confidence = float(confidence_data.get("confidence_score", 0))
    except Exception:
        has_source = "Source:" in findings and "Network Error" not in findings and "Tavily API Error" not in findings
        confidence = 7.0 if has_source else 4.0

    confidence = max(0.0, min(10.0, confidence))
        
    update_session_metadata(session_id, confidence_score=confidence)
    update_agent_status(session_id, "research", "done")
    
    return {
        "research_findings": findings,
        "confidence_score": confidence,
        "research_attempts": attempts
    }

async def validator_agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Validator Agent checks whether the research is complete enough to answer the user.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    update_agent_status(session_id, "validator", "running")

    system_prompt = (
        "You are a strict research quality validator. Decide if the findings answer the user's business question "
        "with enough source-backed detail. Return JSON only with: validation_result ('sufficient' or 'insufficient'), "
        "missing_aspects (string). Mark insufficient when findings are generic, unsourced, unrelated, or missing the "
        "topic requested by the user."
    )
    user_prompt = (
        f"Company: {state.get('company', '')}\n"
        f"Latest user query: {state.get('query', '')}\n"
        f"Confidence score: {state.get('confidence_score', 0)}\n"
        f"Research attempts: {state.get('research_attempts', 0)}\n\n"
        f"Findings:\n{state.get('research_findings', '')}"
    )

    try:
        data = parse_json_response(await call_llm(system_prompt, user_prompt, response_mime_type="application/json"))
        result = data.get("validation_result", "insufficient")
        notes = data.get("missing_aspects", "")
    except Exception:
        result = "sufficient" if state.get("confidence_score", 0) >= 6 else "insufficient"
        notes = "The validator could not parse the model output; routing was based on confidence score."

    if result not in {"sufficient", "insufficient"}:
        result = "insufficient"

    update_agent_status(session_id, "validator", "done")

    return {
        "validation_result": result,
        "validation_notes": notes
    }

async def synthesis_agent(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Synthesis Agent writes a comprehensive report in beautiful markdown.
    """
    session_id = config.get("configurable", {}).get("thread_id", "default")
    
    # Handle skipped badges for other nodes
    finalize_skipped_agents(session_id)
    update_agent_status(session_id, "synthesis", "running")
    
    findings = state.get("research_findings", "")
    messages = state.get("messages", [])
    history_str = format_history(messages)
    validation_notes = state.get("validation_notes", "")
        
    system_prompt = (
        "You are a world-class business research compiler. Combine the search findings and conversation history "
        "into a professional, structured markdown summary.\n"
        "Preserve context for follow-up questions. If the latest question asks only about competitors, CEO, news, "
        "financials, or another focused topic, answer that topic directly while keeping the company context clear.\n"
        "You must organize the report into these exact sections with no placeholders:\n"
        "1. **Overview**: Clear description of the company, headquarters, industry, and main offerings.\n"
        "2. **Key Financials**: Highlight metrics (revenue, stock performance, valuations) using tables and bold formatting.\n"
        "3. **Recent News**: A bulleted list of recent company news, product releases, or controversies.\n"
        "4. **Key People**: Executives like CEO, CFO, and founders.\n"
        "5. **Competitors**: Major competitors and comparisons.\n"
        "Include source URLs from the findings when available. If validation reached max attempts and data is still thin, "
        "state that limitation briefly. Make sure the formatting is modern, readable, and highly professional."
    )
    user_prompt = (
        f"Company: {state.get('company', '')}\n"
        f"Latest query: {state.get('query', '')}\n"
        f"Confidence score: {state.get('confidence_score', 0)}\n"
        f"Validation result: {state.get('validation_result', '')}\n"
        f"Validation notes: {validation_notes or 'None'}\n\n"
        f"History:\n{history_str}\n\nSearch Findings:\n{findings}"
    )
    
    report = await call_llm(system_prompt, user_prompt)
    
    update_agent_status(session_id, "synthesis", "done")
    update_session_metadata(session_id, status="completed")
    
    return {
        "final_response": report
    }
