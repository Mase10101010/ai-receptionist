"""Aggregate all v1 routes under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    billing,
    chat,
    integrations,
    reservations,
    restaurants,
    tables,
) 
from app.api.v1.endpoints import (
    auth,
    chat,
    reservations,
    restaurants,
    tables,
)

from app.api.v1.endpoints import webhooks

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(reservations.router)
api_router.include_router(restaurants.router)
api_router.include_router(tables.router)
api_router.include_router(billing.router)
api_router.include_router(webhooks.router)
api_router.include_router(integrations.router)
