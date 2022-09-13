import argparse
import logging
import time
import os
import sys
import pandas as pd
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pymongo import MongoClient
# config
from config import config
# User-created queries
import queries 


def get_connection():
    connection = MongoClient(**MONGO_ARGS)
    return connection


def format_date(date_str):
    dateFormat = '%Y-%m-%d'
    return datetime.strptime(date_str, dateFormat)


def create_app_logger(filename):
    """Logger format and timed handling"""
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rotateHandler = TimedRotatingFileHandler(os.path.join("logs", "g-statistics.log"),
                                             when="midnight")
    rotateHandler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)

    logger.addHandler(rotateHandler)
    logger.addHandler(stream)
    return logger


def run_aggregation_queries():
    """Collect aggregation query methods from queries.py and run them."""
    query_list = []
    for method_name in args.keys():
        requested = args[method_name]
        if requested and isinstance(requested, bool):
            # Only those args supplied as boolean flags will run as queries
            # getattr(foo, 'bar') equals foo.bar 
            query_list.append(getattr(queries, method_name))

    # Run multiple aggregation queries between specified start/end dates
    for query in query_list:
        logger.info(f"Query: '{query.__name__}', date range: ({start_date}, {end_date})")
        start_time = time.time()
        result = collection.aggregate(query(args))

        # Export CSV
        filename = f"{query.__name__}_{start_date}_to_{end_date}.csv"
        df = pd.DataFrame.from_dict(result)
        df.to_csv(filename, index=False)

        logger.info(f"{query.__name__} query completed in {time.time() - start_time:.3f} seconds.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='mediaTracker', help="Database name")
    parser.add_argument('--col', type=str, default='media', help="Read collection name")
    parser.add_argument("--begin_date", type=str, default="2020-04-29", help="Start date in the format YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default="2020-04-30", help="End date in the format YYYY-MM-DD")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--limit", type=int, default=100, help="Number of results to limit to")
    parser.add_argument("--sort", type=str, default='desc', help="Sort results in ascending or descending order")
    # Query name args (specified as booleans)
    parser.add_argument("--db_stats", action='store_true', help="Run query to calculate overall gender stats (sources, people, authors)")
    parser.add_argument("--outlet_stats", action='store_true', help="Run query to calculate gender stats (sources, people, authors) per outlet")
    parser.add_argument("--top_sources_female", action='store_true', help="Run query to calculate top N female sources")
    parser.add_argument("--top_sources_male", action='store_true', help="Run query to calculate top N male sources")
    parser.add_argument("--top_sources_unknown", action='store_true', help="Run query to calculate top N unknown sources")
    parser.add_argument("--top_sources_all", action='store_true', help="Run query to calculate top N overall sources (male or female)")
    parser.add_argument("--female_author_sources", action='store_true', help="Run query to cross-tabulate female author sources vs. source gender counts")
    parser.add_argument("--male_author_sources", action='store_true', help="Run query to cross-tabulate male author sources vs. source gender counts")
    parser.add_argument("--mixed_author_sources", action='store_true', help="Run query to cross-tabulate both gender (male & female) author sources vs. source gender counts")
    parser.add_argument("--unknown_author_sources", action='store_true', help="Run query to cross-tabulate unknown author sources vs. source gender counts")
    parser.add_argument("--daily_article_counts", action='store_true', help="Run query to get a tally of daily article counts")
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
    # Format dates as datetime objects for pymongo
    args['begin_date'] = format_date(args['begin_date'])
    args['end_date'] = format_date(args['end_date'])

    # Create logs
    os.makedirs("logs", exist_ok=True)
    logger = create_app_logger('statisticsLog')

    # Connect to database
    connection = get_connection()
    collection = connection[args['db']][args['col']]

    run_aggregation_queries()

