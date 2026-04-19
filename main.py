import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Llama Bridge API")
OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

if not OLLAMA_URL:
    raise ValueError("Error: OLLAMA_URL is not exist in .env!")
class ChatRequest(BaseModel):
    prompt: str

@app.post("/ask")
async def ask_llama(request: ChatRequest):
    payload = {
        "model": MODEL_NAME,
        "prompt": request.prompt,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))