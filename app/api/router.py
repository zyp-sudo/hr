from fastapi import APIRouter

from app.api.routes import admin, analysis, search, storage, vectors

api_router = APIRouter()
api_router.include_router(search.router)
api_router.include_router(analysis.router)
api_router.include_router(storage.router)
api_router.include_router(vectors.router)
api_router.include_router(admin.api_router)
