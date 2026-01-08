---
description: Start the Open WebUI development servers (frontend on port 5173, backend on port 8080)
allowed-tools: Bash, BashOutput, Read
---

# Start Development Servers

Start both frontend and backend development servers for Open WebUI.

## Instructions

1. **Check if servers are already running** by checking ports 5173 and 8080

2. **Start Frontend** (if not running):
   ```bash
   npm install --legacy-peer-deps  # Only if node_modules doesn't exist
   npm run dev
   ```
   - Runs on http://localhost:5173
   - Run in background

3. **Start Backend** (if not running):
   - Uses virtual environment at `backend/venv`
   - Uses batch script `backend/start-dev.bat` which sets UTF-8 encoding (required on Windows)
   ```bash
   backend/start-dev.bat
   ```
   - Runs on http://localhost:8080
   - API docs at http://localhost:8080/docs
   - Run in background

   **Note**: The batch script sets `PYTHONUTF8=1` and `chcp 65001` to handle Unicode characters in console output (Windows-specific issue).

4. **Report Status**:
   - Frontend URL: http://localhost:5173
   - Backend API: http://localhost:8080
   - API Docs: http://localhost:8080/docs

## First-Time Setup

If `backend/venv` doesn't exist:
```bash
# Create virtual environment
python -m venv backend/venv

# Install dependencies
backend/venv/Scripts/pip.exe install -r backend/requirements.txt
```

## Prerequisites

- Node.js 18-22
- Python 3.11+
- Virtual environment at `backend/venv` with dependencies installed

## Notes

- Frontend takes ~1-2 minutes on first run to download Pyodide packages
- Backend will download the embedding model (~90MB) on first run
- Both servers support hot-reload for development
- Virtual environment is at `backend/venv` (gitignored)
- The `backend/start-dev.bat` script handles Windows UTF-8 encoding issues
