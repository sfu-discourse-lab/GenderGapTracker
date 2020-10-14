#These are auxiliary tools to perform different operations
import sys
import random
import argparse
import time
from util import *
from config import *

from datetime import datetime
from pymongo import MongoClient
from collections import namedtuple
from logging import StreamHandler

log = logging.getLogger('mediaCollectorsLogger')
log.setLevel(logging.INFO)


def create_random_data():
    connection = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    mediaCollection = connection["mediaTrackerTest"]["media"]

    medias = mediaCollection.find(projection={'_id': True, 'outlet': True})
    for media in medias:
        log.info("Updating id: " + str(media["_id"]) + " outlet: " + media["outlet"])
        randomData = {'expertFemales': random.randint(0, 10),
                       'expertMales': random.randint(0, 10),
                       'expertUnknowns': random.randint(0, 10)}
        mediaCollection.update({"_id": media["_id"]},
                               {"$set": randomData},
                               upsert=True)


def convert_date():
    connection = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    mediaCollection = connection["mediaTracker"]["media"]

    medias = mediaCollection.find({"publishedAt": {"$exists": True}},
                                  projection={'_id': True, 'outlet': True, 'publishedAt': True})
    errors = 0
    for media in medias:
        log.info("Updating id: " + str(media["_id"]) + " outlet: " + media["outlet"])
        strDate = media["publishedAt"]

        if type(strDate) is str:
            log.info("Date:" + media["publishedAt"])
            strDate = strDate.replace("GMT", "")\
                .replace("-0400", "")\
                .replace("EDT", "")\
                .replace("EST", "")\
                .replace("+0000", "")\
                .replace("-0300", "")\
                .replace("-0700", "")\
                .replace("-0600", "")\
                .replace("-0500", "")\
                .replace("-0001 ", "")\
                .replace(".000", "")\
                .strip()
            try:
                try:
                    convDate = datetime.strptime(strDate, '%a, %d %b %Y %H:%M:%S')
                except ValueError:
                    try:
                        convDate = datetime.strptime(strDate, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        convDate = datetime.strptime(strDate, '%d %b %Y %H:%M:%S')

                # log.info("Converted: %s", convDate)
            except Exception as ex:
                log.exception("Exception: %s", ex)
                errors += 1
                convDate = datetime.utcnow()
                # sys.exit()
            mediaCollection.update({"_id": media["_id"]},
                                    {"$set": {"publishedAt": convDate}},
                                    upsert=True)
    log.info("Failures: %s", errors)


def convert_category():
    connection = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    mediaCollection = connection["mediaTracker"]["media"]

    medias = mediaCollection.find({"outlet": "JournalDeMontreal"},
                                  projection={'_id': True, 'outlet': True,
                                               'publishedAt': True, 'url': True,
                                               'category': True})
    errors = 0
    total = 0
    changed = 0
    for media in medias:
        log.info("Updating id: " + str(media["_id"]) + " Category: " + str(media["category"]) +
                 " outlet: " + media["outlet"] + " Url: " + media['url'])
        total += 1

        # print(type(media["category"]))
        if isinstance(media["category"], str):
            changed += 1
            mediaCollection.update({"_id": media["_id"]},
                                    {"$set": {"category": [media["category"]]}},
                                    upsert=True)
    log.info("Total: %s Changed: %s Failures: %s", total, changed, errors)


def generate_daily_collection():
    connection = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    mediaCollection = connection[DBS_NAME]["media"]

    start_time = time.time()

    log.info("DB: " + DBS_NAME)

    log.info("Starting the aggregation...")
    ret_agregated = mediaCollection.aggregate([
                        {"$match": {"publishedAt":{"$type": "date", "$exists": 1},
                                    "sourcesFemaleCount": {"$exists": 1},
                                    "sourcesMaleCount": {"$exists": 1},
                                    "sourcesUnknownCount": {"$exists": 1}
                                    }},
                        {"$group": {"_id": {"outlet":"$outlet",
                                       "publishedAt": {"$dateToString": {"format": "%Y-%m-%d", "date": "$publishedAt"}}},
                                    "totalArticles": {"$sum": 1},
                                    "totalFemales": {"$sum": "$sourcesFemaleCount"},
                                    "totalMales": {"$sum": "$sourcesMaleCount"},
                                    "totalUnknowns": {"$sum": "$sourcesUnknownCount"}}
                        }
                    ])
    log.info("Query time spent: %s", time.time() - start_time)

    log.info("Dropping mediaDaily Collection")
    media_daily_collection = connection[DBS_NAME]["mediaDaily"]
    media_daily_collection.drop()

    log.info("Inserting into mediaDaily Collection")
    start_time = time.time()
    media_daily_collection = connection[DBS_NAME]["mediaDaily"]

    for row in ret_agregated:
        newRow = dict()
        newRow["outlet"] = row["_id"]["outlet"]
        newRow["publishedAt"] = datetime.strptime(row["_id"]["publishedAt"], '%Y-%m-%d')
        row.pop("_id")
        newRow.update(row)
        media_daily_collection.insert_one(newRow)

    log.info("Insert time spent: %s", time.time() - start_time)


    log.info("Finished generate_daily_collection!")


def copy_records():

    db1 = MongoClient("127.0.0.1", 27019)
    # db1 = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    db2 = MongoClient(MONGODB_HOST, MONGODB_PORT, **MONGO_ARGS)
    log.info("Query DB1")
    datetime()
    result = db1["mediaTracker"]["media"].find({"publishedAt":
                                                    {"$gte": datetime.strptime('2018-12-01', '%Y-%m-%d'),
                                                      "$lte": datetime.strptime('2018-12-25', '%Y-%m-%d')},
                                                "outlet": "CBC News"})
    result = list(result)
    log.info("Size: %s" % len(result))
    inserted = 0
    for row in result:
        log.info("Checking id: %s" % row.pop("_id"))
        header = {"authors": row['authors'], 'outlet': row['outlet'], 'title': row['title']}
        exists = db2["mediaTracker"]["media"].find(header).count()
        if exists == 0:
            log.info("Inserting")
            inserted += 1
            db2["mediaTracker"]["media"].insert_one(row)
        else:
            log.info("Already exist")

        log.info("Header: %s", header)

    log.info("Total: %s Inserted: %s", len(result), inserted)



def log_setup(modules):

    format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rotateHandler = CustomTimedRotatingFileHandler(LOGS_DIR + "-".join(modules), when="midnight")
    rotateHandler.suffix += ".log"
    rotateHandler.setFormatter(format)

    log.addHandler(rotateHandler)
    log.addHandler(StreamHandler(sys.stdout))

    return rotateHandler


if __name__ == "__main__":

    mediaCollectors = [("create_random_data", create_random_data),
                       ("convert_date", convert_date),
                       ("convert_category", convert_category),
                       ("generate_daily_collection", generate_daily_collection),
                       ("copy_records", copy_records)]

    parser = argparse.ArgumentParser(description="These are auxiliary tools to perform different operations")
    parser.add_argument("modules",
                        type=str,
                        nargs="+",
                        help="Values: " + ", ".join(map(lambda m: m[0], mediaCollectors)))

    args = parser.parse_args()
    rotateHandler = log_setup(args.modules)


    try:
        log.info("Args: " + str(args))
        for mediaCollector in mediaCollectors:
            if mediaCollector[0].lower() in [module.lower() for module in args.modules]:
                mediaCollector[1]()
    finally:
        rotateHandler.doRollover()




