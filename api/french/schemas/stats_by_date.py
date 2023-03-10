from math import isnan
from typing import List

from pydantic import BaseModel, Field, root_validator


def valid_percentage(cls, values):
    """Avoid NaNs by setting them to 0.0"""
    for key in ["perFemales", "perMales", "perUnknowns"]:
        if isnan(values[key]):
            values[key] = 0.0
    return values


class OutletStatsByDate(BaseModel):
    # In Pydantic, the underscore prefix of a field like `_id` is treated as a private attribute
    # We thus define an alias so that the `_id` field can be referenced as is.
    id: str = Field(alias="_id")
    totalArticles: int
    totalFemales: int
    totalMales: int
    totalUnknowns: int
    totalGenders: int
    perFemales: float
    perMales: float
    perUnknowns: float
    perArticles: float

    # validators
    _avoid_nans = root_validator(allow_reuse=True)(valid_percentage)


class TotalStatsByDate(BaseModel):
    totalArticles: int
    totalFemales: int
    totalMales: int
    totalUnknowns: int
    totalGenders: int
    perFemales: float
    perMales: float
    perUnknowns: float
    sources: List[OutletStatsByDate]

    # validators
    _avoid_nans = root_validator(allow_reuse=True)(valid_percentage)

