import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_groq():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("[GROQ] No GROQ_API_KEY set. Skipping.")
        return False
    print(f"[GROQ] Testing key: {key[:10]}... (length: {len(key)})")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Say hello in one word."}],
        "temperature": 0.1, "max_tokens": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, headers=headers, timeout=10.0)
            print(f"[GROQ] HTTP {r.status_code}: {r.text[:200]}")
            return r.status_code == 200
        except Exception as e:
            print(f"[GROQ] Error: {e}")
            return False

async def test_gemini_rest():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("[GEMINI] No GEMINI_API_KEY set. Skipping.")
        return False
    print(f"[GEMINI] Testing key: {key[:10]}... (length: {len(key)})")
    
    # Use the v1beta REST API directly (no deprecated SDK needed)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": "Say hello in one word."}]}]
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=10.0)
            print(f"[GEMINI] HTTP {r.status_code}: {r.text[:300]}")
            return r.status_code == 200
        except Exception as e:
            print(f"[GEMINI] Error: {e}")
            return False

async def main():
    print("=" * 50)
    print("Testing all configured LLM API keys...")
    print("=" * 50)
    
    groq_ok = await test_groq()
    gemini_ok = await test_gemini_rest()
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print(f"  Groq:   {'WORKING' if groq_ok else 'FAILED'}")
    print(f"  Gemini: {'WORKING' if gemini_ok else 'FAILED'}")
    print("=" * 50)
    
    if groq_ok:
        print("\n>> Use GROQ_API_KEY — it's working!")
    elif gemini_ok:
        print("\n>> Your Gemini key works! I'll switch the backend to use the Gemini REST API (not the broken SDK).")
    else:
        print("\n>> Both keys failed. You need a valid key from either https://console.groq.com/keys or https://aistudio.google.com/apikey")

if __name__ == "__main__":
    asyncio.run(main())
