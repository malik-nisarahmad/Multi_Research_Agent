import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("ERROR: GROQ_API_KEY is not set in environment.")
        return
        
    print(f"Testing Groq key: {key[:8]}... (length: {len(key)})")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-8b-instant", # using smaller model for quick ping test
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0.1
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"HTTP Status: {response.status_code}")
            print(f"Response Body: {response.text}")
        except Exception as e:
            print(f"Connection Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test())
