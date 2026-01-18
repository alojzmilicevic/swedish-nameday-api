#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

# Open browser after a short delay
(sleep 2 && open http://localhost:8000/docs) &

uvicorn main:app --reload --port 8000
