# Kompromap — Windows Setup Guide

## Prerequisites
- Python 3.11+ (https://python.org)
- PostgreSQL 14+ (or use SQLite for testing)

## Quick Setup

### 1. Extract the zip
Extract `kompromap-final.zip` to `C:\Users\Atharva\OneDrive\Hacking\kompromap`

### 2. Backend Setup
```cmd
cd C:\Users\Atharva\OneDrive\Hacking\kompromap\kompromap\backend

# Create virtual environment
python -m venv .venv

# Activate (Command Prompt)
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy ..\.env.example .env

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

### 3. Frontend Setup (new terminal)
```cmd
cd C:\Users\Atharva\OneDrive\Hacking\kompromap\kompromap\frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## Access the App
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Database Options

### Option A: PostgreSQL (Production)
Edit `.env` and set:
```
DATABASE_URL=postgresql://user:pass@localhost/kompromap
```

### Option B: SQLite (Testing)
Edit `.env` and set:
```
DATABASE_URL=sqlite:///kompromap.db
```

## Common Issues

### "TYPE_CHECKING not defined"
Already fixed in this version.

### "Module not found"
Make sure you activated the venv: `.venv\Scripts\activate.bat`

### "Port already in use"
Change the port: `uvicorn app.main:app --reload --port 8001`
