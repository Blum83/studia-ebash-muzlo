@echo off
rem One-click start on Windows: build UI, install deps, fetch models on first run, serve.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

where uv >nul 2>&1 || (echo [x] uv not found: https://docs.astral.sh/uv/ & exit /b 1)
where npm >nul 2>&1 || (echo [x] Node.js/npm not found: https://nodejs.org & exit /b 1)
where ffmpeg >nul 2>&1 || (echo [x] ffmpeg not found on PATH: winget install Gyan.FFmpeg & exit /b 1)

if not exist third_party\ACE-Step-1.5\pyproject.toml git submodule update --init || exit /b 1
if not exist .env copy .env.example .env >nul

pushd frontend
if not exist node_modules (call npm install || exit /b 1)
call npm run build || exit /b 1
popd

pushd backend
uv sync || exit /b 1
if not exist ..\models\acestep-v15-turbo (uv run songgen download || exit /b 1)
rem Open the UI once the server is listening (the model keeps loading in the background).
start "" /b cmd /c "ping -n 9 127.0.0.1 >nul & start http://127.0.0.1:8000"
uv run songgen serve
