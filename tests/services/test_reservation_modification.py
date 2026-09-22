from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.reservation import ReservationUpdate
from app.services.reservation_service import ReservationService

def _build_service(*, reservation):
    repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=reservation),
        update=AsyncMock(return_value=reservation),
        replace_table_assignments=AsyncMock(return_value=reservation),
        db=SimpleNamespace(),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    # LAB-008 tests are about modification availability/assignment authority,
    # not intelligence-event or temporal lifecycle side effects.
    service._record_reservation_event = AsyncMock()
    service._expire_pending_ai_suggestions = AsyncMock()
    service._try_record_temporal_outcome = AsyncMock()

    return service, repository


@pytest.mark.asyncio
async def test_capacity_affecting_modification_uses_aie_and_reassigns_tables():
    reservation_id = uuid4()
    restaurant_id = uuid4()
    old_table_id = uuid4()
    new_table_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        reservation_time=datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        party_size=4,
        duration_minutes=90,
        table_id=old_table_id,
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._assign_tables_with_aie = AsyncMock(
        return_value=(new_table_id, [new_table_id]),
    )

    service._enforce_capacity = AsyncMock()

    payload = ReservationUpdate(
        party_size=6,
    )

    await service.update_reservation(
        reservation_id=reservation_id,
        payload=payload,
    )

    service._assign_tables_with_aie.assert_awaited_once()

    aie_call = service._assign_tables_with_aie.await_args

    assert aie_call.kwargs["reservation_id"] == reservation_id
    assert aie_call.kwargs["party_size"] == 6

    service._enforce_capacity.assert_not_awaited()

    repository.replace_table_assignments.assert_awaited_once_with(
        reservation,
        [new_table_id],
        primary_table_id=new_table_id,
    )


@pytest.mark.asyncio
async def test_metadata_only_modification_does_not_run_aie():
    reservation_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=uuid4(),
        reservation_time=datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        party_size=4,
        duration_minutes=90,
        table_id=uuid4(),
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._assign_tables_with_aie = AsyncMock()
    service._enforce_capacity = AsyncMock()

    payload = ReservationUpdate(
        special_requests="Window seat if possible",
    )

    await service.update_reservation(
        reservation_id=reservation_id,
        payload=payload,
    )

    service._assign_tables_with_aie.assert_not_awaited()
    service._enforce_capacity.assert_not_awaited()

    repository.update.assert_awaited_once()
    repository.replace_table_assignments.assert_not_awaited()

@pytest.mark.asyncio
async def test_capacity_affecting_modification_persists_multi_table_assignment():
    reservation_id = uuid4()
    table_a = uuid4()
    table_b = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=uuid4(),
        reservation_time=datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        party_size=4,
        duration_minutes=90,
        table_id=uuid4(),
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._assign_tables_with_aie = AsyncMock(
        return_value=(
            table_a,
            [table_a, table_b],
        ),
    )

    payload = ReservationUpdate(
        party_size=10,
    )

    await service.update_reservation(
        reservation_id=reservation_id,
        payload=payload,
    )

    repository.replace_table_assignments.assert_awaited_once_with(
        reservation,
        [table_a, table_b],
        primary_table_id=table_a,
    )


@pytest.mark.asyncio
async def test_unavailable_modification_leaves_original_reservation_untouched():
    reservation_id = uuid4()
    old_table_id = uuid4()

    original_time = datetime(
        2026,
        9,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=uuid4(),
        reservation_time=original_time,
        party_size=4,
        duration_minutes=90,
        table_id=old_table_id,
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._assign_tables_with_aie = AsyncMock(
        return_value=(None, []),
    )

    payload = ReservationUpdate(
        party_size=6,
    )

    with pytest.raises(Exception):
        await service.update_reservation(
            reservation_id=reservation_id,
            payload=payload,
        )

    service._assign_tables_with_aie.assert_awaited_once()

    repository.update.assert_not_awaited()
    repository.replace_table_assignments.assert_not_awaited()

    assert reservation.party_size == 4
    assert reservation.reservation_time == original_time
    assert reservation.table_id == old_table_id


@pytest.mark.asyncio
async def test_time_modification_passes_current_reservation_id_to_aie():
    reservation_id = uuid4()
    new_table_id = uuid4()

    original_time = datetime(
        2026,
        9,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    new_time = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=uuid4(),
        reservation_time=original_time,
        party_size=4,
        duration_minutes=90,
        table_id=uuid4(),
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._validate_reservation_time = AsyncMock()

    service._assign_tables_with_aie = AsyncMock(
        return_value=(
            new_table_id,
            [new_table_id],
        ),
    )

    payload = ReservationUpdate(
        reservation_time=new_time,
    )

    await service.update_reservation(
        reservation_id=reservation_id,
        payload=payload,
    )

    service._validate_reservation_time.assert_awaited_once_with(
        new_time,
        reservation.restaurant_id,
    )

    service._assign_tables_with_aie.assert_awaited_once()

    aie_call = service._assign_tables_with_aie.await_args

    assert aie_call.kwargs["reservation_id"] == reservation_id
    assert aie_call.kwargs["reservation_time"] == new_time
    assert aie_call.kwargs["party_size"] == 4

    repository.replace_table_assignments.assert_awaited_once_with(
        reservation,
        [new_table_id],
        primary_table_id=new_table_id,
    )

@pytest.mark.asyncio
async def test_modification_availability_passes_current_reservation_id_to_aie():
    reservation_id = uuid4()
    restaurant_id = uuid4()
    table_id = uuid4()

    intelligence_service = SimpleNamespace(
        optimize=AsyncMock(
            return_value=SimpleNamespace(
                available=True,
                recommended=SimpleNamespace(
                    table_ids=[table_id],
                ),
            )
        )
    )

    repository = SimpleNamespace(
        db=SimpleNamespace(),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=intelligence_service,
    )

    service._validate_reservation_time = AsyncMock()

    reservation_time = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    available = await service.check_availability(
        reservation_time=reservation_time,
        party_size=6,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    assert available is True

    intelligence_service.optimize.assert_awaited_once()

    request = intelligence_service.optimize.await_args.kwargs["payload"]

    assert request.restaurant_id == restaurant_id
    assert request.reservation_id == reservation_id
    assert request.requested_start == reservation_time
    assert request.party_size == 6


@pytest.mark.asyncio
async def test_modification_alternative_slots_preserve_reservation_id():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    service = ReservationService(
        repository=SimpleNamespace(),
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    service.check_availability = AsyncMock(
        side_effect=[
            False,
            False,
            False,
            True,
            True,
            True,
        ]
    )

    reservation_time = datetime(
        2026,
        9,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    slots = await service.suggest_alternative_slots(
        reservation_time=reservation_time,
        party_size=6,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    assert len(slots) == 3

    for call in service.check_availability.await_args_list:
        assert call.kwargs["reservation_id"] == reservation_id
        assert call.kwargs["restaurant_id"] == restaurant_id
        assert call.kwargs["party_size"] == 6

@pytest.mark.asyncio
async def test_modification_does_not_legacy_fallback_after_valid_aie_unavailable():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        reservation_time=datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        party_size=4,
        duration_minutes=90,
        table_id=uuid4(),
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service.intelligence_service = SimpleNamespace(
        optimize=AsyncMock(
            return_value=SimpleNamespace(
                available=False,
                recommended=None,
            )
        )
    )

    service._assign_available_table = AsyncMock(
        return_value=uuid4(),
    )

    payload = ReservationUpdate(
        party_size=6,
    )

    with pytest.raises(Exception):
        await service.update_reservation(
            reservation_id=reservation_id,
            payload=payload,
        )

    service.intelligence_service.optimize.assert_awaited_once()

    request = (
        service.intelligence_service.optimize
        .await_args.kwargs["payload"]
    )

    assert request.reservation_id == reservation_id

    # A valid AIE "unavailable" result is authoritative.
    # Legacy allocation must not contradict it.
    service._assign_available_table.assert_not_awaited()

    repository.update.assert_not_awaited()
    repository.replace_table_assignments.assert_not_awaited()

@pytest.mark.asyncio
async def test_modification_uses_legacy_fallback_when_aie_raises():
    reservation_id = uuid4()
    restaurant_id = uuid4()
    fallback_table_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        reservation_time=datetime(
            2026,
            9,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        party_size=4,
        duration_minutes=90,
        table_id=uuid4(),
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service.intelligence_service = SimpleNamespace(
        optimize=AsyncMock(
            side_effect=RuntimeError("AIE unavailable"),
        )
    )

    service._assign_available_table = AsyncMock(
        return_value=fallback_table_id,
    )

    payload = ReservationUpdate(
        party_size=6,
    )

    await service.update_reservation(
        reservation_id=reservation_id,
        payload=payload,
    )

    service.intelligence_service.optimize.assert_awaited_once()

    request = (
        service.intelligence_service.optimize
        .await_args.kwargs["payload"]
    )

    assert request.reservation_id == reservation_id

    service._assign_available_table.assert_awaited_once()

    repository.replace_table_assignments.assert_awaited_once_with(
        reservation,
        [fallback_table_id],
        primary_table_id=fallback_table_id,
    )

@pytest.mark.asyncio
async def test_accepted_alternative_is_revalidated_and_lost_slot_leaves_original_untouched():
    reservation_id = uuid4()
    old_table_id = uuid4()

    original_time = datetime(
        2026,
        9,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    accepted_alternative = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=uuid4(),
        reservation_time=original_time,
        party_size=6,
        duration_minutes=90,
        table_id=old_table_id,
        status=SimpleNamespace(value="confirmed"),
    )

    service, repository = _build_service(
        reservation=reservation,
    )

    service._validate_reservation_time = AsyncMock()

    # The alternative may have been available when it was offered,
    # but by the time the guest accepts it another reservation has
    # consumed the capacity. update_reservation must revalidate.
    service._assign_tables_with_aie = AsyncMock(
        return_value=(None, []),
    )

    payload = ReservationUpdate(
        reservation_time=accepted_alternative,
    )

    with pytest.raises(Exception):
        await service.update_reservation(
            reservation_id=reservation_id,
            payload=payload,
        )

    service._validate_reservation_time.assert_awaited_once_with(
        accepted_alternative,
        reservation.restaurant_id,
    )

    service._assign_tables_with_aie.assert_awaited_once()

    aie_call = service._assign_tables_with_aie.await_args

    assert aie_call.kwargs["reservation_id"] == reservation_id
    assert aie_call.kwargs["reservation_time"] == accepted_alternative
    assert aie_call.kwargs["party_size"] == 6

    repository.update.assert_not_awaited()
    repository.replace_table_assignments.assert_not_awaited()

    assert reservation.reservation_time == original_time
    assert reservation.party_size == 6
    assert reservation.table_id == old_table_id