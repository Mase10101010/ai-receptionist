"""add service areas and floor plans

Revision ID: a957f39dbd63
Revises: 806250fce884
Create Date: 2026-07-23 08:23:20.531694
"""

from datetime import datetime
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a957f39dbd63"
down_revision: Union[str, None] = "806250fce884"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_areas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("restaurant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("area_type", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "restaurant_id",
            "name",
            name="uq_service_areas_restaurant_name",
        ),
    )

    op.create_index(
        "ix_service_areas_restaurant_id",
        "service_areas",
        ["restaurant_id"],
        unique=False,
    )

    op.create_table(
        "floor_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("service_area_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_area_id"],
            ["service_areas.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_area_id",
            "name",
            name="uq_floor_plans_service_area_name",
        ),
    )

    op.create_index(
        "ix_floor_plans_service_area_id",
        "floor_plans",
        ["service_area_id"],
        unique=False,
    )

    # Temporarily nullable so existing tables can be migrated safely.
    op.add_column(
        "tables",
        sa.Column(
            "floor_plan_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    restaurant_ids = connection.execute(
        sa.text("SELECT id FROM restaurants"),
    ).scalars().all()

    now = datetime.utcnow()

    for restaurant_id in restaurant_ids:
        service_area_id = uuid.uuid4()
        floor_plan_id = uuid.uuid4()

        connection.execute(
            sa.text(
                """
                INSERT INTO service_areas (
                    id,
                    restaurant_id,
                    name,
                    area_type,
                    color,
                    sort_order,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :restaurant_id,
                    :name,
                    :area_type,
                    :color,
                    :sort_order,
                    :is_active,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": service_area_id,
                "restaurant_id": restaurant_id,
                "name": "Main Dining Room",
                "area_type": "indoor",
                "color": "#7FE3E6",
                "sort_order": 0,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

        connection.execute(
            sa.text(
                """
                INSERT INTO floor_plans (
                    id,
                    service_area_id,
                    name,
                    width,
                    height,
                    sort_order,
                    is_default,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :service_area_id,
                    :name,
                    :width,
                    :height,
                    :sort_order,
                    :is_default,
                    :is_active,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": floor_plan_id,
                "service_area_id": service_area_id,
                "name": "Default Layout",
                "width": 1200,
                "height": 800,
                "sort_order": 0,
                "is_default": True,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

        connection.execute(
            sa.text(
                """
                UPDATE tables
                SET floor_plan_id = :floor_plan_id
                WHERE restaurant_id = :restaurant_id
                """
            ),
            {
                "floor_plan_id": floor_plan_id,
                "restaurant_id": restaurant_id,
            },
        )

    # Safety check: no existing table may remain without a layout.
    orphaned_tables = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tables
            WHERE floor_plan_id IS NULL
            """
        ),
    ).scalar_one()

    if orphaned_tables:
        raise RuntimeError(
            f"Migration left {orphaned_tables} table(s) "
            "without a floor plan.",
        )

    op.alter_column(
        "tables",
        "floor_plan_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.create_index(
        "ix_tables_floor_plan_id",
        "tables",
        ["floor_plan_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_tables_floor_plan_id_floor_plans",
        "tables",
        "floor_plans",
        ["floor_plan_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tables_floor_plan_id_floor_plans",
        "tables",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_tables_floor_plan_id",
        table_name="tables",
    )

    op.drop_column(
        "tables",
        "floor_plan_id",
    )

    op.drop_index(
        "ix_floor_plans_service_area_id",
        table_name="floor_plans",
    )

    op.drop_table(
        "floor_plans",
    )

    op.drop_index(
        "ix_service_areas_restaurant_id",
        table_name="service_areas",
    )

    op.drop_table(
        "service_areas",
    )