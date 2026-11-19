from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.market import FixtureFetchers
from app.main import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "market"
TODAY = date(2026, 11, 19)


@pytest.fixture
def client_fixtures(tmp_path):
    app = create_app(tmp_path / "db.sqlite", fetchers=FixtureFetchers(FIXTURES), today_fn=lambda: TODAY)
    return TestClient(app)
