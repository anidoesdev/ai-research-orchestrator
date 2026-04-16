# AI Research Orchestrator

A full-stack research assistant that ingests arXiv paper summaries into a vector database, retrieves relevant chunks for user questions, and streams grounded answers to a React UI.

## What It Does

- Ingests paper summaries from arXiv by topic.
- Splits summaries into chunks and embeds them with `all-MiniLM-L6-v2`.
- Stores vectors in Postgres (`pgvector`) and queues ingestion tasks with Redis.
- Retrieves nearest chunks for each user query.
- Streams LLM responses to the frontend chat interface.

## Tech Stack

- **Backend:** FastAPI, asyncpg, Redis, SentenceTransformers, LangChain Groq, arXiv API
- **Vector DB:** PostgreSQL + `pgvector`
- **Queue:** Redis list (`ingestion_tasks`)
- **Frontend:** React + TypeScript + Vite + Tailwind CSS

## Project Structure

- `main.py` - FastAPI server, ingestion worker, retrieval + streaming endpoints
- `model.py` - LLM client configuration (Groq)
- `compose.yaml` - Postgres + Redis services
- `.env.example` - backend environment variable template
- `research-frontend/` - React frontend app

## Prerequisites

- Python 3.10+ (recommended 3.11/3.12)
- Node.js 20+
- npm
- Docker + Docker Compose (for Postgres and Redis)
- A valid `GROQ_API_KEY` in your environment

## Setup

### 1) Clone and enter project

```bash
git clone <your-repo-url>
cd ai-research-orchestrator
```

### 2) Configure environment

Create `.env` from template:

```bash
cp .env.example .env
```

Then set values as needed:

- `PG_USER`, `PG_PASSWORD`, `PG_DB`, `PG_HOST`, `PG_PORT`
- `REDIS_URL`
- `SENTENCE_TRANSFORMER_MODEL`
- `EMBEDDING_DIM`
- `GROQ_API_KEY` (required by `model.py`)

### 3) Start infra (Postgres + Redis)

```bash
docker compose up -d
```

This starts:

- Postgres on `localhost:5432`
- Redis on `localhost:6379`

### 4) Install backend dependencies

No `requirements.txt` is currently committed, so install manually:

```bash
pip install fastapi uvicorn[standard] asyncpg redis sentence-transformers arxiv langchain-text-splitters langchain-groq python-dotenv
```

### 5) Run backend

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 6) Run frontend

```bash
cd research-frontend
npm install
npm run dev
```

Frontend runs on Vite default (`http://localhost:5173`) and calls backend at `http://127.0.0.1:8000`.

## API Endpoints

### `GET /fetch-papers?topic=<topic>`

Queues a topic for ingestion into the vector store.

Example:

```bash
curl "http://127.0.0.1:8000/fetch-papers?topic=graph%20neural%20networks"
```

### `POST /trigger-research`

Retrieves nearest chunks and streams an LLM answer.

Request body:

```json
{
  "history": [
    { "role": "user", "text": "Explain how diffusion models work." }
  ]
}
```

Example:

```bash
curl -N -X POST "http://127.0.0.1:8000/trigger-research" \
  -H "Content-Type: application/json" \
  -d "{\"history\":[{\"role\":\"user\",\"text\":\"Explain transformer attention\"}]}"
```

### `GET /search-research?query=<query>`

Returns the top matching chunk from the vector DB.

Example:

```bash
curl "http://127.0.0.1:8000/search-research?query=quantum%20error%20correction"
```

## Current Behavior Notes

- Data in `research_papers` is now preserved across backend restarts.
- Ingestion worker runs in background and handles queue tasks continuously.
- Backend returns clearer validation/service errors for missing input or unavailable dependencies.
- Response generation is source-grounded and asks the model to cite source numbers (`[1]`, `[2]`).

## Troubleshooting

- **`Redis not initialized` / `DB not initialized`:** ensure `docker compose up -d` is running and env vars point to correct hosts/ports.
- **No answers or weak context:** ingest a topic first via `/fetch-papers`, then query.
- **Groq auth errors:** verify `GROQ_API_KEY` is exported in your shell or loaded in environment.
- **Port conflicts:** change backend or Vite ports if `8000` or `5173` are already used.

## Suggested Next Improvements

- Add a committed `requirements.txt` for reproducible backend setup.
- Add health endpoints (`/healthz`, `/readyz`) and structured logging.
- Add deduplication/versioning for ingested papers.
- Add backend tests for ingestion and retrieval endpoints.

