@echo off
setlocal
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo Google Chrome was not found.
  pause
  exit /b 1
)
set "PROFILE=%~dp0..\data\ums\playwright-chrome-profile"
if not exist "%PROFILE%" mkdir "%PROFILE%"
start "CampusAI UMS Chrome" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "https://ums.lpu.in/lpuums/"
echo CampusAI Chrome started on CDP port 9222.
echo Complete UMS/Cloudflare login manually. CampusAI Playwright will attach to this browser.
