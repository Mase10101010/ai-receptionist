from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.services.ai_service import _build_system_prompt


@pytest.mark.parametrize(
    ("timezone_name", "expected_date"),
    [
        ("Australia/Perth", "Saturday, October 17, 2026"),
        ("America/Los_Angeles", "Friday, October 16, 2026"),
    ],
)
def test_system_prompt_uses_restaurant_local_date(
    timezone_name,
    expected_date,
):
    fixed_utc = datetime(2026, 10, 16, 18, 30, tzinfo=timezone.utc)

    with patch("app.services.ai_service.datetime") as mocked_datetime:
        mocked_datetime.now.side_effect = (
            lambda tz=None: fixed_utc.astimezone(tz)
            if tz is not None
            else fixed_utc.replace(tzinfo=None)
        )
        mocked_datetime.utcnow.return_value = fixed_utc.replace(tzinfo=None)

        prompt = _build_system_prompt(
            restaurant_name="Alias Test Restaurant",
            timezone_name=timezone_name,
            opening_hour=12,
            closing_hour=23,
        )

    assert f"Today is {expected_date}" in prompt
    assert f"Timezone: {timezone_name}" in prompt
