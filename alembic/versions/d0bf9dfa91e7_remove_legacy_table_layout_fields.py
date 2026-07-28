"""remove legacy table layout fields

Revision ID: d0bf9dfa91e7
Revises: 1f7bbd1907e0
Create Date: 2026-07-28 10:31:09.084205
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0bf9dfa91e7"
down_revision: Union[str, None] = "1f7bbd1907e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    tables_without_placement = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tables AS t
            LEFT JOIN table_placements AS tp
                ON tp.table_id = t.id
            WHERE tp.id IS NULL
            """
        )
    ).scalar_one()

    if tables_without_placement:
        raise RuntimeError(
            f"Cannot remove legacy layout fields: "
            f"{tables_without_placement} table(s) "
            "have no placement."
        )

    op.drop_constraint(
        "fk_tables_floor_plan_id_floor_plans",
        "tables",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_tables_floor_plan_id",
        table_name="tables",
    )

    op.drop_column("tables", "rotation")
    op.drop_column("tables", "height")
    op.drop_column("tables", "width")
    op.drop_column("tables", "y")
    op.drop_column("tables", "x")
    op.drop_column("tables", "floor_plan_id")


def downgrade() -> None:
    op.add_column(
        "tables",
        sa.Column(
            "floor_plan_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.add_column(
        "tables",
        sa.Column(
            "x",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tables",
        sa.Column(
            "y",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tables",
        sa.Column(
            "width",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tables",
        sa.Column(
            "height",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tables",
        sa.Column(
            "rotation",
            sa.Integer(),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE tables AS t
            SET
                floor_plan_id = source.floor_plan_id,
                x = source.x,
                y = source.y,
                width = source.width,
                height = source.height,
                rotation = source.rotation
            FROM (
                SELECT DISTINCT ON (tp.table_id)
                    tp.table_id,
                    tp.floor_plan_id,
                    tp.x,
                    tp.y,
                    tp.width,
                    tp.height,
                    tp.rotation
                FROM table_placements AS tp
                JOIN floor_plans AS fp
                    ON fp.id = tp.floor_plan_id
                ORDER BY
                    tp.table_id,
                    fp.is_default DESC,
                    fp.sort_order ASC,
                    tp.created_at ASC
            ) AS source
            WHERE t.id = source.table_id
            """
        )
    )

    missing_legacy_values = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tables
            WHERE
                floor_plan_id IS NULL
                OR x IS NULL
                OR y IS NULL
                OR width IS NULL
                OR height IS NULL
                OR rotation IS NULL
            """
        )
    ).scalar_one()

    if missing_legacy_values:
        raise RuntimeError(
            f"Cannot restore legacy layout fields: "
            f"{missing_legacy_values} table(s) "
            "have no usable placement."
        )

    op.alter_column(
        "tables",
        "floor_plan_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.alter_column(
        "tables",
        "x",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "tables",
        "y",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "tables",
        "width",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "tables",
        "height",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "tables",
        "rotation",
        existing_type=sa.Integer(),
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
