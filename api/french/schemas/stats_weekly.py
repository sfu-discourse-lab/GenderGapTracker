from datetime import date, datetime
from math import isnan
from typing import Dict, List

from pydantic import BaseModel, root_validator, validator


class OutletStatsByWeek(BaseModel):
    w_begin: date
    w_end: date
    perFemales: float
    perMales: float
    perUnknowns: float

    # validation
    @validator("w_begin", "w_end", pre=True, always=True)
    def valid_date(dateval):
        """Validate a date string to be of the format yyyy-mm-dd"""
        if isinstance(dateval, str):
            return datetime.strptime(dateval, "%Y-%m-%d").strftime("%Y-%m-%d")
        return dateval

    @root_validator
    def _valid_percentage(cls, values):
        """Avoid NaNs by setting them to 0.0"""
        for key in ["perFemales", "perMales", "perUnknowns"]:
            if isnan(values[key]):
                values[key] = 0.0
        return values


class TotalStatsByWeek(BaseModel):
    outlets: Dict[str, List[OutletStatsByWeek]]

    class Config:
        schema_extra = {
            "example": {
                "outlets": {
                    "Outlet 1": [
                        {
                            "w_begin": "2021-12-26",
                            "w_end": "2022-01-01",
                            "perFemales": 0.3915470494417863,
                            "perMales": 0.6052631578947368,
                            "perUnknowns": 0.003189792663476874,
                        },
                        {
                            "w_begin": "2022-01-02",
                            "w_end": "2022-01-08",
                            "perFemales": 0.39904862579281186,
                            "perMales": 0.6004228329809725,
                            "perUnknowns": 0.0005285412262156448,
                        },
                    ],
                    "Outlet 2": [
                        {
                            "w_begin": "2021-12-26",
                            "w_end": "2022-01-01",
                            "perFemales": 0.34763636363636363,
                            "perMales": 0.648,
                            "perUnknowns": 0.004363636363636364,
                        },
                        {
                            "w_begin": "2022-01-02",
                            "w_end": "2022-01-08",
                            "perFemales": 0.0,
                            "perMales": 0.0,
                            "perUnknowns": 0.0,
                        },
                    ],
                }
            }
        }
