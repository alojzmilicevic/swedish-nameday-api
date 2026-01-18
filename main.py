from fastapi import FastAPI, HTTPException, Header
from datetime import datetime
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from fetch import fetch_html, parse_tables

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Upstash Redis (via Vercel Marketplace)
kv = None
if os.environ.get("KV_REST_API_URL"):
    from upstash_redis import Redis
    kv = Redis(
        url=os.environ["KV_REST_API_URL"],
        token=os.environ["KV_REST_API_TOKEN"]
    )

app = FastAPI(
    title="Swedish Nameday API",
    description="API for Swedish namedays (namnsdagar)",
    version="1.0.0"
)

JSON_PATH = BASE_DIR / "svenska_namnsdagar.json"
API_KEY = os.environ.get("NAMEDAY_API_KEY", "")
KV_KEY = "namedays"


def load_namedays():
    """Load nameday data from KV store, fallback to JSON file"""
    # Try KV first (on Vercel)
    if kv:
        data = kv.get(KV_KEY)
        if data:
            return data if isinstance(data, dict) else json.loads(data)
    
    # Fallback to JSON file
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def verify_api_key(x_api_key: str = Header(None)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured on server")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


NAMEDAYS = load_namedays()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Swedish Nameday API",
        "version": "1.0.0",
        "description": "API for Swedish namedays (namnsdagar)",
        "endpoints": {
            "today": "/api/today",
            "date": "/api/date/{month}/{day}",
            "name": "/api/name/{name}",
            "month": "/api/month/{month}",
            "all": "/api/all"
        }
    }

@app.get("/api/today")
async def get_today():
    """Get today's namedays"""
    today = datetime.now()
    month = today.month
    day = today.day
    
    date_key = f"{month:02d}-{day:02d}"
    names = NAMEDAYS.get(date_key, [])
    
    return {
        "date": f"{month:02d}-{day:02d}",
        "names": names,
        "count": len(names)
    }

@app.get("/api/date/{month}/{day}")
async def get_date(month: int, day: int):
    """Get namedays for a specific date"""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    if day < 1 or day > 31:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 31")
    
    # Basic date validation
    try:
        datetime(2000, month, day)  # Use 2000 as a non-leap year for validation
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")
    
    date_key = f"{month:02d}-{day:02d}"
    names = NAMEDAYS.get(date_key, [])
    
    return {
        "date": date_key,
        "names": names,
        "count": len(names)
    }

@app.get("/api/name/{name}")
async def get_name(name: str):
    """Find dates for a specific name"""
    name_lower = name.lower()
    results = []
    
    for date_key, names in NAMEDAYS.items():
        for n in names:
            if n.lower() == name_lower:
                results.append({
                    "date": date_key,
                    "name": n
                })
                break
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Name '{name}' not found in nameday calendar")
    
    return {
        "name": name,
        "dates": results,
        "count": len(results)
    }

@app.get("/api/month/{month}")
async def get_month(month: int):
    """Get all namedays for a specific month"""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    month_namedays = {}
    for date_key, names in NAMEDAYS.items():
        if date_key.startswith(f"{month:02d}-"):
            month_namedays[date_key] = names
    
    return {
        "month": month,
        "namedays": month_namedays,
        "count": len(month_namedays)
    }

@app.get("/api/all")
async def get_all():
    """Get all namedays"""
    return {
        "namedays": NAMEDAYS,
        "total_dates": len(NAMEDAYS),
        "total_names": sum(len(names) for names in NAMEDAYS.values())
    }


@app.post("/api/refresh")
async def refresh_namedays(x_api_key: str = Header()):
    """Refresh nameday data from Wikipedia (requires API key)"""
    global NAMEDAYS
    verify_api_key(x_api_key)
    
    html = fetch_html()
    data = parse_tables(html)
    if not data:
        raise HTTPException(status_code=500, detail="Failed to fetch data from Wikipedia")
    
    # Save to KV if available (Vercel), otherwise to file
    if kv:
        kv.set(KV_KEY, json.dumps(data, ensure_ascii=False))
    else:
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    NAMEDAYS = data
    return {
        "status": "success",
        "total_dates": len(NAMEDAYS),
        "total_names": sum(len(names) for names in NAMEDAYS.values())
    }
