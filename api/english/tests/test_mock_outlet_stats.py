from fastapi.testclient import TestClient

from english.main import app
from endpoints.outlet_stats import ID_MAPPING

PREFIX = "expertWomen"


def test_get_info_by_date():
    with TestClient(app) as client:
        # We test mock data in a date range outside that specified in outlet_stats.py
        begin = "2018-09-29"
        end = "2018-09-30"
        response = client.get(f"/{PREFIX}/info_by_date?begin={begin}&end={end}")
        assert response.status_code == 200
        body = response.json()
        # Ensure there are no NaN values due to DivisionByZero when no sources exist
        assert body.get("perFemales") >= 0
        assert body.get("perMales") >= 0
        assert body.get("perUnknowns") >= 0
        assert isinstance(body.get("sources"), list)
        for obj in body.get("sources"):
            assert isinstance(obj.get("_id"), str)
            assert obj.get("perFemales") >= 0
            assert obj.get("perMales") >= 0
            assert obj.get("perUnknowns") >= 0


def test_get_info_outlet_name_mapping_in_list():
    with TestClient(app) as client:
        begin = "2018-09-29"
        end = "2018-09-30"
        response = client.get(f"/{PREFIX}/info_by_date?begin={begin}&end={end}")
        outlet_list = [item.get("_id") for item in response.json().get("sources")]
        for outlet in ID_MAPPING:
            assert ID_MAPPING[outlet] in outlet_list


def test_weekly_info_outlet_name_mapping_in_list():
    with TestClient(app) as client:
        begin = "2018-09-29"
        end = "2018-09-30"
        response = client.get(f"/{PREFIX}/weekly_info?begin={begin}&end={end}")
        outlet_list = [k for k, _ in response.json().get("outlets").items()]
        for outlet in ID_MAPPING:
            assert ID_MAPPING[outlet] in outlet_list