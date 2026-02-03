from fastapi import APIRouter

from app.api.routes import export, health, ocr, variants

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(ocr.router, tags=["ocr"])
api_router.include_router(variants.router, tags=["variants"])
api_router.include_router(export.router, tags=["export"])
