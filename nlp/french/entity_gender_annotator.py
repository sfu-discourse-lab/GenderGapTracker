import argparse
import importlib
import json
import re
import logging
import traceback
import urllib
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count

import coreferee
import requests
import spacy
from bson import ObjectId

import utils
from entity_merger import FrenchEntityMerger
from quote_extractor import QuoteExtractor as FrenchQuoteExtractor
from quote_merger import FrenchQuoteMerger


logger = utils.create_logger(
    "entity_gender_annotator_fr",
    log_dir="logs",
    logger_level=logging.INFO,
    file_log_level=logging.INFO,
)


class FrenchEntityGenderAnnotator:
    """
    Takes the outputs of the entity merger and quote merger as inputs
    Returns the people mentioned in the doc and various informations on their genders
    """

    gender_titles_dict = {
        "male": [
            "M.",
            "Mm.",
            "Monsieur",
            "Messieurs",
            "Mgr",
            "Monseigneur",
            "président",
        ],
        "female": [
            "Mme",
            "Mmes",
            "Madame",
            "Mesdames",
            "Mlle",
            "Mlles",
            "Mademoiselle",
            "Mesdemoiselles",
            "Vve",
            "Veuve",
            "présidente",
        ],
        "mixed": [
            "Docteur",
            "Dr",
            "Docteurs",
            "Drs",
            "Professeur",
            "Pr",
            "Professeurs",
            "Prs" "Maitre",
            "Maître",
            "Me",
            "ministre",
        ],
    }
    titles_gender_dict = {
        title.lower(): k for k, v in gender_titles_dict.items() for title in v
    }

    sibling_separator =  re.compile(",|(\\b((et)|(ou)|(mais))\\b)")
    non_name_character = re.compile("[^\w \t\-]")

    def __init__(self, config) -> None:
        self.session = config["session"]
        gender_ip = config["GENDER_RECOGNITION"]["HOST"]
        gender_port = config["GENDER_RECOGNITION"]["PORT"]
        self.gender_recognition_service = f"http://{gender_ip}:{gender_port}"
        self.blocklist = utils.get_author_blocklist(config["NLP"]["AUTHOR_BLOCKLIST"])

    def get_genders(self, session, names: list) -> dict:
        """
        Gets genders of names by calling API
        Returns dict with name as key and gender as value
        """
        parsed_names = urllib.parse.quote(",".join(names))
        url = f"{self.gender_recognition_service}/get-genders?people={parsed_names}"
        if parsed_names:
            response = session.get(url)
            if response:
                data = response.json()
            else:
                code = response.status_code
                data = {}
                print("no response from server", code)
        else:
            data = {}
        return data

    def run(self, entities: dict, updated_quotes: list, authors: list) -> dict:
        """Returns gender annotation based on names of people and quotes"""
        (
            unique_people,
            people_female,
            people_male,
            people_unknown,
        ) = self.get_people_genders(entities)

        (
            sources,
            sources_female,
            sources_male,
            sources_unknown,
        ) = self.get_sources_genders(
            updated_quotes, unique_people, people_female, people_male, people_unknown
        )
        (
            authors_clean,
            authors_female,
            authors_male,
            authors_unknown,
        ) = self.get_author_genders(authors)

        nb_quotes_speaker_not_count_sources = sum(
            1 for q in updated_quotes if q["reference"] not in sources
        )
        annotation = {
            "authorsAll": authors_clean,
            "authorsMale": authors_male,
            "authorsMaleCount": len(authors_male),
            "authorsFemale": authors_female,
            "authorsFemaleCount": len(authors_female),
            "authorsUnknown": authors_unknown,
            "authorsUnknownCount": len(authors_unknown),
            "people": list(unique_people),
            "peopleCount": len(unique_people),
            "peopleFemale": list(people_female),
            "peopleFemaleCount": len(people_female),
            "peopleMale": list(people_male),
            "peopleMaleCount": len(people_male),
            "peopleUnknown": list(people_unknown),
            "peopleUnknownCount": len(people_unknown),
            "sources": list(sources),
            "sourcesCount": len(sources),
            "sourcesFemale": list(sources_female),
            "sourcesFemaleCount": len(sources_female),
            "sourcesMale": list(sources_male),
            "sourcesMaleCount": len(sources_male),
            "sourcesUnknown": list(sources_unknown),
            "sourcesUnknownCount": len(sources_unknown),
            "quoteCount": len(updated_quotes),
            "speakersNotCountedInSources": nb_quotes_speaker_not_count_sources,
            "quotesUpdated": updated_quotes,
            "lastModifier": "entity_gender_annotator",
            "lastModified": datetime.now(),
        }
        return annotation

    def get_people_genders(self, people: dict) -> list:
        """
        Get the gender of the list of people in the doct
        First it lchecks if the title is sign of a gender
        If it does not find any gender it runs the get_genders() func
        """
        unique_people, female_people, male_people, unknown_people = (
            set(),
            set(),
            set(),
            set(),
        )

        title_non_gendered_people = set()
        for entity, entity_sets in people.items():
            if (
                self.sibling_separator.search(entity)
                or self.non_name_character.search(entity)
                or len(entity.split(" ")) < 2
            ):
                continue
            titles_genders = {
                self.titles_gender_dict.get(title) for title in entity_sets[1]
            }

            if "female" in titles_genders:
                female_people.add(entity)
            elif "male" in titles_genders:
                male_people.add(entity)
            else:
                title_non_gendered_people.add(entity)
        # print(people,"|",title_non_gendered_people)
        people_genders = self.get_genders(self.session, title_non_gendered_people)
        female_people |= {
            person for person, gender in people_genders.items() if gender == "female"
        }
        male_people |= {
            person for person, gender in people_genders.items() if gender == "male"
        }
        unknown_people = {
            person for person, gender in people_genders.items() if gender == "unknown"
        }

        unique_people = female_people | male_people | unknown_people

        return (unique_people, female_people, male_people, unknown_people)

    def get_sources_genders(
        self,
        updated_quotes: list,
        unique_people: set,
        people_female: set,
        people_male: set,
        people_unknown: set,
    ) -> tuple:
        """
        returns the sets of sources sorted by their genders
        sources is a subset of unique_people
        """
        sources = {
            quote["reference"] for quote in updated_quotes if quote["reference"]
        } & unique_people
        sources_female = sources & people_female
        sources_male = sources & people_male
        sources_unknown = sources & people_unknown

        return (sources, sources_female, sources_male, sources_unknown)

    def get_author_genders(self, authors: list):
        """
        Run method for processing authors and return more clean author names for gender
        processing.
        """
        cleaner = utils.CleanAuthors(authors)
        authors_clean = cleaner.clean(self.blocklist)
        author_genders = self.get_genders(self.session, authors_clean)

        authors_female = []
        authors_male = []
        authors_unknown = []

        for person, gender in author_genders.items():
            if gender == "female":
                authors_female.append(person)
            elif gender == "male":
                authors_male.append(person)
            else:
                if person:
                    authors_unknown.append(person)
        return (authors_clean, authors_female, authors_male, authors_unknown)


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i : i + chunksize]


def parse_chunks(chunk):
    """Pass through a chunk of document IDs and extract quotes"""
    db_client = utils.init_client(MONGO_ARGS)
    read_collection = db_client[DB_NAME][READ_COL]
    write_collection = db_client[DB_NAME][WRITE_COL] if WRITE_COL else read_collection
    for idx in chunk:
        mongo_doc = read_collection.find_one({"_id": idx})
        process_mongo_doc(write_collection, mongo_doc)


def annotate_text(text, authors, quotes):
    text = utils.preprocess_text(text)
    doc = nlp(text)
    people_clusters = entity_merger.run(doc)
    updated_quotes = quote_merger.run(quotes, people_clusters, doc)
    annotation = entity_gender_annotator.run(people_clusters, updated_quotes, authors)
    return annotation


def process_mongo_doc(collection, mongo_doc):
    """Run whole pipeline on a MongoDB document, and write quotes to a specified collection in the database"""
    try:
        doc_id = str(mongo_doc["_id"])
        if mongo_doc is None:
            logger.error(f'Document "{doc_id}" not found.')
        else:
            text = mongo_doc["body"]
            text_length = len(text)
            if text_length > MAX_BODY_LENGTH:
                logger.warning(
                    f"Skipping document {mongo_doc['_id']} due to long length {text_length} characters"
                )
                if UPDATE_DB:
                    collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {
                            "$unset": {
                                "people": 1,
                                "peopleCount": 1,
                                "peopleFemale": 1,
                                "peopleFemaleCount": 1,
                                "peopleMale": 1,
                                "peopleMaleCount": 1,
                                "peopleUnknown": 1,
                                "peopleUnknownCount": 1,
                                "sources": 1,
                                "sourcesCount": 1,
                                "sourcesFemale": 1,
                                "sourcesFemaleCount": 1,
                                "sourcesMale": 1,
                                "sourcesMaleCount": 1,
                                "sourcesUnknown": 1,
                                "sourcesUnknownCount": 1,
                                "authorsAll": 1,
                                "authorsMale": 1,
                                "authorsMaleCount": 1,
                                "authorsFemale": 1,
                                "authorsFemaleCount": 1,
                                "authorsUnknown": 1,
                                "authorsUnknownCount": 1,
                                "voicesFemale": 1,
                                "voicesMale": 1,
                                "voicesUnknown": 1,
                                "quoteCount": 1,
                                "speakersNotCountedInSources": 1,
                                "quotesUpdated": 1,
                                "articleType": 1,
                                "lastModifier": "max_body_len",
                                "lastModified": datetime.now(),
                            }
                        },
                    )
            else:
                # Process document
                authors = mongo_doc.get("authors", [])
                text = mongo_doc["body"]
                quotes = mongo_doc["quotes"]
                annotation = annotate_text(text, authors, quotes)
                if UPDATE_DB:
                    if WRITE_COL:
                        # This logic is useful if we want to write to a different collection without affecting existing results
                        collection.insert_one({"currentId": ObjectId(doc_id), **annotation})
                    else:
                        # Directly perform update on existing collection
                        collection.update_one(
                            {"_id": ObjectId(doc_id)}, {"$set": annotation}
                        )
    except:
        logger.exception(f"Failed to process {mongo_doc['_id']} due to runtime exception!")
        traceback.print_exc()


def run_pool(poolsize, chunksize):
    """Concurrently perform quote extraction based on a filter query"""
    # Find ALL ids in the database within the query bounds (one-time only)
    client = utils.init_client(MONGO_ARGS)
    id_collection = client[DB_NAME][READ_COL]
    query = utils.prepare_query(FILTERS)
    document_ids = id_collection.find(query).distinct("_id")
    logger.info(f"Obtained ID list for {len(document_ids)} articles.")

    # Check for doc limit
    if DOC_LIMIT > 0:
        document_ids = document_ids[:DOC_LIMIT]
    logger.info(f"Processing {len(document_ids)} articles...")

    # Process quotes using a pool of executors
    if MULTIPROCESSING:
        # TODO: Currently, coreferee doesn't support multiprocessing!!!
        pool = Pool(processes=poolsize)
        pool.map(parse_chunks, chunker(document_ids, chunksize=chunksize))
        pool.close()
    else:
        parse_chunks(document_ids)


# TODO: Remove these helper methods once we process all French articles in the DB at least once
def get_yesterday():
    today = datetime.today().date() - timedelta(days=1)
    return today.strftime("%Y-%m-%d")


def get_last_3_months():
    today = datetime.today().date() - timedelta(days=90)
    return today.strftime("%Y-%m-%d")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract quotes from doc(s) locally or push to db.")
    parser.add_argument("--config_file", type=str, default="config", help="Name of config file")
    parser.add_argument("--db", type=str, default="mediaTracker", help="Database name")
    parser.add_argument("--readcol", type=str, default="media", help="Collection name")
    parser.add_argument("--writecol", type=str, default="", help="Write collection name")
    parser.add_argument("--dry_run", action="store_true", help="Do not write anything to database (dry run)")
    parser.add_argument("--force_update", action="store_true", help="Overwrite already processed documents in database")
    parser.add_argument("--in_dir", type=str, default="", help="Path to read input text files from this directory.")
    parser.add_argument("--out_dir", type=str, default="", help="Path to write JSON quotes to this directory.")
    parser.add_argument("--limit", type=int, default=0, help="Max. number of articles to process")
    parser.add_argument("--begin_date", default=get_last_3_months(), type=str, help="Start date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--end_date", default=get_yesterday(), type=str, help="End date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--ids", type=str, help="Comma-separated list of document ids to process. \
                                                  By default, all documents in the collection are processed.")
    parser.add_argument("--spacy_model", type=str, default="fr_core_news_lg", help="spaCy language model to use for NLP")
    parser.add_argument("--poolsize", type=int, default=cpu_count(), help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")
    parser.add_argument("--multiprocessing", action="store_true", help="Use multiprocessing when processing data")
    dargs = parser.parse_args()
    args = vars(dargs)

    config_file_name = args["config_file"]
    config_file = importlib.import_module(config_file_name)
    config = config_file.config

    MONGO_ARGS = config["MONGO_ARGS"]
    MAX_BODY_LENGTH = config["NLP"]["MAX_BODY_LENGTH"]
    NAME_PATTERNS = config["NLP"]["NAME_PATTERNS"]

    print(f"Loading spaCy language model: {args['spacy_model']}...")
    nlp = spacy.load(args["spacy_model"])
    nlp.add_pipe("entity_ruler", config={"overwrite_ents": True}).from_disk(NAME_PATTERNS)
    nlp.add_pipe("coreferee")
    print("Finished loading")
    args["spacy_lang"] = nlp
    session = requests.Session()
    args["session"] = session

    DB_NAME = args["db"]
    READ_COL = args["readcol"]
    WRITE_COL = args["writecol"]
    DOC_LIMIT = args["limit"]
    UPDATE_DB = not args["dry_run"]
    FORCE_UPDATE = args["force_update"]
    IN_DIR = args["in_dir"] + "/" if args["in_dir"] else ""
    OUT_DIR = args["out_dir"] + "/" if args["out_dir"] else ""
    DOC_LIMIT = args["limit"]
    POOLSIZE = args["poolsize"]
    CHUNKSIZE = args["chunksize"]
    MULTIPROCESSING = args["multiprocessing"]

    DATE_BEGIN = utils.convert_date(args["begin_date"]) if args["begin_date"] else None
    DATE_END = utils.convert_date(args["end_date"]) if args["begin_date"] else None

    DATE_FILTERS = []
    if DATE_BEGIN:
        DATE_FILTERS.append({"publishedAt": {"$gte": DATE_BEGIN}})
    if DATE_END:
        DATE_FILTERS.append({"publishedAt": {"$lt": DATE_END + timedelta(days=1)}})

    if FORCE_UPDATE:
        OTHER_FILTERS = [{"quotes": {"$exists": True}}]
    else:
        OTHER_FILTERS = [
            {"quotes": {"$exists": True}},
            {"lastModifier": "quote_extractor_fr"},
            {"quotesUpdated": {"$exists": False}},
        ]

    DOC_ID_LIST = args["ids"] if args["ids"] else None
    OUTLET_LIST = args["outlets"] if args["outlets"] else None

    FILTERS = {
        "doc_id_list": DOC_ID_LIST,
        "outlets": OUTLET_LIST,
        "force_update": FORCE_UPDATE,
        "date_filters": DATE_FILTERS,
        "other_filters": OTHER_FILTERS,
    }

    config |= args
    entity_merger = FrenchEntityMerger(nlp)
    quote_merger = FrenchQuoteMerger(nlp)
    entity_gender_annotator = FrenchEntityGenderAnnotator(config)

    if IN_DIR:
        if OUT_DIR:
            quote_extractor = FrenchQuoteExtractor(config)
            print("processing local files")
            file_dict = utils.get_files_from_folder(folder_path=IN_DIR, limit=DOC_LIMIT)
            for idx, text in file_dict.items():
                print(idx)
                quotes = quote_extractor.extract_quotes(nlp(utils.preprocess_text(text)))
                annotation = annotate_text(text, [], quotes)
                # json jump can't write datetime objects
                annotation["lastModified"] = annotation["lastModified"].strftime(
                    "%m/%d/%Y, %H:%M:%S"
                )
                json.dump(annotation, open(f"{OUT_DIR}/{idx}.json", "w"))
    else:
        # Directly parse documents from the db, and write back to db
        print("Running on database: ", DB_NAME)
        run_pool(poolsize=POOLSIZE, chunksize=CHUNKSIZE)
        logger.info("Finished processing documents.")
