from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    Enum as SqlEnum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TableCombinationRuleStatus(str, Enum):
    AUTO = "auto"
    CONFIRMED = "confirmed"
    BLOCKED = "blocked"

def build_table_combination_member_key(
    table_ids: list[uuid.UUID],
) -> str:
    """
    Build a deterministic identity for a physical table set.

    Member order must not affect combination identity.
    """
    unique_ids = {table_id for table_id in table_ids}

    if len(unique_ids) < 2:
        raise ValueError(
            "A table combination rule requires at least "
            "2 distinct tables"
        )

    return "|".join(
        sorted(str(table_id) for table_id in unique_ids)
    )


class TableCombinationRule(Base):
    __tablename__ = "table_combination_rules"

    __table_args__ = (
        UniqueConstraint(
            "floor_plan_id",
            "member_key",
            name="uq_table_combination_rules_floor_member_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "restaurants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "service_areas.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    floor_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "floor_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    member_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    status: Mapped[TableCombinationRuleStatus] = mapped_column(
        SqlEnum(
            TableCombinationRuleStatus,
            name="table_combination_rule_status",
            values_callable=lambda enum: [
                item.value
                for item in enum
            ],
        ),
        nullable=False,
        default=TableCombinationRuleStatus.AUTO,
        index=True,
    )

    members: Mapped[list["TableCombinationRuleMember"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="TableCombinationRuleMember.sort_order",
    )


class TableCombinationRuleMember(Base):
    __tablename__ = "table_combination_rule_members"

    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "table_id",
            name="uq_table_combination_rule_members_rule_table",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "table_combination_rules.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tables.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sort_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    rule: Mapped[TableCombinationRule] = relationship(
        back_populates="members",
    )

    table = relationship(
        "Table",
    )