import os, json, re
from pathlib import Path
from dotenv import dotenv_values, load_dotenv
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)

DATA = BASE_DIR / "data" / "corpus.jsonl"
STATIC_DIR = BASE_DIR / "static"

DEFAULT_MODELS = "nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3.5-super-vl:free,baidu/ernie-5.5-flash-preview:free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"

def get_config():
    vals = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = vals.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
    key = key.strip().strip("'\"")
    models_str = vals.get("OPENROUTER_MODEL") or os.getenv("OPENROUTER_MODEL", DEFAULT_MODELS)
    models = [m.strip() for m in models_str.split(",") if m.strip()]
    return key, models

tok = lambda s: re.findall(r"\w+", s.lower())
docs = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()] if DATA.exists() else []
bm25 = BM25Okapi([tok(d["text"]) for d in docs]) if docs else None

SYSTEM = ("You are a helpful assistant for DarGlobal (luxury branded real estate developer) and Wasalt "
          "(Saudi real estate platform). Answer ONLY from the provided context. If the context lacks the "
          "answer, say you don't have that information. Be concise and mention the company you refer to.")

app = FastAPI(title="DarGlobal & Wasalt Chatbot")

class Chat(BaseModel):
    message: str
    history: list[dict] = []

@app.get("/", response_class=HTMLResponse)
def home():
    index_file = STATIC_DIR / "index.html"
    return index_file.read_text(encoding="utf-8") if index_file.exists() else "<h1>DarGlobal & Wasalt Chatbot</h1>"

@app.get("/health")
def health():
    key, _ = get_config()
    return {"ok": True, "chunks": len(docs), "key_set": bool(key)}

@app.post("/chat")
async def chat(req: Chat):
    if not bm25 or not docs:
        return {"answer": "Knowledge base is empty. Please run scraper or add corpus data.", "sources": []}
    scores = bm25.get_scores(tok(req.message))
    top = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[:5]
    ctx = "\n\n".join(f"[{docs[i]['company']} | {docs[i]['url']}]\n{docs[i]['text']}" for i in top)
    sources = list(dict.fromkeys(docs[i]["url"] for i in top))

    key, models = get_config()
    if not key:
        return {
            "answer": "OpenRouter API key is not set. Please set OPENROUTER_API_KEY in your .env file or environment variables to receive AI answers.\n\nRetrieved context from knowledge base:\n" + ctx,
            "sources": sources
        }

    msgs = [{"role": "system", "content": SYSTEM + "\n\nContext:\n" + ctx}]
    msgs += [m for m in req.history[-6:] if m.get("role") in ("user", "assistant")]
    msgs.append({"role": "user", "content": req.message})
    async with httpx.AsyncClient(timeout=60) as c:
        for model in models:
            try:
                r = await c.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": msgs, "temperature": 0.2}
                )
                if r.status_code == 200:
                    data = r.json()
                    answer = data["choices"][0]["message"]["content"]
                    return {"answer": answer, "sources": sources}
            except Exception:
                continue
    return {"answer": "The model is busy right now, please retry.", "sources": sources}
