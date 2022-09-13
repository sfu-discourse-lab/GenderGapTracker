"""
Prepare Data for Topic Modelling:

Since the raw dump from MongoDB has data in an undesirable format,
we clean it up and filter the relevant subset for our needs in topic modelling.
"""
import argparse
import os
from pyspark.sql import SparkSession
import pyspark.sql.functions as f
import pyspark.sql.types as t
from config import config

# root_dit = "./"
root_dir = "/home/pprao/projects/ctb-popowich/ggt"
dataloc = os.path.join(root_dir, '21-04-2020-ggt.parquet')


@f.udf(t.StringType())
def get_ids(_id):
    return _id[0]


def filter_raw_data(df):
    """Extract only relevant columns of data we require for topic modelling.
       NOTE: The unix timestamp from MongoDB is divided by 1000 here because of the
       extra 3 zeros at the end (we don't need milliseconds).
    """
    dataDF = df.select('_id', 'publishedAt', 'outlet', 'url', 'title', 'body', 'peopleFemaleCount',
                       'peopleMaleCount', 'sourcesFemaleCount', 'sourcesMaleCount') \
        .withColumn('id', get_ids(f.col('_id'))) \
        .withColumn('unix_timestamp', f.get_json_object(df.publishedAt, "$.$date") / 1000) \
        .withColumn('string_timestamp', f.from_unixtime(f.col('unix_timestamp'))) \
        .withColumn('timestamp', f.col('string_timestamp').cast(t.TimestampType())) \
        .drop('_id', 'publishedAt', 'unix_timestamp', 'string_timestamp')
    return dataDF


def get_english_by_timestamp(df):
    """Extract English articles only within the given date range"""
    englishArticleDF = df.where(f.col('outlet').isin(OUTLETS))
    # Use timestamps for the first and last minute of the start/end days respectively
    start = "{} 00:00:00".format(begin_date)
    end = "{} 23:59:59".format(end_date)
    filteredDF = englishArticleDF.filter(f.col("timestamp") > f.unix_timestamp(
                                         f.lit(start)).cast('timestamp')) \
                                 .filter(f.col("timestamp") < f.unix_timestamp(
                                         f.lit(end)).cast('timestamp'))
    return filteredDF


def get_articles_with_sources(df):
    """Ignore articles for which the `sourcesFemaleCount` and `sourcesMaleCount` fields are
       null (this means that the full NLP pipeline wasn't run on these articles). 
       Zero sources in the article are possible, and these are not filtered out.
    """
    sourcesDF = df.filter('sourcesFemaleCount is not NULL and sourcesMaleCount is not NULL')
    return sourcesDF


def get_date_range(df, colname='timestamp'):
    """Sanity check to verify that the minimum and maximum dates make sense
       (after running the filtering and cleanup steps).
    """
    min_date = f.date_format(f.min(colname), 'YYYY-MM-dd HH:mm:ss')
    max_date = f.date_format(f.max(colname), 'YYYY-MM-dd HH:mm:ss')
    min_date, max_date = df.select(min_date, max_date).first()
    print("Earliest timestamp in data: {}".format(min_date))
    print("Latest timestamp in data: {}".format(max_date))
    return min_date, max_date


def write_output_parquet(df, output_dir):
    df.write.mode('overwrite').parquet(output_dir)


def make_dir(dirpath):
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)


def run_cleanup():
    df = spark.read.parquet(dataloc)
    dataDF = filter_raw_data(df)
    filteredDF = get_english_by_timestamp(dataDF)
    sourcesDF = get_articles_with_sources(filteredDF)
    sourcesReordered = sourcesDF.select('id', 'timestamp', 'outlet', 'url', 'title', 'body',
                                        'peopleFemaleCount', 'peopleMaleCount',
                                        'sourcesFemaleCount', 'sourcesMaleCount',
                                        )
    return sourcesReordered


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions", type=int, default=200, help="Number of shuffle partitions in PySpark")
    parser.add_argument("--begin_date", type=str, default='2018-10-01', help="Begin date format YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default='2020-04-20', help="End date format YYYY-MM-DD")
    args = parser.parse_args()

    # Parse arge
    begin_date = args.begin_date
    end_date = args.end_date

    # Read config
    OUTLETS = config['MODEL']['OUTLETS']

    spark = SparkSession.builder.appName("Cleanup for GGT MongoDB Data Dump") \
        .config("spark.shuffle.io.maxRetries", 20) \
        .config("spark.shuffle.io.retryWait", "20s") \
        .config("spark.buffer.pageSize", "2m") \
        .config("spark.sql.shuffle.partitions", args.partitions) \
        .getOrCreate()
    # Specify timezone as UTC to match with raw data on MongoDB!
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    # Create output directory
    output_dir = "{}/ggt_english_{}_{}".format(root_dir, begin_date, end_date)
    make_dir(output_dir)

    existSourcesDF = run_cleanup()
    num_articles = existSourcesDF.count()
    dtypes = existSourcesDF.dtypes
    # Show minimum and maximum timestamps in the filtered data
    min_date, max_date = get_date_range(existSourcesDF, 'timestamp')
    # Write data to output directory
    write_output_parquet(existSourcesDF, output_dir)

    print("\n\n***\nObtained {} articles after filtering".format(num_articles))
    print("\n\n***\nThe below columns are output to new Parquet files:\n{}".format(dtypes))
    print("\n\n***\nEarliest timestamp article in data: {}\nLatest timestamp article in data: {}\n".format(min_date, max_date))

    spark.stop()
