import pandas as pd
import utils.dateutils as dateutils
from db.mongoqueries import agg_total_by_week, agg_total_per_outlet
from fastapi import APIRouter, HTTPException, Request, Query
from schemas.stats_by_date import TotalStatsByDate
from schemas.stats_weekly import TotalStatsByWeek

outlet_router = APIRouter()
COLLECTION_NAME = "mediaDaily"
LOWER_BOUNT_START_DATE = "2018-10-01"
ID_MAPPING = {"Huffington Post": "HuffPost Canada"}


@outlet_router.get(
    "/info_by_date",
    response_model=TotalStatsByDate,
    response_description="Get total and per outlet gender statistics for English outlets between two dates",
)
def expertwomen_info_by_date(
    request: Request,
    begin: str = Query(description="Start date in yyyy-mm-dd format"),
    end: str = Query(description="End date in yyyy-mm-dd format"),
) -> TotalStatsByDate:
    if not dateutils.is_valid_date_range(begin, end, LOWER_BOUNT_START_DATE):
        raise HTTPException(
            status_code=416,
            detail=f"Date range error: Should be between {LOWER_BOUNT_START_DATE} and tomorrow's date",
        )
    begin = dateutils.convert_date(begin)
    end = dateutils.convert_date(end)

    query = agg_total_per_outlet(begin, end)
    response = request.app.connection[COLLECTION_NAME].aggregate(query)
    # Work with the data in pandas
    source_stats = list(response)
    df = pd.DataFrame.from_dict(source_stats)
    df["totalGenders"] = df["totalFemales"] + df["totalMales"] + df["totalUnknowns"]
    # Replace outlet names if necessary
    df["_id"] = df["_id"].replace(ID_MAPPING)
    # Take sums of total males, females, unknowns and articles and convert to dict
    result = df.drop("_id", axis=1).sum().to_dict()
    # Compute per outlet stats
    df["perFemales"] = df["totalFemales"] / df["totalGenders"]
    df["perMales"] = df["totalMales"] / df["totalGenders"]
    df["perUnknowns"] = df["totalUnknowns"] / df["totalGenders"]
    df["perArticles"] = df["totalArticles"] / result["totalArticles"]
    # Convert dataframe to dict prior to JSON serialization
    result["sources"] = df.to_dict("records")
    result["perFemales"] = result["totalFemales"] / result["totalGenders"]
    result["perMales"] = result["totalMales"] / result["totalGenders"]
    result["perUnknowns"] = result["totalUnknowns"] / result["totalGenders"]
    return result


@outlet_router.get(
    "/weekly_info",
    response_model=TotalStatsByWeek,
    response_description="Get gender statistics per English outlet aggregated WEEKLY between two dates",
)
def expertwomen_weekly_info(
    request: Request,
    begin: str = Query(description="Start date in yyyy-mm-dd format"),
    end: str = Query(description="End date in yyyy-mm-dd format"),
) -> TotalStatsByWeek:
    if not dateutils.is_valid_date_range(begin, end, LOWER_BOUNT_START_DATE):
        raise HTTPException(
            status_code=416,
            detail=f"Date range error: Should be between {LOWER_BOUNT_START_DATE} and tomorrow's date",
        )
    begin = dateutils.convert_date(begin)
    end = dateutils.convert_date(end)

    query = agg_total_by_week(begin, end)
    response = request.app.connection[COLLECTION_NAME].aggregate(query)
    # Work with the data in pandas
    df = (
        pd.json_normalize(list(response), max_level=1)
        .sort_values(by="_id.outlet")
        .reset_index(drop=True)
    )
    df.rename(
        columns={
            "_id.outlet": "outlet",
            "_id.week": "week",
            "_id.year": "year",
        },
        inplace=True,
    )
    # Replace outlet names if necessary
    df["outlet"] = df["outlet"].replace(ID_MAPPING)
    # Construct DataFrame and handle begin/end dates as datetimes for summing by week
    df["w_begin"] = df.apply(lambda row: dateutils.get_week_bound(row["year"], row["week"], 0), axis=1)
    df["w_end"] = df.apply(lambda row: dateutils.get_week_bound(row["year"], row["week"], 6), axis=1)
    df["w_begin"], df["w_end"] = zip(*df.apply(lambda row: (pd.to_datetime(row["w_begin"]), pd.to_datetime(row["w_end"])), axis=1))
    df = (
        df.drop(columns=["week", "year"], axis=1)
        .sort_values(by=["outlet", "w_begin"])
    )
    # In earlier versions, there was a bug due to which we returned weekly information for the same week begin date twice
    # This bug only occurred when the last week of one year spanned into the next year (partial week across a year boundary)
    # To address this, we perform summation of stats by week to avoid duplicate week begin dates being passed to the front end
    df = df.groupby(["outlet", "w_begin", "w_end"]).sum().reset_index()
    df["totalGenders"] = df["totalFemales"] + df["totalMales"] + df["totalUnknowns"]
    df["perFemales"] = df["totalFemales"] / df["totalGenders"]
    df["perMales"] = df["totalMales"] / df["totalGenders"]
    df["perUnknowns"] = df["totalUnknowns"] / df["totalGenders"]
    # Convert datetimes back to string for JSON serialization
    df["w_begin"] = df["w_begin"].dt.strftime("%Y-%m-%d")
    df["w_end"] = df["w_end"].dt.strftime("%Y-%m-%d")
    df = df.drop(columns=["totalGenders", "totalFemales", "totalMales", "totalUnknowns"], axis=1)

    # Convert dataframe to dict prior to JSON serialization
    weekly_data = dict()
    for outlet in df["outlet"]:
        per_outlet_data = df[df["outlet"] == outlet].to_dict(orient="records")
        # Remove the outlet key from weekly_data
        [item.pop("outlet") for item in per_outlet_data]
        weekly_data[outlet] = per_outlet_data
    output = {"outlets": weekly_data}
    return output
