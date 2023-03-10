from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from english.main import app
from endpoints.outlet_stats import LOWER_BOUND_START_DATE

PREFIX = "expertWomen"


def test_read_main():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200


def test_get_info_by_date():
    with TestClient(app) as client:
        # Choose a date range that is in the recent past
        begin = datetime.today().date() - timedelta(days=7)
        end = datetime.today().date() - timedelta(days=3)
        response = client.get(f"/{PREFIX}/info_by_date?begin={begin}&end={end}")
        assert response.status_code == 200
        body = response.json()
        assert body.get("perFemales") >= 0
        assert body.get("perMales") >= 0
        assert body.get("perUnknowns") >= 0
        assert isinstance(body.get("sources"), list)
        for obj in body.get("sources"):
            assert isinstance(obj.get("_id"), str)
            assert obj.get("perFemales") >= 0
            assert obj.get("perMales") >= 0
            assert obj.get("perUnknowns") >= 0


def test_get_info_by_date_invalid_date_range():
    with TestClient(app) as client:
        lower_bound_date = datetime.fromisoformat(LOWER_BOUND_START_DATE).date()
        past = lower_bound_date - timedelta(days=2)
        response = client.get(f"/{PREFIX}/info_by_date?begin={past}&end={lower_bound_date}")
        assert (
            response.status_code == 416
        ), "English articles start on 2018-10-01, so start date should be 2018-10-01 or later"
        today = datetime.today().date()
        future = today + timedelta(days=2)
        response = client.get(f"/{PREFIX}/info_by_date?begin={today}&end={future}")
        assert response.status_code == 416, "Cannot request stats for dates in the future"


def test_get_weekly_info():
    with TestClient(app) as client:
        # Choose a date range that is in the recent past
        begin = datetime.today().date() - timedelta(days=7)
        end = datetime.today().date() - timedelta(days=3)
        response = client.get(f"/{PREFIX}/weekly_info?begin={begin}&end={end}")
        assert response.status_code == 200
        body = response.json().get("outlets")
        assert len(body) > 0
        for _, stats in body.items():
            for week_id in stats:
                assert isinstance(week_id.get("w_begin"), str)
                assert isinstance(week_id.get("w_end"), str)
                assert week_id.get("perFemales") >= 0
                assert week_id.get("perMales") >= 0
                assert week_id.get("perUnknowns") >= 0


def test_get_weekly_info_invalid_date_range():
    with TestClient(app) as client:
        lower_bound_date = datetime.fromisoformat(LOWER_BOUND_START_DATE).date()
        past = lower_bound_date - timedelta(days=2)
        response = client.get(f"/{PREFIX}/weekly_info?begin={past}&end={lower_bound_date}")
        assert (
            response.status_code == 416
        ), "English articles start on 2018-10-01, so start date should be 2018-10-01 or later"
        today = datetime.today().date()
        future = today + timedelta(days=2)
        response = client.get(f"/{PREFIX}/weekly_info?begin={today}&end={future}")
        assert response.status_code == 416, "Cannot request stats for dates in the future"