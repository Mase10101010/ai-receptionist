"""Aggregate all v1 routes under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    billing,
    chat,
    floor_plans,
    integrations,
    reservations,
    restaurants,
    service_areas,
    tables,
    webhooks,
    table_placements,
) 

from app.intelligence.router import router as intelligence_router


api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(
    table_placements.router,
)
api_router.include_router(reservations.router)
api_router.include_router(restaurants.router)
api_router.include_router(service_areas.router)
api_router.include_router(floor_plans.router)
api_router.include_router(tables.router)
api_router.include_router(billing.router)
api_router.include_router(webhooks.router)
api_router.include_router(integrations.router)
api_router.include_router(intelligence_router)
