from fastapi import APIRouter

from app.api.routes import analysis, search

api_router = APIRouter()
api_router.include_router(search.router)
api_router.include_router(analysis.router)
