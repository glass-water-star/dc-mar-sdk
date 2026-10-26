import pytest
import typer
from typer.testing import CliRunner

from dc_mar_sdk.cli.main import api_request, app, parse_key_value_options

runner = CliRunner()


def test_cli_and_typed_command_help_are_available() -> None:
    root_help = runner.invoke(app, ["--help"])
    address_help = runner.invoke(app, ["locations", "address", "--help"])

    assert root_help.exit_code == 0
    assert "api-request" in root_help.output
    assert address_help.exit_code == 0
    assert "Locate an address with strict response validation." in address_help.output


def test_api_request_rejects_unknown_documented_operation() -> None:
    with pytest.raises(typer.BadParameter, match=r"must match the authoritative MAR v2\.2 contract"):
        api_request(method="DELETE", operation="/api/v2.2/units")


def test_parse_key_value_options_requires_unique_pairs() -> None:
    assert parse_key_value_options(["zone=Ward", "geo=true"], "--query-parameter") == {
        "zone": "Ward",
        "geo": "true",
    }

    try:
        parse_key_value_options(["zone=Ward", "zone=ANC"], "--query-parameter")
    except Exception as error:
        assert "duplicate key" in str(error)
    else:
        raise AssertionError("Expected duplicate query parameter to be rejected")
