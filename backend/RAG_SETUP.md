# CampusAI Local Chunk RAG

This version does not require pgvector, Docker, Qdrant, or another vector database.

## How it works

1. Crawl the college website.
2. Extract readable page text.
3. Split text into overlapping chunks.
4. Generate local document embeddings with Ollama `embeddinggemma`.
5. Store chunks and embeddings in `data/rag/chunks.json`.
6. For a student question, generate a local query embedding with the same model.
7. Rank stored chunks using cosine similarity.
8. Remove duplicate pages and near-duplicate content so one page does not fill the whole result list.
9. Give the most relevant chunks to Gemini through the `search_college_knowledge` tool.

## Setup

Install the normal backend requirements:

```powershell
pip install -r requirements.txt
```

No PostgreSQL extension is required for RAG.

Set these in `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=embeddinggemma
RAG_TOP_K=5
```

## Ingest a website

```http
POST /api/rag/ingest
```

```json
{
  "url": "https://your-college-website.example",
  "max_pages": 20
}
```

The generated local store is:

```text
data/rag/chunks.json
```

## Search

```http
POST /api/rag/search
```

```json
{
  "query": "What is the examination registration deadline?",
  "limit": 5
}
```

## Agent

The Gemini agent can call `search_college_knowledge` for public college information. It remains separate from PostgreSQL tools such as attendance, timetable, announcements, and services. Ollama is used only for RAG embeddings; Gemini remains the agent/reasoning model.
