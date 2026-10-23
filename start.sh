#!/bin/bash
# AeroFleet - one command: sets up what is missing, starts the API and the app, opens the browser.
#   ./start.sh            API on :8000, app on http://localhost:1420
#   ./start.sh api        API only
# Ctrl-C stops both.
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "Creating the Python environment (.venv)..."
  "$PYTHON" -m venv .venv
fi
source .venv/bin/activate

# Install only when requirements.txt changed since the last install.
if [ ! -f .venv/.req-installed ] || [ requirements.txt -nt .venv/.req-installed ]; then
  echo "Installing Python dependencies (first run takes a few minutes)..."
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  touch .venv/.req-installed
fi

export DATABASE_URL="${DATABASE_URL:-sqlite:///./aerofleet.db}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
mkdir -p data logs

# 0.0.0.0 so a Quest headset on the same network can reach the API (docs/VR_QUEST3_GUIDE.md).
python -m uvicorn aerofleet.api.app:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
trap 'echo; echo "Stopping..."; kill $API_PID $APP_PID 2>/dev/null; exit 0' INT TERM

echo -n "Starting the API (first start takes a minute or two)"
until curl -s -o /dev/null http://127.0.0.1:8000/docs; do
  if ! kill -0 $API_PID 2>/dev/null; then echo; echo "The API stopped. Last lines of logs/api.log:"; tail -20 logs/api.log; exit 1; fi
  echo -n "."; sleep 2
done
echo " ready: http://localhost:8000/docs"

if [ "$1" = "api" ]; then
  wait $API_PID
  exit 0
fi

if [ ! -d tauri-app/node_modules ]; then
  echo "Installing the app's packages..."
  npm install --prefix tauri-app --silent
fi
npm run dev --prefix tauri-app > logs/app.log 2>&1 &
APP_PID=$!
until curl -s -o /dev/null http://localhost:1420; do      # vite listens on localhost, IPv6 on macOS
  if ! kill -0 $APP_PID 2>/dev/null; then echo "The app stopped. Last lines of logs/app.log:"; tail -20 logs/app.log; kill $API_PID; exit 1; fi
  sleep 1
done
echo "App ready: http://localhost:1420  (sign in, then open Fleet Assurance)"
command -v open >/dev/null && open http://localhost:1420 || true
echo "Ctrl-C to stop. Logs: logs/api.log, logs/app.log"
wait
