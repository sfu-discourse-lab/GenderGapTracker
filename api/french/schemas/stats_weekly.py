from datetime import date, datetime
from typing import Dict, List

from pydantic import BaseModel, validator


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


class TotalStatsByWeek(BaseModel):
    outlets: Dict[str, List[OutletStatsByWeek]]
    