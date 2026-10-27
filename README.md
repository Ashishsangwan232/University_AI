# CampusAI

A chat assistant for LPU students. It answers two kinds of questions:

- **Your own data**, read live from the UMS portal: attendance, timetable, notices, messages, hostel leave balance, profile.
- **General university information** from a file we maintain ourselves: [backend/data/university_info.md](backend/data/university_info.md) (contacts, attendance rules, academic calendar, hostel and mess fees, health centre, placements, scholarships…). Nothing is crawled.

Questions are matched to that file with **hybrid search (RAG)**: by meaning, using a small free embedding model that runs locally ([fastembed](https://github.com/qdrant/fastembed), `BAAI/bge-small-en-v1.5`, no API key), and by keyword. So "dorm rent" finds *Hostel fees* even though no word matches. The first start downloads the model (~67 MB) into `backend/data/rag/models`; after that it works offline. Set `KNOWLEDGE_EMBEDDINGS=false` for keyword-only search. Test it with `python scripts/test_knowledge.py`.

```
my-app/   React chat UI (Vite)
backend/  FastAPI + AI agent (Ollama Cloud or Gemini) + Playwright UMS session + SQLite chat history
```

## Run

Backend (needs Python 3.12+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env      # then add OLLAMA_API_KEY and/or GEMINI_API_KEY
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd my-app
npm install
npm run dev
```

Open http://localhost:5173, ask a university question straight away, or click **Connect UMS**, sign in to UMS in the window that opens, and ask about your own data.

## Updating university information

Edit `backend/data/university_info.md` and restart the backend. Each `## ` heading is one section the bot can look up; keep the `Source:` line so answers can cite it.

## Privacy

CampusAI never sees or stores your UMS password — you sign in yourself in a dedicated browser window. `.env`, the browser profile and the chat database are git-ignored; never commit them.
