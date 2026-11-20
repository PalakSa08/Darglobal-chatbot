---
title: DarGlobal Chatbot
sdk: docker
app_port: 7860
---

# DarGlobal & Wasalt RAG Chatbot

Scrapes public pages (respecting robots.txt) -> BM25 retrieval -> free OpenRouter model, served by FastAPI in Docker.

## Run locally
    pip install -r requirements.txt
    python scraper.py                      # builds data/corpus.jsonl
    export OPENROUTER_API_KEY=sk-or-...
    uvicorn app:app --port 7860            # http://localhost:7860

## Docker
    docker build -t dar-chatbot .
    docker run -p 7860:7860 -e OPENROUTER_API_KEY=sk-or-... dar-chatbot

## Config
- OPENROUTER_API_KEY (required, secret)
- OPENROUTER_MODEL (optional, comma-separated fallback list of free models)

## Design
- scraper.py: same-domain BFS crawl (60 pages/site), cleans HTML, chunks text (~900 chars)
- app.py: BM25 top-5 retrieval, grounded system prompt, model fallback, source URLs returned
