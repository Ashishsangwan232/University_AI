# CampusAI Backend — Playwright-only UMS

FastAPI + PostgreSQL + Gemini + local RAG + Playwright-controlled UMS automation.

## UMS architecture

The UMS browser extension/bridge has been removed.

CampusAI uses one dedicated, visible Chrome/Edge profile. The student manually completes UMS login, Cloudflare/human verification, and OTP when required. Playwright then attaches to that same browser through Chrome DevTools Protocol and performs UMS navigation/extraction.

```text
CampusAI FastAPI
      |
      | starts dedicated Chrome with a separate profile
      v
Real Chrome / Edge
      |
      | student manually logs in + completes verification
      v
Authenticated UMS
      |
      | Playwright CDP attachment
      v
UMS Playwright service
      |
      +--> attendance
      +--> timetable/navigation helpers
      +--> announcements/page extraction helpers
      +--> future leave form automation
```

No extension, content script, bridge token, heartbeat, snapshot API, or credential forwarding is used.

### Why a dedicated profile?

Chrome 136+ requires remote debugging to use a non-default user-data directory. Playwright also recommends a separate automation profile rather than the user's normal Chrome profile. The default profile is therefore never touched.

The profile is stored at:

```text
data/ums/playwright-chrome-profile/
```

This directory is local-only and must not be committed.

## Run

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Set `GEMINI_API_KEY` in `.env`. Never commit `.env`.

## UMS workflow

1. Start FastAPI.
2. From CampusAI click **Connect UMS**, or call `POST /api/ums/session/start`.
3. CampusAI opens a dedicated visible Chrome window at UMS.
4. Manually enter the UMS username/password.
5. Manually complete Cloudflare/human verification and OTP if shown.
6. Once Student Dashboard is reached, Playwright detects the authenticated session.
7. Playwright locates Attendance/Attendance Summary and extracts the table automatically.
8. `/api/attendance` and Gemini attendance tools use the live Playwright result.
9. The same browser session remains available for later UMS actions.

### Useful endpoints

- `POST /api/ums/session/start` — open/connect the dedicated UMS browser.
- `GET /api/ums/session/status` — current browser/login/attendance state.
- `POST /api/ums/session/refresh` — force another attendance extraction attempt.
- `POST /api/ums/session/navigate` with `{"target":"attendance"}` — ask Playwright to navigate/extract attendance.
- `POST /api/ums/session/stop` — close the dedicated browser session.
- `GET /api/ums/attendance` — current live UMS attendance.
- `GET /api/ums/attendance/status` — diagnostic status.

## Security

CampusAI does not collect or send UMS username/password to Gemini. The student enters credentials directly into the dedicated browser. Cloudflare/human verification is always completed by the student. Authentication state remains inside the local browser profile.

Do not copy the browser profile into GitHub or share it: it contains authenticated browser state.

## RAG

PostgreSQL stores structured campus data. `data/rag/chunks.json` stores college website chunks and local Ollama `embeddinggemma` embeddings. No Docker or pgvector is required.

```powershell
ollama pull embeddinggemma
```

## Gemini

Gemini 2.5 Flash is the primary agent. If Gemini is unavailable because of quota, key, network, or provider errors, the local deterministic agent still handles supported tool-backed requests such as live UMS attendance, timetable, announcements, services, and attendance calculations.
