"""
This script aggregates the top-N male, female and unknown sources for a given month and 
writes these aggregated top sources and their counts to the `monthlySources` collection.

The purpose of the new collection is to power a dashboard app that allows
the user to see the top quoted sources for a given month.
"""
import argparse
from typing import List, Dict, Any
from datetime import timedelta, datetime
from pymongo import MongoClient
from config import config


def get_connection():
    _db_client = MongoClient(**MONGO_ARGS)
    return _db_client


def get_start_date(year: int, month: int) -> datetime:
    """Given a year and month, return a start date as the first day of that month and year."""
    start_date = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d")
    return start_date


def get_end_date(start_date: datetime) -> datetime:
    """Given a start-date of the first of a given month/year, obtain an end-date
       of the first of next month. Includes a failsafe to handle the month of December.
    """
    if start_date.month == 12:
        # Failsafe if current month is December
        end_date = start_date.replace(year=start_date.year + 1, month=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1)
    return end_date


def get_default_start_year() -> int:
    """Obtain default start year (the year of the previous month from today)"""
    today = datetime.today()
    # Easy way to get last month is to subtract close to 30 days from today
    last_month = today - timedelta(days=25)
    return last_month.year


def get_default_start_month() -> int:
    """Obtain default start month (the previous month from today)"""
    today = datetime.today()
    # Easy way to get last month is to subtract close to 30 days from today
    last_month = today - timedelta(days=25)
    return last_month.month


def top_sources_by_gender(args: Dict[str, Any], field: str="sourcesFemale") -> List[object]:
    """Returns a query that counts of the top-N male/female/unknown sources or people.
       If sorted in ascending order, the returned values represent the 
       bottom-N female sources.
    """
    query = [
        { 
            "$match": { 
                "body": {
                    "$ne": ""
                }, 
                "quotesUpdated": { 
                    "$exists": True
                },
                "outlet": {
                    "$in": args['outlets']
                },
                "publishedAt": { 
                    "$gte": start_date, 
                    "$lt": end_date,
                }
            }
        }, 
        { 
            "$project": { 
                "outlet": 1.0, 
                field: 1.0   # Project just the outlet and the given field (sourcesMale or sourcesFemale)
            }
        }, 
        { 
            "$unwind": { 
                "path": f"${field}", 
                "preserveNullAndEmptyArrays": False
            }
        }, 
        { 
            "$group": { 
                "_id": f"${field}", 
                "count": { 
                    "$sum": 1.0
                }
            }
        }, 
        { 
            "$sort": { 
                "count": args['sort']
            }
        }, 
        { 
            "$limit": args['limit']
        },
        {
            "$project": {
                "_id": 0,
                "name": "$_id",
                "count": 1,
            }
        }
    ]
    return query


def update_db(collection, payload: Dict[str, Any], id_str: str):
    """Update individual JSON objects in the write collection on MongoDB.
    """
    # Write date to DB
    try:
        # Find and upsert unique date id based on the YYYYMM date format
        collection.update_one({'_id': id_str}, {'$set': {'_id': id_str}}, upsert=True)
        # Write topics
        collection.find_one_and_update({'_id': id_str}, {'$set': payload})
    except Exception as e:
        print(f"Error: {e}")


def main(id_str: str):
    """Run query and write the monthly top-source names/counts to the database."""
    top_females = read_collection.aggregate(top_sources_by_gender(args, field='sourcesFemale'))
    top_males = read_collection.aggregate(top_sources_by_gender(args, field='sourcesMale'))
    top_unknowns = read_collection.aggregate(top_sources_by_gender(args, field='sourcesUnknown'))
    # Read in existing user-entered observations on the results (if they exist)
    # NOTE: This assumes that a collection `monthlySources` already exists
    existing_comment = list(write_collection.find({'_id': id_str}, {'comment': '$comment'}))

    # # Convert to a single JSON payload to easily write to MongoDB
    payload = {}
    payload['topFemaleSources'] = list(top_females)
    payload['topMaleSources'] = list(top_males)
    payload['topUnknownSources'] = list(top_unknowns)
    payload['comment'] = existing_comment[0]['comment'] if existing_comment else ""
    # Update DB
    update_db(write_collection, payload, id_str)
    print(f"Finished calculating monthly top sources for {year}-{month}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="mediaTracker", help="Database name")
    parser.add_argument("--readcol", type=str, default="media", help="Read collection name")
    parser.add_argument("--writecol", type=str, default="monthlySources", help="Write collection name")
    parser.add_argument("--year", type=int, default=get_default_start_year(), help="Start date in the format YYYY-MM-DD")
    parser.add_argument("--month", type=int, default=get_default_start_month(), help="End date in the format YYYY-MM-DD")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--limit", type=int, default=50, help="Number of results to limit to")
    parser.add_argument("--sort", type=str, default='desc', help="Sort results in ascending or descending order")
    args = vars(parser.parse_args())

    if args['month'] not in range(1, 13):
        parser.error('Please enter a valid integer month (1-12).')

    year = args['year']
    month = args['month']
    DB_NAME = args["db"]
    READ_COL = args["readcol"]
    WRITE_COL = args["writecol"]

    start_date = get_start_date(year, month)
    end_date = get_end_date(start_date)

    # Import config settings
    MONGO_ARGS = config['MONGO_ARGS']

    if not args['outlets']:
        # Consider all seven English-language outlets by default
        args['outlets'] = [
            'National Post', 'The Globe And Mail', 'The Star', 
            'Huffington Post', 'Global News', 'CTV News', 'CBC News'
        ]
    else:
        # Format outlets as a list of strings
        args['outlets'] = args['outlets'].split(",")

    # Convert sort value to float for pymongo (1.0 is ascending, -1.0 is descending)
    args['sort'] = 1.0 if args['sort'] == 'asc' else -1.0

    # Store year and month for file prefix
    prefix = start_date.strftime('%Y-%m')

    # Store the de-hyphenated date prefix as a unique document ID for MongoDB
    id_str = prefix.replace("-", "")

    # Connect to database
    _client = get_connection()
    read_collection = _client[DB_NAME][READ_COL]
    write_collection = _client[DB_NAME][WRITE_COL]

    main(id_str)
