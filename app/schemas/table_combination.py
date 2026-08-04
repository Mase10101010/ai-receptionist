import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TableCombinationCreate(BaseModel):
    service_area_id: uuid.UUID

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    min_capacity: int = Field(
        ...,
        ge=1,
    )

    max_capacity: int = Field(
        ...,
        ge=1,
    )

    setup_minutes: int = Field(
        default=0,
        ge=0,
        le=180,
    )

    table_ids: list[uuid.UUID] = Field(
        ...,
        min_length=2,
    )

    @model_validator(mode="after")
    def validate_combination(
        self,
    ) -> "TableCombinationCreate":
        unique_table_ids = list(
            dict.fromkeys(self.table_ids),
        )

        if len(unique_table_ids) < 2:
            raise ValueError(
                "A table combination requires at least two distinct tables."
            )

        if self.min_capacity > self.max_capacity:
            raise ValueError(
                "Minimum capacity cannot exceed maximum capacity."
            )

        self.table_ids = unique_table_ids

        return self


class TableCombinationUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    min_capacity: int | None = Field(
        default=None,
        ge=1,
    )

    max_capacity: int | None = Field(
        default=None,
        ge=1,
    )

    setup_minutes: int | None = Field(
        default=None,
        ge=0,
        le=180,
    )

    table_ids: list[uuid.UUID] | None = Field(
        default=None,
        min_length=2,
    )

    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_combination(
        self,
    ) -> "TableCombinationUpdate":
        if self.table_ids is not None:
            unique_table_ids = list(
                dict.fromkeys(self.table_ids),
            )

            if len(unique_table_ids) < 2:
                raise ValueError(
                    "A table combination requires at least two distinct tables."
                )

            self.table_ids = unique_table_ids

        if (
            self.min_capacity is not None
            and self.max_capacity is not None
            and self.min_capacity > self.max_capacity
        ):
            raise ValueError(
                "Minimum capacity cannot exceed maximum capacity."
            )

        return self


class TableCombinationMemberResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    table_id: uuid.UUID
    table_number: str
    seats: int
    sort_order: int


class TableCombinationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    restaurant_id: uuid.UUID
    service_area_id: uuid.UUID
    name: str
    min_capacity: int
    max_capacity: int
    setup_minutes: int
    is_active: bool

    members: list[
        TableCombinationMemberResponse
    ]