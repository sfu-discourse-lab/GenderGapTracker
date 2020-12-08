import argparse
from typing import List, Dict, Any
from datetime import timedelta, datetime
from pymongo import MongoClient
from config import config


def get_connection():
    _db_client = MongoClient(**MONGO_ARGS)
    return _db_client


def convert_date(date_str):
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
                "name": "$_id",
                "count": 1,
            }
        }
    ]
    return query


def update_db(collection, payload, id_str):
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


def main(id_str):
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
    args['begin_date'] = convert_date(args['begin_date'])
    args['end_date'] = convert_date(args['end_date'])

    # Store the de-hyphenated date prefix as a unique document ID for MongoDB
    id_str = prefix.replace("-", "")

    # Connect to database
    _client = get_connection()
    read_collection = _client['mediaTracker']["media"]
    write_collection = _client['mediaTracker']["monthlySources"]

    main(id_str)