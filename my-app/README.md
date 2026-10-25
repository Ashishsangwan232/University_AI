# CampusAI Frontend

React + TypeScript + Vite frontend for CampusAI.

## UMS

UMS no longer uses a browser extension or bridge. The frontend starts a Playwright-managed dedicated browser through the backend.

Use **Profile & Settings → Student portal → Connect UMS**. CampusAI opens a dedicated Chrome window. Enter UMS credentials and complete Cloudflare/OTP manually. Playwright then detects the authenticated session and captures attendance.

The frontend never receives or stores UMS credentials.

## Run

```powershell
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if FastAPI is not running on `http://127.0.0.1:8000`.
