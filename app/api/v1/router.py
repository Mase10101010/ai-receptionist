"""Aggregate all v1 routes under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, reservations, restaurants
from app.api.v1.endpoints import (
    auth,
    chat,
    reservations,
    restaurants,
    tables,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(reservations.router)
api_router.include_router(restaurants.router)
api_router.include_router(tables.router)
