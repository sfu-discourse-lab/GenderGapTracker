from typing import List

from pydantic import BaseModel, Field


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

