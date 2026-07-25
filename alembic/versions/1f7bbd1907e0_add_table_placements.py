"""add table placements

Revision ID: 1f7bbd1907e0
Revises: a957f39dbd63
Create Date: 2026-07-24 09:21:02.240624
"""

from datetime import datetime
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "1f7bbd1907e0"
down_revision: Union[str, None] = "a957f39dbd63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "table_placements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("floor_plan_id", sa.UUID(), nullable=False),
        sa.Column("table_id", sa.UUID(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("rotation", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["floor_plan_id"],
            ["floor_plans.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["table_id"],
            ["tables.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "floor_plan_id",
            "table_id",
            name="uq_table_placements_floor_plan_table",
        ),
    )

    op.create_index(
        "ix_table_placements_floor_plan_id",
        "table_placements",
        ["floor_plan_id"],
        unique=False,
    )

    op.create_index(
        "ix_table_placements_table_id",
        "table_placements",
        ["table_id"],
        unique=False,
    )

    # Temporarily nullable while existing tables are migrated.
    op.add_column(
        "tables",
        sa.Column(
            "service_area_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    connection = op.get_bind()
    now = datetime.utcnow()

    existing_tables = connection.execute(
        sa.text(
            """
            SELECT
                t.id,
                t.floor_plan_id,
                t.x,
                t.y,
                t.width,
                t.height,
                t.rotation,
                fp.service_area_id
            FROM tables AS t
            JOIN floor_plans AS fp
                ON fp.id = t.floor_plan_id
            """
        ),
    ).mappings().all()

    for table in existing_tables:
        connection.execute(
            sa.text(
                """
                UPDATE tables
                SET service_area_id = :service_area_id
                WHERE id = :table_id
                """
            ),
            {
                "service_area_id": table["service_area_id"],
                "table_id": table["id"],
            },
        )

        connection.execute(
            sa.text(
                """
                INSERT INTO table_placements (
                    id,
                    floor_plan_id,
                    table_id,
                    x,
                    y,
                    width,
                    height,
                    rotation,
                    is_visible,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :floor_plan_id,
                    :table_id,
                    :x,
                    :y,
                    :width,
                    :height,
                    :rotation,
                    :is_visible,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "floor_plan_id": table["floor_plan_id"],
                "table_id": table["id"],
                "x": table["x"],
                "y": table["y"],
                "width": table["width"],
                "height": table["height"],
                "rotation": table["rotation"],
                "is_visible": True,
                "created_at": now,
                "updated_at": now,
            },
        )

    orphaned_tables = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tables
            WHERE service_area_id IS NULL
            """
        ),
    ).scalar_one()

    if orphaned_tables:
        raise RuntimeError(
            f"Migration left {orphaned_tables} table(s) "
            "without a service area.",
        )

    missing_placements = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tables AS t
            LEFT JOIN table_placements AS tp
                ON tp.table_id = t.id
                AND tp.floor_plan_id = t.floor_plan_id
            WHERE tp.id IS NULL
            """
        ),
    ).scalar_one()

    if missing_placements:
        raise RuntimeError(
            f"Migration left {missing_placements} table(s) "
            "without a placement.",
        )

    op.alter_column(
        "tables",
        "service_area_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.create_index(
        "ix_tables_service_area_id",
        "tables",
        ["service_area_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_tables_service_area_id_service_areas",
        "tables",
        "service_areas",
        ["service_area_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tables_service_area_id_service_areas",
        "tables",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_tables_service_area_id",
        table_name="tables",
    )

    op.drop_column(
        "tables",
        "service_area_id",
    )

    op.drop_index(
        "ix_table_placements_table_id",
        table_name="table_placements",
    )

    op.drop_index(
        "ix_table_placements_floor_plan_id",
        table_name="table_placements",
    )

    op.drop_table(
        "table_placements",
    )
