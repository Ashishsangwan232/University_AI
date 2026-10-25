# CampusAI

A chat assistant for LPU students. It answers two kinds of questions:

- **Your own data**, read live from the UMS portal: attendance, timetable, notices, messages, hostel leave balance, profile.
- **General university information** from a file we maintain ourselves: [backend/data/university_info.md](backend/data/university_info.md) (contacts, attendance rules, academic calendar, hostel and mess fees, health centre, placements, scholarships…). Nothing is crawled or embedded at runtime.

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
