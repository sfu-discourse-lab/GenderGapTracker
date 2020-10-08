"""
Test script to directly pull data from Mongo database and convert to Spark DataFrame.
(Not used in the pipeline) - this script is purely for testing the DB connection with Spark.
"""
import argparse
import datetime
from pyspark.sql import SparkSession
from pymongo import MongoClient
from config import config


def convert_date(date_str):
    return datetime.datetime.strptime(date_str, '%Y-%m-%d')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions", type=int, default=100, help="Number of shuffle partitions in PySpark")
    parser.add_argument("--begin_date", type=str, default='2020-04-28', help="Begin date format YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default='2020-04-30', help="End date format YYYY-MM-DD")

    args = parser.parse_args()

    begin_date = convert_date(args.begin_date)
    end_date = convert_date(args.end_date)

    # Read config
    MONGO_ARGS = config['MONGO_ARGS']
    DB_NAME = config['DB']['DB_NAME']
    COLLECTION_NAME = config['DB']['COLLECTION_NAME']
    OUTLETS = config['MODEL']['OUTLETS']

    with MongoClient(**MONGO_ARGS) as connection:
        collection = connection[DB_NAME][COLLECTION_NAME]
        articles = collection.aggregate([
            {"$match": {
                "outlet": {"$in": OUTLETS},
                "publishedAt": {"$gte": begin_date, "$lte": end_date}
            }},
            {"$project": {
                '_id': {'$toString': '$_id'}, 'url': 1, 'publishedAt': 1,
                'outlet': 1, 'title': 1, 'body': 1,
                'peopleFemaleCount': 1, 'peopleMaleCount': 1,
                'sourcesFemaleCount': 1, 'sourcesMaleCount': 1}}
        ])

        spark = SparkSession.builder.appName("Cleanup for GGT MongoDB Data Dump") \
            .config("spark.shuffle.io.maxRetries", 20) \
            .config("spark.shuffle.io.retryWait", "20s") \
            .config("spark.buffer.pageSize", "2m") \
            .config("spark.sql.shuffle.partitions", args.partitions) \
            .getOrCreate()

        # Specify timezone as UTC to match with raw data on MongoDB!
        spark.conf.set("spark.sql.session.timeZone", "UTC")
        df_articles = spark.createDataFrame(list(articles))
        num_articles = df_articles.count()
        dtypes = df_articles.dtypes

        print("\n\n***\nObtained {} articles after filtering".format(num_articles))
        print("\n\n***\nThe below columns are output to new Parquet files:\n{}".format(dtypes))
        print("\n\n***\nEarliest timestamp article in data: {}\nLatest timestamp article in data: {}\n".format(begin_date, end_date))

        df_articles.show()
        spark.stop()
