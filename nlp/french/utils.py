import json
import logging
import os
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Union

import Levenshtein as lev
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

    def __init__(self, authors):
        self.authors = authors

    def get_valid_names(self, blocklist):
        "Return a list of clean author names that do not have blocklisted words"
        authors = set()
        for author in self.authors:
            if not self.contains_blocklist(author, blocklist):
                if len(author) > 1:
                    authors.add(author)
        clean_authors = list(authors)
        return clean_authors

    def contains_blocklist(self, parent, blocklist):
        "Identify if a given author name contains a word from the blocklist."
        return any(token in parent for token in blocklist)

    def de_duplicate(self, authors):
        "If an author name is a subset of another author name, keep only the subset."
        repeated = set()
        for author1 in authors:
            for author2 in authors:
                if author1.lower() in author2.lower() and author1 != author2:
                    repeated.add(author2)
        return list(set(authors) - repeated)

    def clean(self, blocklist):
        "Run cleaning scripts"
        try:
            authors = self.get_valid_names(blocklist)
            if len(authors) > 1:
                authors = self.de_duplicate(authors)
        except:
            authors = []
        # Make sure no empty values are sent for gender prediction
        authors = list(filter(None, authors))
        return authors


# ========== Text Processing functions ==========
def preprocess_text(txt):
    """Apply a series of cleaning operations to news text to better process
    quotes and named entities downstream.
    """
    # Fix non-breaking space in unicode
    txt = txt.replace("\xa0", " ")
    # Remove accents to normalize names and get more accurate source counts
    # txt = remove_accents(txt)

    # # Remove titles and honorifics to reduce ambiguity for gender prediction
    # # Currently deactivated because it did not help improve F1-scores in our Canadian news data
    # txt = remove_titles(txt)

    # ======================================= OLD
    # # To fix the problem of not breaking at \n
    # txt = txt.replace("\n", ".\n ")
    # # To remove potential duplicate dots
    txt = txt.replace("..\n ", ".\n ")
    txt = txt.replace(". .\n ", ".\n ")
    txt = txt.replace("  ", " ")
    # Fix newlines for raw string literals
    txt = txt.replace("\\n", " ")
    txt = txt.replace("\\n\\n", " ")
    p = re.compile(r"(\.)([ \n\r]+)(\.)")
    txt = p.sub(".\\2 ", txt)
    # ======================================= NEW
    # txt = re.sub("[\r\n]+", " ", txt)
    # txt = re.sub("\.( |\.)+",". ", txt)
    # txt = re.sub(" +", " ", txt)
    # txt = txt.strip()
    # ======================================= END

    # Normalize double quotes
    txt = txt.replace("”", '"')
    txt = txt.replace("“", '"')
    txt = txt.replace("〝", '"')
    txt = txt.replace("〞", '"')
    # NOTE: We keep single quotes for now as they are very common outside quotes
    # txt = txt.replace("‘", "'")
    # txt = txt.replace("’", "'")

    txt = re.sub("\\b’\\b", "'", txt)  # apostrophes
    txt = txt.replace("*", " ")
    return txt


def name_length_is_invalid(name):
    """Check if name is too long or too short to be a valid person name."""
    # Sometimes, NER fails comically and returns entities that are too long, and are most likely invalid person names
    # (Unfortunately, this means long Arabic names can be missed , e.g., "Sheikh Faleh bin Nasser bin Ahmed bin Ali Al Thani")
    is_invalid = (len(name.split()) <= 1) or (len(name.split()) > 6)
    return True if is_invalid else False


# ========== DB functions ==========
def init_client(MONGO_ARGS):
    _db_client = pymongo.MongoClient(**MONGO_ARGS)
    return _db_client


def prepare_query(filters):
    if filters["outlets"]:
        # Assumes that the user provided outlets as a comma-separated list
        outlets = filters["outlets"].split(",")
    else:
        outlets = [
            "Journal De Montreal",
            "La Presse",
            "Le Devoir",
            "Le Droit",
            "Radio Canada",
            "TVA News",
        ]

    if filters["doc_id_list"]:
        doc_id_list = [ObjectId(x.strip()) for x in filters["doc_id_list"].split(",")]
        query = {"_id": {"$in": doc_id_list}}
    else:
        query = {
            "$and": [
                {"outlet": {"$in": outlets}},
                {"body": {"$ne": ""}},
            ]
            + filters["date_filters"]
            + filters["other_filters"]
        }

    return query


# ========== Span and Text Comparisons ==========


def are_almost_same(name_a: str, name_b: str, max_dist: int = 1) -> bool:
    if not name_a or not name_b:
        return False
    # We allow one character difference (one typo in the name)
    return lev.distance(name_a, name_b) <= max_dist


def has_coverage(span_1: tuple, span_2: tuple) -> bool:
    """
    Checks if span_1 has at least two overlapping characters
    with span_2
    """
    span_1_char_indexes = set(range(*span_1))
    span_2_char_indexes = set(range(*span_2))
    return len(span_1_char_indexes & span_2_char_indexes) >= 2


def has_coverage_for_all(spans_1: tuple[tuple[int]], spans_2: tuple[tuple[int]]) -> bool:
    """
    Checks if all the spans in spans_1 have at least two overlapping
    characters with at least one span of spans_2
    """
    return all(
        any(has_coverage(span_1, span_2) for span_2 in spans_2) for span_1 in spans_1
    ) and all(any(has_coverage(span_2, span_1) for span_1 in spans_1) for span_2 in spans_2)


def get_list_of_spans(token_indexes: list[int], doc) -> list[tuple[int]]:
    return [(doc[i].idx, doc[i].idx + len(doc[i])) for i in token_indexes]


# ========== Other functions ==========
def create_logger(
    logger_name, log_dir="logs", logger_level=logging.WARN, file_log_level=logging.INFO
):
    # Create logs directory if does not exist
    os.makedirs(log_dir, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # create two loggers for entity_gender_annotator and gender detection
    app_logger = logging.getLogger(logger_name)
    app_logger.setLevel(logging.DEBUG)
    # add a rotating handler
    app_log_fh = TimedRotatingFileHandler(
        os.path.join(log_dir, logger_name + ".log"),
        when="d",
        interval=1,
        backupCount=30,
    )
    # app_log_fh = logging.FileHandler(os.path.join(log_dir, logger_name + '.log'))
    app_log_fh.setLevel(file_log_level)
    app_log_ch = logging.StreamHandler()
    app_log_ch.setLevel(logger_level)
    app_log_fh.setFormatter(formatter)
    app_log_ch.setFormatter(formatter)
    app_logger.addHandler(app_log_fh)
    app_logger.addHandler(app_log_ch)
    return app_logger


def convert_date(date_str: str):
    if date_str is None:
        return None
    else:
        dateFormat = "%Y-%m-%d"
        return datetime.strptime(date_str, dateFormat)


# ========== I/O functions ==========
def get_file_tuple(
    file: str, encoding: str = "utf-8", type: str = "txt"
) -> tuple[str, Union[str, dict]]:
    """tion
    # # Currently deactivated because it did not help improve F1-scores i

    Returns:
        tuple: (int, str)
    """
    head, file_name = os.path.split(file)
    dot_index = file_name.find(".")
    idx = file_name[:dot_index]
    if type == "txt":
        content = open(file, "r", encoding=encoding).read()
    elif type == "json":
        content = json.load(open(file, encoding=encoding))
    return idx, content


def get_file_dict(
    paths: list[str], limit: int, type: str = "txt", encoding="utf-8"
) -> dict[str, Union[str, dict]]:
    files = {}
    for file in paths:
        if len(files) >= limit:
            break
        try:
            idx, text = get_file_tuple(file, encoding=encoding, type=type)
            files[idx] = text
        except Exception as e:
            print(f"{e}\nError encountered in file: ", file)
    return files


def get_files_from_folder(
    folder_path: str = None,
    limit: int = None,
    type: str = "txt",
    encoding: str = "utf-8",
) -> dict[str, Union[str, dict]]:
    files = {}
    if folder_path:
        file_paths = [os.path.join(folder_path, file) for file in os.listdir(folder_path)]
        limit = limit or len(file_paths)
        files = get_file_dict(paths=file_paths, limit=limit, type=type, encoding=encoding)
    return files


def write_quotes_local(quote_dict: dict[str, str], output_dir: str) -> None:
    """Write quotes to output file specified in the commandline args.

    Args:
        quote_dict (dict{int: [Quote]}): a dictionary of quotes by document id
        output_dir (str): the path to save the quotes to
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for idx, quotes in quote_dict.items():
        out_file = open(os.path.join(output_dir, idx + ".json"), "w", encoding="utf-8")
        json.dump(quotes, out_file, indent=4, ensure_ascii=False)
