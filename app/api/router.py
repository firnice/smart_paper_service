from fastapi import APIRouter

from app.api.routes import auth, export, health, metadata, ocr, statistics, users, variants, wrong_questions

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(ocr.router, tags=["ocr"])
api_router.include_router(variants.router, tags=["variants"])
api_router.include_router(export.router, tags=["export"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(metadata.router, tags=["metadata"])
api_router.include_router(wrong_questions.router, tags=["wrong-questions"])
api_router.include_router(statistics.router, tags=["statistics"])
