"""
This script is meant to be run JUST ONCE A MONTH (at the start).
It aggregates the top-N sources (male and female), for a given month and 
writes their names and quote counts to the `monthlySourcesTopN` collection.

The purpose of the new collection is to power a dashboard app that allows
the user to explore top-source-count trends over each month.
"""
import argparse
from typing import List, Dict, Any
from datetime import timedelta, datetime
from pymongo import MongoClient
from config import config


def get_connection():
    _db_client = MongoClient(**MONGO_ARGS)
    return _db_client


def format_date(date_str):
    dateFormat = '%Y-%m-%d'
    return datetime.strptime(date_str, dateFormat)


def get_begin_date():
    """Automatically generate a string representing the first day of last month."""
    today = datetime.today()
    # Easy way to get last month is to subtract close to 30 days from today
    # The assumption is that this script is ONLY run once a month, at the start.
    last_month = today - timedelta(days=25)
    begin_date = last_month.strftime("%Y-%m") + "-01"  # First day of last month
    return begin_date


def get_end_date():
    """Automatically generate a string representing the first day of this month."""
    today = datetime.today()
    end_date = today.strftime("%Y-%m") + "-01"  # First day of this month
    return end_date


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
                    "$gte": args['begin_date'], 
                    "$lt": args['end_date'] + timedelta(days=1)
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
                "date": args['begin_date'],
                "name": "$_id",
                "count": 1,
            }
        }
    ]
    return query


def update_db(collection, payload):
    """Insert aggregated stats (names and counts) to the specified collection in the DB"""
    try:
        # Find and upsert stats based on the date in YYYYMM date format
        # To avoid duplicates, we match on BOTH the name of the person and the month
        for item in payload:
            collection.update_one(
                {'$and':
                    [
                        {'name': item['name']},
                        {'date': item['date']},
                    ]
                },
                {'$set': {'count': item['count']}},
                upsert=True,
            )
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run query and write the monthly top-source names/counts to the database."""
    top_females = read_collection.aggregate(top_sources_by_gender(args, field='sourcesFemale'))
    top_males = read_collection.aggregate(top_sources_by_gender(args, field='sourcesMale'))
    # Update DB
    update_db(write_collection, top_females)
    update_db(write_collection, top_males)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--begin_date", type=str, default=get_begin_date(), help="Start date in the format YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default=get_end_date(), help="End date in the format YYYY-MM-DD")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--limit", type=int, default=50, help="Number of results to limit to")
    parser.add_argument("--sort", type=str, default='desc', help="Sort results in ascending or descending order")
    args = vars(parser.parse_args())

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

    # Store dates as strings for file naming
    start_date = args['begin_date']
    end_date = args['end_date']
    # Store year and month for file prefix
    prefix = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m')
    # Format dates as datetime objects for pymongo
    args['begin_date'] = format_date(args['begin_date'])
    args['end_date'] = format_date(args['end_date'])

    # Connect to database
    _client = get_connection()
    read_collection = _client['mediaTracker']["media"]
    write_collection = _client['mediaTracker']["monthlySourcesTimeSeries"]

    main()
