"""
This script merges the results from the newly created collection from the entity 
gender annotation script (when the user specifies the `writecol` argument) with
the original collection.

Only the fields specified in this file are merged with (i.e. overwrite) the original
`media` collection - the remaining fields in the original collection are left untouched.
"""
import argparse
from multiprocessing import Pool, cpu_count
from config import config
import utils


def update_field(existing_collection, new_collection, idx):
    """Overwrite existing collection's fields with new collection's fields (except IDs)"""
    new_id = idx['_id']
    existing_id = idx['currentId']
    doc = new_collection.find_one({'_id': new_id}, no_cursor_timeout=True)
    existing_collection.update(
        {'_id': existing_id},
        {'$set': filter_dict(doc)}
    )


def filter_dict(dict_obj):
    """Return a dictionary that has the same keys/values as the original dictionary,
       except for a few select keys that are to be excluded.
    """
    ignore_keys = ['_id', 'currentId']
    new_dict = {key: dict_obj[key] for key in dict_obj if key not in ignore_keys}
    return new_dict


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i:i + chunksize]


def parse_chunks(chunk):
    """Pass through a chunk of document IDs and update fields"""
    db_client = utils.init_client(MONGO_ARGS)
    existing_collection = db_client[DB_NAME][EXISTING_COL]
    new_collection = db_client[DB_NAME][NEW_COL]
    for idx in chunk:
        update_field(existing_collection, new_collection, idx)


def run_pool(poolsize, chunksize):
    """Concurrently run independent operations on multiple cores"""
    db_client = utils.init_client(MONGO_ARGS)
    # Get list of new and old IDs from new collection
    new_col = db_client[DB_NAME][NEW_COL]
    new_old_ids = list(new_col.find({}, {'_id': 1, 'currentId': 1}))
    print('Obtained ID list of length {}.'.format(len(new_old_ids)))
    # Process quotes using a pool of executors 
    pool = Pool(processes=poolsize)
    pool.map(parse_chunks, chunker(new_old_ids, chunksize=chunksize))
    pool.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='mediaTracker', help="Database name")
    parser.add_argument('--oldcol', type=str, default='media', help="Existing collection name")
    parser.add_argument('--newcol', type=str, default='entitiesAnnotated', help="New collection name")
    parser.add_argument("--poolsize", type=int, default=cpu_count() + 1, help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=100, help="Number of articles IDs per chunk being processed concurrently")
    args = vars(parser.parse_args())

    # From config
    MONGO_ARGS = config['MONGO_ARGS']
    # Parse arguments
    DB_NAME = args['db']
    EXISTING_COL = args['oldcol']
    NEW_COL = args['newcol']
    poolsize = args['poolsize']
    chunksize = args['chunksize']

    run_pool(poolsize, chunksize)
    print("Finished merging collections!")
