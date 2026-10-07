"""Tests for English action translations."""

import json
from pathlib import Path

import yaml

INTEGRATION_DIR = Path(__file__).resolve().parents[1] / "custom_components/boardoil"


def test_service_translations_match_services_yaml() -> None:
    """Test translations cover every action name and field."""
    services = yaml.safe_load((INTEGRATION_DIR / "services.yaml").read_text())
    translations = json.loads((INTEGRATION_DIR / "translations/en.json").read_text())[
        "services"
    ]
    assert set(translations) == set(services)
    for service, definition in services.items():
        assert set(translations[service].get("fields", {})) == set(
            definition.get("fields", {})
        ), service
