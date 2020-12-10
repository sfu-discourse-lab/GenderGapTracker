"""
This script aggregates the top-N male and female sources for a given month and 
writes their names and quote counts to the `monthlySourcesTimeSeries` collection.

The purpose of the new collection is to power a time series dashboard app that allows
the user to explore top-source count trends over time.
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
                "date": start_date,
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


def delete_existing_docs(collection):
    """Delete any existing documents with the given date stamp"""
    d = collection.delete_many({'date': start_date})
    print(f"Deleted {d.deleted_count} existing documents with the date {start_date}.")


def main():
    """Run query and write the monthly top-source names/counts to the database."""
    top_females = read_collection.aggregate(top_sources_by_gender(args, field='sourcesFemale'))
    top_males = read_collection.aggregate(top_sources_by_gender(args, field='sourcesMale'))
    # Delete existing documents with the given dates
    delete_existing_docs(write_collection)
    # Write new results to DB for the given dates
    update_db(write_collection, top_females)
    update_db(write_collection, top_males)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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

    # Connect to database
    _client = get_connection()
    read_collection = _client['mediaTracker']["media"]
    write_collection = _client['mediaTracker']["monthlySourcesTimeSeries"]

    main()

