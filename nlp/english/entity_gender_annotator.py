import argparse
import logging
import re
import traceback
import urllib
import importlib
import json
from bson import ObjectId
from datetime import datetime, timedelta
import requests
from multiprocessing import Pool, cpu_count

import neuralcoref
import spacy
from spacy.pipeline import EntityRuler
from config import config
import utils
from quote_extractor import QuoteExtractor

logger = utils.create_logger(
    "entity_gender_annotator",
    log_dir="logs",
    logger_level=logging.INFO,
    file_log_level=logging.INFO,
)


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i : i + chunksize]


def process_chunks(chunk):
    """Pass through a chunk of document IDs and extract quotes"""
    db_client = utils.init_client(MONGO_ARGS)
    read_collection = db_client[DB_NAME][READ_COL]
    write_collection = db_client[DB_NAME][WRITE_COL] if WRITE_COL else None
    for idx in chunk:
        mongo_doc = read_collection.find_one({"_id": idx})
        process_mongo_doc(read_collection, write_collection, mongo_doc)


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
    pool = Pool(processes=poolsize)
    pool.map(process_chunks, chunker(document_ids, chunksize=chunksize))
    pool.close()


class EntityGenderAnnotator:
    def __init__(self, config) -> None:
        self.nlp = config["spacy_lang"]
        self.session = config["session"]
        gender_ip = config["GENDER_RECOGNITION"]["HOST"]
        gender_port = config["GENDER_RECOGNITION"]["PORT"]
        self.gender_recognition_service = f"http://{gender_ip}:{gender_port}"
        self.blocklist = utils.get_author_blocklist(config["NLP"]["AUTHOR_BLOCKLIST"])

    def has_coverage(self, s1, s2):
        """Check if one span covers another"""
        return len(s1.intersection(s2)) >= 2

    def get_genders(self, session, names):
        """Query gender services for a named entity's gender"""
        parsed_names = urllib.parse.quote(",".join(names))
        url = f"{self.gender_recognition_service}/get-genders?people={parsed_names}"
        if parsed_names:
            response = session.get(url)
            if response:
                data = response.json()
            else:
                code = response.status_code
                logger.warning(f"Failed to retrieve valid JSON: status code {code}")
                data = {}
        else:
            data = {}
        return data

    def merge_nes(self, doc_coref):
        """
        Merging named entities is a two step unification process:
          1. Merge NEs based on exact match
          2. merge NEs based on partial match
        """
        # ne_dict and ne_cluster are dictionaries which keys are PERSON named entities extracted from the text and values
        #  are mentions of that named entity in the text. Mention clusters come from coreference clustering algorithm.
        ne_dict = {}
        ne_clust = {}
        # It's highly recommended to clean nes before merging them. They usually contain invalid characters
        person_nes = [x for x in doc_coref.ents if x.label_ == "PERSON"]
        # in this for loop we try to merge clusters detected in coreference clustering

        # ----- Part A: assign clusters to person named entities
        for ent in person_nes:
            # Sometimes we get noisy characters in name entities
            # TODO: Maybe it's better to check for other types of problems in NEs here too

            ent_cleaned = utils.clean_ne(str(ent))
            if (len(ent_cleaned) == 0) or utils.string_contains_digit(ent_cleaned):
                continue

            ent_set = set(range(ent.start_char, ent.end_char))
            found = False
            # if no coreference clusters is detected in the document
            if doc_coref._.coref_clusters is None:
                ne_dict[ent] = []
                ne_clust[ent] = -1

            else:
                for cluster in doc_coref._.coref_clusters:
                    for ment in cluster.mentions:
                        ment_set = set(range(ment.start_char, ment.end_char))
                        if self.has_coverage(ent_set, ment_set):
                            ne_dict[ent] = cluster
                            ne_clust[ent] = cluster.i
                            found = True
                            break
                    if found:
                        break
                if not found:
                    ne_dict[ent] = []
                    ne_clust[ent] = -1

        # ----- Part B: Merge clusters in ne_dict based on exact match of their representative (PERSON named entities)
        merged_nes = {}
        for ne, cluster in zip(ne_dict.keys(), ne_dict.values()):
            ne_clean_text = utils.clean_ne(str(ne))
            if not cluster:
                cluster_id = [-1]
                mentions = []
            else:
                cluster_id = [cluster.i]
                mentions = cluster.mentions

            # check if we already have a unique cluster with same representative
            if ne_clean_text in merged_nes.keys():
                retrieved = merged_nes[ne_clean_text]
                lst = retrieved["mentions"]
                lst = lst + [ne] + mentions
                cls = retrieved["cluster_id"]
                cls = cls + cluster_id
                merged_nes[ne_clean_text] = {"mentions": lst, "cluster_id": cls}
            else:
                tmp = [ne] + mentions
                merged_nes[ne_clean_text] = {"mentions": tmp, "cluster_id": cluster_id}

        # ----- Part C: do a complex merge
        complex_merged_nes, _ = self.complex_merge(merged_nes)
        return complex_merged_nes

    def complex_merge(self, ne_dict):
        """
        Last try to merge named entities based on multi-part ne merge policy
        """
        merged_nes = {}
        changed = {}
        for ne in ne_dict.keys():
            found = False
            for merged in merged_nes.keys():
                if self.can_merge_nes(str(ne), str(merged)):
                    if len(ne) > len(merged):
                        merged_nes[ne] = merged_nes[merged] + ne_dict[ne]["mentions"]
                        changed[ne] = 1
                        del merged_nes[merged]
                    elif len(ne) < len(merged):
                        changed[merged] = 1
                        merged_nes[merged] = (
                            merged_nes[merged] + ne_dict[ne]["mentions"]
                        )
                    found = True
                    break
            if not found:
                changed[ne] = 0
                merged_nes[ne] = ne_dict[ne]["mentions"]

        return merged_nes, changed

    def can_merge_nes(self, ne1, ne2):
        """
        Check whether we can do a multi-part merge for two named entities.
        """
        can_merge = False
        # To get rid of \n and empty tokens
        ne1 = ne1.strip()
        ne2 = ne2.strip()
        if len(ne1) > len(ne2):
            ne_big = ne1
            ne_small = ne2
        else:
            ne_big = ne2
            ne_small = ne1

        ne_big = ne_big.split(" ")
        ne_small = ne_small.split(" ")

        # Check for merging a two part name with a one part first name
        if len(ne_big) == 2 and len(ne_small) == 1:
            first_name_match = (
                (ne_big[0] == ne_small[0])
                and ne_big[0][0].isupper()
                and ne_small[0][0].isupper()
                and ne_big[1][0].isupper()
            )
            can_merge = first_name_match
        # Check for merging a three part and a two part
        elif len(ne_big) == 3 and len(ne_small) == 2:
            last_middle_name_match = (
                (ne_big[-1] == ne_small[-1])
                and (ne_big[-2] == ne_small[-2])
                and ne_big[0][0].isupper()
                and ne_big[1][0].isupper()
                and ne_big[2][0].isupper()
            )
            can_merge = last_middle_name_match
        # Check for merging a three part and a one part
        elif len(ne_big) == 3 and len(ne_small) == 1:
            last_name_match = (
                (ne_big[-1] == ne_small[-1])
                and ne_big[-1][0].isupper()
                and ne_big[0][0].isupper()
            )
            can_merge = last_name_match
        logger.debug(f"ne1: {ne1}\tne2: {ne2}\tComplex Merge Result: {can_merge}")
        return can_merge

    def remove_invalid_nes(self, unified_nes):
        final_nes = {}
        for key, value in zip(unified_nes.keys(), unified_nes.values()):
            # to remove one part NEs after merge
            # Todo: should only remove singltones?
            representative_has_one_token = len(key.split(" ")) == 1
            key_is_valid = not (representative_has_one_token)
            if key_is_valid:
                final_nes[key] = value
        return final_nes

    def get_named_entity(self, doc_coref, span_start, span_end):
        span_set = set(range(span_start, span_end))
        for x in doc_coref.ents:
            x_start = x.start_char
            x_end = x.end_char
            x_set = set(range(x_start, x_end))
            if self.has_coverage(span_set, x_set):
                return str(x), x.label_
        return None, None

    def quote_assign(self, nes, quotes, doc_coref):
        """
        Assign quotes to named entities based on overlap of quote's speaker span and the named entity span
        """
        quote_nes = {}
        quote_no_nes = []
        index_finder_pattern = re.compile(r".*\((\d+),(\d+)\).*")

        aligned_quotes_indices = []

        for q in quotes:
            regex_match = index_finder_pattern.match(q["speaker_index"])
            q_start = int(regex_match.groups()[0])
            q_end = int(regex_match.groups()[1])
            q_set = set(range(q_start, q_end))

            quote_aligned = False
            # search in all of the named entity mentions in it's cluster for the speaker span.
            for ne, mentions in zip(nes.keys(), nes.values()):
                if quote_aligned:
                    break
                for mention in mentions:
                    mention_start = mention.start_char
                    mention_end = mention.end_char
                    mention_set = set(range(mention_start, mention_end))

                    if self.has_coverage(q_set, mention_set):
                        alignment_key = f"{q_start}-{q_end}"
                        aligned_quotes_indices.append(alignment_key)
                        q["is_aligned"] = True
                        q["named_entity"] = str(ne)
                        q["named_entity_type"] = "PERSON"
                        quote_aligned = True

                        if ne in quote_nes.keys():
                            current_ne_quotes = quote_nes[ne]
                            current_ne_quotes.append(q)
                            quote_nes[ne] = current_ne_quotes
                        else:
                            quote_nes[ne] = [q]

                        break  # Stop searching in mentions. Go for next quote

            if not quote_aligned:
                q["is_aligned"] = False
                ne_text, ne_type = self.get_named_entity(doc_coref, q_start, q_end)
                if ne_text is not None:
                    q["named_entity"] = ne_text
                    q["named_entity_type"] = ne_type
                else:
                    q["named_entity"] = ""
                    q["named_entity_type"] = "UNKNOWN"

                quote_no_nes.append(q)

        all_quotes = []
        for ne, q in zip(quote_nes.keys(), quote_nes.values()):
            all_quotes = all_quotes + q

        all_quotes = all_quotes + quote_no_nes

        return quote_nes, quote_no_nes, all_quotes

    def run(self, text, authors, quotes, article_url):
        """Return gender annotations based on names of people and quotes"""
        # Process authors
        cleaner = utils.CleanAuthors(self.nlp)
        authors = cleaner.clean(authors, self.blocklist)
        author_genders = self.get_genders(self.session, authors)
        authors_female, authors_male, authors_unknown = [], [], []

        for person, gender in zip(author_genders.keys(), author_genders.values()):
            if gender == "female":
                authors_female.append(person)
            elif gender == "male":
                authors_male.append(person)
            else:
                if person:
                    authors_unknown.append(person)

        text_preprocessed = utils.preprocess_text(text)
        doc_coref = self.nlp(text_preprocessed)
        unified_nes = self.merge_nes(doc_coref)
        final_nes = self.remove_invalid_nes(unified_nes)

        # Process people
        people = list(final_nes.keys())
        people = list(
            filter(None, people)
        )  # Make sure no empty values are sent for gender prediction
        people_genders = self.get_genders(self.session, people)

        people_female, people_male, people_unknown = [], [], []
        for person, gender in zip(people_genders.keys(), people_genders.values()):
            if gender == "female":
                people_female.append(person)
            elif gender == "male":
                people_male.append(person)
            else:
                if person:
                    people_unknown.append(person)

        # Expert fields are filled base on gender of speakers in the quotes
        sources_female, sources_male, sources_unknown = [], [], []
        nes_quotes, quotes_no_nes, all_quotes = self.quote_assign(
            final_nes, quotes, doc_coref
        )
        sources = list(nes_quotes.keys())

        for speaker in sources:
            gender = people_genders[speaker]
            if gender == "female":
                sources_female.append(speaker)
            elif gender == "male":
                sources_male.append(speaker)
            else:
                if speaker:
                    sources_unknown.append(speaker)

        article_type = utils.get_article_type(article_url)
        annotation = {
            "people": people,
            "peopleCount": len(people),
            "peopleFemale": people_female,
            "peopleFemaleCount": len(people_female),
            "peopleMale": people_male,
            "peopleMaleCount": len(people_male),
            "peopleUnknown": people_unknown,
            "peopleUnknownCount": len(people_unknown),
            "sources": sources,
            "sourcesCount": len(sources),
            "sourcesFemale": sources_female,
            "sourcesFemaleCount": len(sources_female),
            "sourcesMale": sources_male,
            "sourcesMaleCount": len(sources_male),
            "sourcesUnknown": sources_unknown,
            "sourcesUnknownCount": len(sources_unknown),
            "authorsAll": authors,
            "authorsMale": authors_male,
            "authorsMaleCount": len(authors_male),
            "authorsFemale": authors_female,
            "authorsFemaleCount": len(authors_female),
            "authorsUnknown": authors_unknown,
            "authorsUnknownCount": len(authors_unknown),
            "quoteCount": len(quotes),
            "speakersNotCountedInSources": len(quotes_no_nes),
            "quotesUpdated": all_quotes,
            "articleType": article_type,
            "lastModifier": "entity_gender_annotator",
            "lastModified": datetime.now(),
        }
        return annotation


def process_mongo_doc(read_collection, write_collection, mongo_doc):
    """Write entity-gender annotation results to a new collection OR update the existing collection."""
    try:
        doc_id = str(mongo_doc["_id"])
        if mongo_doc is None:
            logger.error(f'Document "{doc_id}" not found.')
        else:
            text = mongo_doc["body"]
            text_length = len(text)
            if text_length > MAX_BODY_LENGTH:
                logger.warning(
                    "Skipping document {doc_id} due to long length {text_length} characters"
                )
                read_collection.update_one(
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
                authors = mongo_doc.get("authors", [])
                text = mongo_doc["body"]
                quotes = mongo_doc["quotes"]
                article_url = mongo_doc["url"]
                annotation = annotator.run(text, authors, quotes, article_url)
                if UPDATE_DB:
                    if WRITE_COL:
                        # This logic is useful if we want to write to a different collection without affecting existing results
                        write_collection.insert_one(
                            {"currentId": ObjectId(doc_id), **annotation}
                        )
                    else:
                        # Directly perform update on existing collection
                        read_collection.update_one(
                            {"_id": ObjectId(doc_id)}, {"$set": annotation}
                        )
    except:
        logger.exception(
            f"Failed to process {mongo_doc['_id']} due to runtime exception!"
        )
        traceback.print_exc()


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
    parser.add_argument("--begin_date", type=str, help="Start date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, help="End date of articles to process (YYYY-MM-DD)")
    parser.add_argument("--outlets", type=str, help="Comma-separated list of news outlets to consider in query scope")
    parser.add_argument("--ids", type=str, help="Comma-separated list of document ids to process. \
                                                  By default, all documents in the collection are processed.")
    parser.add_argument("--spacy_model", type=str, default="en_core_web_lg", help="spaCy language model to use for NLP")
    parser.add_argument("--poolsize", type=int, default=cpu_count(), help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")

    dargs = parser.parse_args()
    args = vars(dargs)

    config_file_name = args["config_file"]
    config_file = importlib.import_module(config_file_name)
    config = config_file.config

    MONGO_ARGS = config["MONGO_ARGS"]
    MAX_BODY_LENGTH = config["NLP"]["MAX_BODY_LENGTH"]
    NAME_PATTERNS = config["NLP"]["NAME_PATTERNS"]

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
            {"lastModifier": "quote_extractor"},
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

    print(f"Loading spaCy language model: {args['spacy_model']}...")
    nlp = spacy.load(args["spacy_model"])
    # Add custom named entity rules for non-standard person names that spaCy doesn't automatically identify
    ruler = EntityRuler(nlp, overwrite_ents=True).from_disk(NAME_PATTERNS)
    nlp.add_pipe(ruler)
    coref = neuralcoref.NeuralCoref(nlp.vocab, max_dist=200)
    nlp.add_pipe(coref, name="neuralcoref")
    print("Finished loading")

    args["spacy_lang"] = nlp
    session = requests.Session()
    args["session"] = session
    config = {**args, **config}
    annotator = EntityGenderAnnotator(config)

    if IN_DIR:
        if OUT_DIR:
            quote_extractor = QuoteExtractor(config)
            print("processing local files")
            file_dict = utils.get_files_from_folder(folder_path=IN_DIR, limit=DOC_LIMIT)
            for idx, text in file_dict.items():
                print(idx)
                quotes = quote_extractor.extract_quotes(
                    nlp(utils.preprocess_text(text))
                )
                annotation = annotator.run(text, [], quotes, "")
                # json jump can't write datetime objects
                annotation["lastModified"] = annotation["lastModified"].strftime(
                    "%m/%d/%Y, %H:%M:%S"
                )
                json.dump(annotation, open(f"{OUT_DIR}/{idx}.json", "w"))
    else:
        # Directly parse documents from the db, and write back to db
        print("Running on database: ", DB_NAME)
        run_pool(POOLSIZE, CHUNKSIZE)
        logger.info("Finished processing documents.")
