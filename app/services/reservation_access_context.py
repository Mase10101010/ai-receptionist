"""Server-verified authorization context for customer reservation access."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReservationAccessContext:
    """A reservation scope established by server-side token verification."""

    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID

    def allows(
        self,
        restaurant_id: uuid.UUID | None,
        reservation_id: uuid.UUID,
    ) -> bool:
        return (
            restaurant_id is not None
            and self.restaurant_id == restaurant_id
            and self.reservation_id == reservation_id
        )
