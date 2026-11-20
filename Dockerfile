FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Scrape at build time unless data already exists (don't fail the build if a site blocks us)
RUN [ -s data/corpus.jsonl ] || python scraper.py || true
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
