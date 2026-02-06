from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount static files for serving uploaded images and exports
storage_dir = Path(settings.storage_base_dir)
storage_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(storage_dir)), name="static")


@app.get("/")
def read_root():
    return {"name": "Smart Paper Service", "status": "ready"}
