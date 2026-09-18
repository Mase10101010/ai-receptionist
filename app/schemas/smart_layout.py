from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.table_combination_rule import TableCombinationRuleStatus


class SmartLayoutAnalysisResponse(BaseModel):
    discovered_count: int
    created_auto_count: int
    preserved_auto_count: int
    preserved_confirmed_count: int
    preserved_blocked_count: int
    deleted_obsolete_auto_count: int


class SmartLayoutRuleMemberResponse(BaseModel):
    table_id: uuid.UUID
    sort_order: int


class SmartLayoutRuleResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    service_area_id: uuid.UUID
    floor_plan_id: uuid.UUID
    member_key: str
    status: TableCombinationRuleStatus
    members: list[SmartLayoutRuleMemberResponse]

class SmartLayoutRuleStatusUpdate(BaseModel):
    status: TableCombinationRuleStatus