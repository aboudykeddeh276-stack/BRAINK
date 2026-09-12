from pathlib import Path


def test_operator_deploy_has_no_hardcoded_workbook_dependency():
    script = Path(__file__).resolve().parents[1] / "operator_deploy.sh"
    text = script.read_text(encoding="utf-8")

    assert 'BRAINK_SOURCE_WORKBOOK_ID="${BRAINK_SOURCE_WORKBOOK_ID:-}"' in text
    assert 'BRAINK_OPERATOR_WORKBOOK_ID="${BRAINK_OPERATOR_WORKBOOK_ID:-}"' in text
    assert 'BRAINK_TELEMETRY_SPREADSHEET_ID="${BRAINK_TELEMETRY_SPREADSHEET_ID:-}"' in text
    assert "google_required_for_execution\": False" in text


def test_google_dependencies_are_optional_extra_only():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    base_block = pyproject.split("[project.optional-dependencies]", 1)[0]
    assert "google-api-python-client" not in base_block
    assert "google-auth-oauthlib" not in base_block
    assert "google-auth-httplib2" not in base_block
    assert "[project.optional-dependencies]" in pyproject
    assert "google = [" in pyproject


def test_projection_failure_is_nonfatal_to_host_qualification():
    qualifier = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "qualify_live_telemetry.py"
    ).read_text(encoding="utf-8")

    assert 'result["sheet_projection"] = {"status": "NOT_PROJECTED"' in qualifier
    assert 'result["status"] = "OPERATOR_HOST_LIVE_CARRIER_BOUND"' in qualifier
