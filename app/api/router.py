from fastapi import APIRouter

from app.api.routes import admin, ai_hub, analysis, auth, home, search, storage, vectors

api_router = APIRouter()
api_router.include_router(home.router)
api_router.include_router(auth.router)
api_router.include_router(search.router)
api_router.include_router(analysis.router)
api_router.include_router(storage.router)
api_router.include_router(vectors.router)
api_router.include_router(ai_hub.router)
api_router.include_router(admin.api_router)
