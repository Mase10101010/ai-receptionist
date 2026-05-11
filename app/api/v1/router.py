"""Aggregate all v1 routes under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import chat, reservations

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(reservations.router)
