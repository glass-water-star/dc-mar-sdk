import os
from pathlib import Path

import pytest

from dc_mar_sdk.tools.drift_detector import SwaggerValidator


@pytest.mark.asyncio
async def test_live_drift_smoke_covers_all_operations_without_drift() -> None:
    """
    Optional live smoke test covering every documented MAR operation.

    Enabled only when:
    - DC_RUN_SMOKE_TESTS=1
    - DC_MAR_API_KEY is set
    """
    if os.getenv("DC_RUN_SMOKE_TESTS") != "1":
        pytest.skip("Set DC_RUN_SMOKE_TESTS=1 to run live smoke tests.")

    api_key = os.getenv("DC_MAR_API_KEY")
    if not api_key:
        pytest.skip("Set DC_MAR_API_KEY for live smoke test.")

    swagger_file = os.getenv(
        "DC_SWAGGER_FILE",
        str(Path(__file__).resolve().parents[1] / "swagger" / "swagger.json"),
    )

    validator = SwaggerValidator(swagger_file, api_key)

    allowed, disallowed, robots_error = await validator.check_robots_txt(
        user_agent="dc_mar_sdk-pytest-smoke",
        include_unsafe_methods=True,
    )
    assert robots_error is None, robots_error
    assert allowed, f"robots.txt disallowed operations: {disallowed[:10]}"

    results = await validator.test_all(
        user_agent="dc_mar_sdk-pytest-smoke",
        include_unsafe_methods=True,
    )
    assert len(results) == 33
    critical_errors = sum(1 for r in results for i in r.issues if i.severity == "error")
    assert critical_errors == 0
