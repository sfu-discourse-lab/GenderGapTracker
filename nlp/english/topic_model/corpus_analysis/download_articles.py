"""
Download specific articles that are have high values of a particular topic's weights
(t1, t2, etc.). Based on a user's input topic, we rank the article IDs in descending
order of that topic's weights. 

The top 200 (or any other desired number of) article
bodies are downloaded and stored to individual text files, following which we can perform
keyness or other corpus-based linguistic analyses methods.
"""
import argparse
import os
from pymongo import MongoClient
from bson import ObjectId
import pandas as pd
from config import config


def make_dirs(dirpath):
    """ Make directories for output if they don't exist. """
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)


def init_client(MONGO_ARGS):
    """ Initialize a MongoDB client. """
    _db_client = MongoClient(**MONGO_ARGS)
    return _db_client


def download_articles(root_dir, collection, doc_id_list, case='female'):
    """ Download a document object and export its body content to a file. 
    """
    doc_obj = [ObjectId(doc_id.strip()) for doc_id in doc_id_list]
    for idx in doc_obj:
        doc = collection.find_one(
            {'_id': idx},
            {'_id': 1, 'body': 1},
            no_cursor_timeout=True
        )
        make_dirs(f"{root_dir}/{TOPIC}/{case}")
        with open(f"{root_dir}/{TOPIC}/{case}/{str(idx)}.txt", 'w') as f:
            f.write(doc['body'])


def read_data(filepath):
    """ Read topic-split data from CSV """
    df = pd.read_csv(filepath, header=0, parse_dates=['publishedAt'],
                     index_col='_id')
    print(f"Obtained {df.shape[0]} articles in total")
    return df


def get_gender_splitDF(df):
    """ Split the given Dataframe into two smaller Dataframes that each
        represent articles that are female or male source-dominated.
    """
    female = df.loc[df['sourcesFemaleCount'] > df['sourcesMaleCount']]
    male = df.loc[df['sourcesFemaleCount'] < df['sourcesMaleCount']]
    print(f"Found {female.shape[0]} articles dominated by female sources.")
    print(f"Found {male.shape[0]} articles dominated by male sources.")
    return female, male


def top100_per_gender_and_topic(female, male, topic):
    """ Collect top 100 articles sorted by topic weight for a particular
        topic (The topic names are t1-t15 by default in the CSV).
    """
    t_female = female.sort_values(by=topic, ascending=False).iloc[:LIMIT, :]
    t_male = male.sort_values(by=topic, ascending=False).iloc[:LIMIT, :]
    return t_female, t_male


def get_ids(filepath, topic):
    """ Obtain article ID lists for female/male source-dominated articles. """
    df = read_data(filepath)
    female, male = get_gender_splitDF(df)
    t_female, t_male = top100_per_gender_and_topic(female, male, topic)
    female_ids, male_ids = list(t_female.index), list(t_male.index)
    return female_ids, male_ids


def main(filepath, topic='t1'):
    """ Download articles using main pipeline """
    female_ids, male_ids = get_ids(filepath, topic)
    client = init_client(MONGO_ARGS)
    collection = client[DB_NAME][COL_NAME]
    # Make root directory before downloading files
    root_dir = FILENAME.split('/')[-1].replace(".csv", "")
    download_articles(root_dir, collection, female_ids, case='female')
    download_articles(root_dir, collection, male_ids, case='male')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', '-d', type=str, default='mediaTracker', help="Database name")
    parser.add_argument('--col', '-c', type=str, default='media', help="Existing collection name")
    parser.add_argument('--topic', '-t', type=str, default='t1', help="Topic (t1, t2, etc.) to extract articles for")
    parser.add_argument('--file', '-f', type=str, required=True, help="CSV file containing topic splits")
    parser.add_argument('--limit', '-l', type=int, default=200, help="Max. number of articles to consider")
    args = parser.parse_args()

    # Config settings
    MONGO_ARGS = config['MONGO_ARGS']
    # Parse args
    DB_NAME = args.db
    COL_NAME = args.col
    TOPIC = args.topic
    FILENAME = args.file
    LIMIT = args.limit

    main(FILENAME, topic=TOPIC)


