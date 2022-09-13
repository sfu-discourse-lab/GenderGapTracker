"""
This script is designed to be a replacement for the tools.py script that calculates
daily article/source counts per outlet. The aim is to speed up the computation (the
earlier version used vanilla Python) using native mongo objects and queries.

By default, this script is run for all articles published within the last 3 months. Even
though this is redundant, we feel this is necessary, because in some cases, the scrapers
can populate the DB with new articles from a past date. This is why it makes sense to
check up to 3 months back on a daily basis.
"""
import argparse
from datetime import timedelta, datetime
from pymongo import MongoClient
from config import config


def get_connection():
    _db_client = MongoClient(**MONGO_ARGS)
    return _db_client


def format_date(date_str):
    dateFormat = '%Y-%m-%d'
    return datetime.strptime(date_str, dateFormat)


def get_past_date_as_str(days_ago=1):
    today = datetime.today().date() - timedelta(days=days_ago)
    return today.strftime("%Y-%m-%d")


def daily_article_counts(start_date, end_date):
    """
    Returns the daily counts for articles and sources by gender, as published by each
    outlet between two specified dates
    """
    query = [
        {
            "$match": {
                "body": {"$ne": ""},
                "outlet": {"$in": args["outlets"]},
                "publishedAt": {
                    "$gte": start_date,
                    "$lt": end_date,
                },
            }
        },
        {
            "$project": {
                "publishedAt": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$publishedAt"}
                },
                "outlet": 1.0,
                "sourcesFemaleCount": 1.0,
                "sourcesMaleCount": 1.0,
                "sourcesUnknownCount": 1.0,
            }
        },
        {
            "$group": {
                "_id": {
                    "publishedAt": "$publishedAt",
                    "outlet": "$outlet",
                },
                "totalArticles": {"$sum": 1.0},
                "totalFemales": {"$sum": "$sourcesFemaleCount"},
                "totalMales": {"$sum": "$sourcesMaleCount"},
                "totalUnknowns": {"$sum": "$sourcesUnknownCount"},
            }
        },
        # Final projection: Extract the date (from string) and the outlet name, along with article counts
        {
            "$project": {
                "_id": 0.0,
                "publishedAt": {
                    "$dateFromString": {
                        "dateString": "$_id.publishedAt",
                        "format": "%Y-%m-%d",
                    }
                },
                "outlet": "$_id.outlet",
                "totalArticles": 1.0,
                "totalFemales": 1.0,
                "totalMales": 1.0,
                "totalUnknowns": 1.0,
            }
        },
    ]
    return query


def update_db(collection, payload):
    """
    Insert aggregated stats of daily per-outlet article and source counts to the
    specified collection in the DB
    """
    try:
        # Find and upsert stats based on the date string value and outlet name
        # To avoid duplicates, we match on BOTH the name of the outlet and the date string
        for item in payload:
            collection.update_one(
                {
                    "$and": [
                        {"outlet": item["outlet"]},
                        {"publishedAt": item["publishedAt"]},
                    ]
                },
                {
                    "$set": {
                        "totalArticles": item["totalArticles"],
                        "totalFemales": item["totalFemales"],
                        "totalMales": item["totalMales"],
                        "totalUnknowns": item["totalUnknowns"],
                    }
                },
                upsert=True,
            )
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run query and write the daily per-outlet article counts to the database."""
    daily_counts = read_collection.aggregate(daily_article_counts(start_date, end_date))
    # Write daily article counts per outlet to DB for the given date range
    update_db(write_collection, daily_counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="mediaTracker", help="Database name")
    parser.add_argument("--readcol", type=str, default="media", help="Read collection name")
    parser.add_argument("--writecol", type=str, default="mediaDaily", help="Write collection name")
    parser.add_argument("--begin_date", type=str, default=get_past_date_as_str(days_ago=90), help="Start date in the string format YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default=get_past_date_as_str(days_ago=3), help="End date in the string format YYYY-MM-DD")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    args = vars(parser.parse_args())

    start_date = format_date(args["begin_date"])
    end_date = format_date(args["end_date"]) + timedelta(days=1)

    # Import config settings
    MONGO_ARGS = config["MONGO_ARGS"]

    if not args["outlets"]:
        # English outlets
        args["outlets"] = [
            "National Post",
            "The Globe And Mail",
            "The Star",
            "Huffington Post",
            "Global News",
            "CTV News",
            "CBC News",
        ]
    else:
        # Format outlets as a list of strings
        args["outlets"] = args["outlets"].split(",")

    # Connect to database
    _client = get_connection()
    read_collection = _client[args["db"]][args["readcol"]]
    write_collection = _client[args["db"]][args["writecol"]]

    main()