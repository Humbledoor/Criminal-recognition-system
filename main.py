"""
Criminal Face Recognition & Record Management System
FastAPI application entry point.
"""
import os
import sys

# Fix Windows console encoding BEFORE any library imports
# TensorFlow/DeepFace print Unicode characters that crash cp1252 console
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database.database import init_db
from routes.auth_routes import router as auth_router
from routes.person_routes import router as person_router
from routes.record_routes import router as record_router
from routes.search_routes import router as search_router
from routes.audit_routes import router as audit_router
from routes.dashboard_routes import router as dashboard_router
from routes.export_routes import router as export_router

app = FastAPI(
    title="Criminal Recognition System",
    description="AI-Powered Criminal Face Recognition & Record Management",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth_router)
app.include_router(person_router)
app.include_router(record_router)
app.include_router(search_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(export_router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
data_dir = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(data_dir, "uploads"), exist_ok=True)

app.mount("/data", StaticFiles(directory=data_dir), name="data")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.on_event("startup")
def startup():
    init_db()
    print("[OK] Criminal Recognition System started")
    print("[DB] Database initialized with sample data")
    print("[AUTH] Officer credentials:")
    print("       officer_rakesh / Rakesh@001  (Admin)")
    print("       officer_priya  / Priya@002   (Investigator)")
    print("       officer_arjun  / Arjun@003   (Viewer)")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
