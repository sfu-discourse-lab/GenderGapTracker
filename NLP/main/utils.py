import logging
import os
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from urllib.request import urlparse

import pymongo
from bson import ObjectId


# ========== Author name cleaning functions and classes ==========
def get_author_blocklist(author_blocklist_file):
    """Store a list of words that cannot be present in an author's name"""
    with open(author_blocklist_file) as f:
        blocklist = set([line.strip() for line in f])
    return blocklist


class CleanAuthors:
    """Class containing methods to process and clean author names as valid
       person names.
    """
    def __init__(self, nlp):
        self.nlp = nlp

    def get_valid_names(self, author_list, blocklist):
        "Return a list of clean author names that do not have blocklisted words"
        authors = set()
        for doc in self.nlp.pipe(author_list, disable=["tagger", "parser", "neuralcoref"]):
            if not self.contains_blocklist(doc.text, blocklist):
                not_blocklist = [tok for tok in doc.ents
                                 if not self.contains_blocklist(tok.text, blocklist)]
                for ent in not_blocklist:
                    if ent.label_ == 'PERSON' and len(ent) > 1:
                        authors.add(ent.text)
            clean_authors = list(authors)
        return clean_authors

    def contains_blocklist(self, parent, blocklist):
        "Identify if a given author name contains a word from the blocklist."
        return (any(token in parent.split() for token in blocklist))

    def de_duplicate(self, authors):
        "If an author name is a subset of another author name, keep only the subset."
        repeated = set()
        for author1 in authors:
            for author2 in authors:
                if author1.lower() in author2.lower() and author1 != author2:
                    repeated.add(author2)
        return list(set(authors) - repeated)

    def clean(self, author_list, blocklist):
        "Run cleaning scripts"
        try:
            authors = self.get_valid_names(author_list, blocklist)
            if len(authors) > 1:
                authors = self.de_duplicate(authors)
        except:
            authors = []
        return authors


# ========== Named Entity Merging functions ==========
def clean_ne(ne_str):
    ne_str = re.sub(r'\W', ' ', ne_str).strip()
    # Remove 's from end of names. Frequent patterns found in logs.
    # the ' has been replace with space in last re.sub function
    if ne_str.endswith(' s'):
        ne_str = ne_str[:-2]
    ne_str = ne_str.replace('  ', ' ').strip()
    return ne_str


def string_contains_digit(inputString):
    return bool(re.search(r'\d', inputString))


# ========== Text Processing functions ==========
def remove_accents(txt):
    """Certain outlets (CTV News) do not use accented characters in person names.
       Others (CBC News and Global news), always use accented characters in names.
       To help normalize these names and get accurate counts of sources, we replace 
       accented characters with their regular English equivalents.

       Example names that are normalized across different outlets using this method:
        * François Legault <-> Francois Legault
        * Valérie Plante <-> Valerie Plante
        * Jean Chrétien <-> Jean Chretien 
    """
    txt = re.sub("[àáâãäå]", 'a', txt)
    txt = re.sub("[èéêë]", 'e', txt)
    txt = re.sub("[ìíîï]", 'i', txt)
    txt = re.sub("[òóôõö]", 'o', txt)
    txt = re.sub("[ùúûü]", 'u', txt)
    txt = re.sub("[ýÿ]", 'y', txt)
    txt = re.sub("ç", 'c', txt)
    txt = re.sub("ñ", 'n', txt)
    # Capitals
    txt = re.sub("[ÀÁÂÃÄÅ]", 'A', txt)
    txt = re.sub("[ÈÉÊË]", 'E', txt)
    txt = re.sub("[ÌÍÎÏ]", 'I', txt)
    txt = re.sub("[ÒÓÔÕÖ]", 'O', txt)
    txt = re.sub("[ÙÚÛÜ]", 'U', txt)
    txt = re.sub("[ÝŸ]", 'Y', txt)
    txt = re.sub("Ç", 'C', txt)
    txt = re.sub("Ñ", 'N', txt)
    return txt


def preprocess_text(txt):
    """Apply a series of cleaning operations to news text to better process
       quotes and named entities downstream.
    """
    # Fix non-breaking space in unicode
    txt = txt.replace(u'\xa0', u' ')   
    # Remove accents to normalize names and get more accurate source counts
    txt = remove_accents(txt)
    # To fix the problem of not breaking at \n
    txt = txt.replace("\n", ".\n ")
    # To remove potential duplicate dots
    txt = txt.replace("..\n ", ".\n ")
    txt = txt.replace(". .\n ", ".\n ")
    txt = txt.replace("  ", " ")
    # Normalize double quotes
    txt = txt.replace("”", '"')
    txt = txt.replace("“", '"')
    txt = txt.replace("〝", '"')
    txt = txt.replace("〞", '"')
    # NOTE: We keep single quotes for now as they are very common outside quotes
    # txt = txt.replace("‘", "'")
    # txt = txt.replace("’", "'")
    return txt


# ========== DB functions ==========
def init_client(MONGO_ARGS):
    _db_client = pymongo.MongoClient(**MONGO_ARGS)
    return _db_client


def prepare_query(filters):
    if filters['outlets']:
        # Assumes that the user provided outlets as a comma-separated list
        outlets = filters['outlets'].split(",")
    else:
        outlets = [
            'National Post', 'The Globe And Mail', 'The Star', 'Huffington Post', 'Global News',
            'CTV News', 'CBC News']    

    if filters['doc_id_list']:
        doc_id_list = [ObjectId(x.strip()) for x in filters['doc_id_list'].split(",")]
        query = {'_id': {'$in': doc_id_list}}
    else:
        query = {
            '$and':
                [
                    {
                        'outlet': {'$in': outlets}
                    },
                    {
                        'body': {'$ne': ''}
                    },

                ] + filters['date_filters'] + filters['other_filters']
        }

    return query


# ========== Other functions ==========

def get_article_type(url):
    result = None
    try:
        url = url.lower()
        o = urlparse(url)
        parts = o.path.split('/')

        # Update article type if found opinion keyword in url
        if ('opinion' in parts) or ('opinions' in parts):
            result = 'opinion'
        else:
            result = 'hard news'
    except:
        result = 'unknown'
        # TODO a better logging mechanism!
        # app_logger.error('Can not get article type for: "' + url + '"')

    return result


def create_logger(logger_name, log_dir="logs", logger_level=logging.WARN, file_log_level=logging.INFO):
    # Create logs directory if does not exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # create two loggers for entity_gender_annotator and gender detection
    app_logger = logging.getLogger(logger_name)

    app_logger.setLevel(logging.DEBUG)
    # add a rotating handler
    app_log_fh = TimedRotatingFileHandler(os.path.join(log_dir, logger_name + '.log'),
                                          when="d",
                                          interval=1,
                                          backupCount=30)

    # app_log_fh = logging.FileHandler(os.path.join(log_dir, logger_name + '.log'))
    app_log_fh.setLevel(file_log_level)
    app_log_ch = logging.StreamHandler()
    app_log_ch.setLevel(logger_level)
    app_log_fh.setFormatter(formatter)
    app_log_ch.setFormatter(formatter)
    app_logger.addHandler(app_log_fh)
    app_logger.addHandler(app_log_ch)

    return app_logger


def extract_first_name(full_name):
    # Fix for names with multiple part
    if full_name.strip().count(' ') > 1 or full_name.strip().count(' ') == 0:
        return None
    else:
        return full_name.split(' ')[0]


def convert_date(date_str):
    if date_str is None:
        return None
    else:
        dateFormat = '%Y-%m-%d'
        return datetime.strptime(date_str, dateFormat)