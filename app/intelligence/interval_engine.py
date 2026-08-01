from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from .types import ExistingReservation


ACTIVE_RESERVATION_STATUSES = {
    "confirmed",
    "seated",
    "arrived",
    "pending",
}


def intervals_overlap(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    """Half-open interval overlap: [start, end). Back-to-back bookings are valid."""
    return first_start < second_end and second_start < first_end


def reservation_blocks_tables(
    reservation: ExistingReservation,
    candidate_table_ids: set[str],
    candidate_start: datetime,
    candidate_end: datetime,
) -> bool:
    if reservation.status.lower() not in ACTIVE_RESERVATION_STATUSES:
        return False

    if not candidate_table_ids.intersection(reservation.table_ids):
        return False

    return intervals_overlap(
        reservation.start_at,
        reservation.end_at,
        candidate_start,
        candidate_end,
    )


def is_assignment_available(
    table_ids: tuple[str, ...],
    start_at: datetime,
    end_at: datetime,
    reservations: Iterable[ExistingReservation],
    buffer_before_minutes: int = 0,
    buffer_after_minutes: int = 0,
    setup_minutes: int = 0,
) -> bool:
    blocked_start = start_at - timedelta(
        minutes=buffer_before_minutes + setup_minutes,
    )
    blocked_end = end_at + timedelta(minutes=buffer_after_minutes)
    candidate_table_ids = set(table_ids)

    return not any(
        reservation_blocks_tables(
            reservation=reservation,
            candidate_table_ids=candidate_table_ids,
            candidate_start=blocked_start,
            candidate_end=blocked_end,
        )
        for reservation in reservations
    )


def calculate_fragmentation_minutes(
    table_ids: tuple[str, ...],
    start_at: datetime,
    end_at: datetime,
    reservations: Iterable[ExistingReservation],
    useful_gap_threshold_minutes: int,
) -> int:
    """Penalise small unusable gaps immediately before or after an assignment."""
    relevant = [
        reservation
        for reservation in reservations
        if set(table_ids).intersection(reservation.table_ids)
        and reservation.status.lower() in ACTIVE_RESERVATION_STATUSES
    ]

    previous_end: datetime | None = None
    next_start: datetime | None = None

    for reservation in relevant:
        if reservation.end_at <= start_at:
            if previous_end is None or reservation.end_at > previous_end:
                previous_end = reservation.end_at

        if reservation.start_at >= end_at:
            if next_start is None or reservation.start_at < next_start:
                next_start = reservation.start_at

    fragmentation = 0

    if previous_end is not None:
        gap = int((start_at - previous_end).total_seconds() // 60)
        if 0 < gap < useful_gap_threshold_minutes:
            fragmentation += gap

    if next_start is not None:
        gap = int((next_start - end_at).total_seconds() // 60)
        if 0 < gap < useful_gap_threshold_minutes:
            fragmentation += gap

    return fragmentation
