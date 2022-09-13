# Python 3.9

import argparse
import importlib
import json
import os
from ast import literal_eval
from datetime import timedelta
from multiprocessing import cpu_count
from typing import Union

import spacy
from spacy.language import Language
from spacy.tokens import Doc

import utils
from utils import (
    are_almost_same,
    get_list_of_spans,
    has_coverage,
    has_coverage_for_all,
)
from entity_merger import FrenchEntityMerger


class FrenchQuoteMerger:
    """
    Takes the results of the QuoteExtractor (quotes) and
    the EntityMerger (entities) as inputs and assigns a reference entity
    to each of the quotes
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

    def __init__(self, nlp: Language) -> None:
        self.rules_analyzer = nlp.get_pipe("coreferee").annotator.rules_analyzer

    def run(
        self, 
        quotes: list[dict[str, str]], 
        entities: dict[str, tuple[set[tuple[int]], set[str]]], 
        doc: Doc
        ) -> list[dict[str, str]]:
        referenced_quotes = []
        for quote in quotes:
            if quote.get("speaker_gender") == "unknown":
                continue
            referenced_quote = quote.copy()
            assigned_entity, assigned_titles = self.assign_entity(quote, entities, doc)
            referenced_quote["reference"] = assigned_entity
            referenced_quote["speaker_titles"] = assigned_titles
            referenced_quotes.append(referenced_quote)
        return referenced_quotes

    def assign_entity(
        self, 
        quote : dict[str, str], 
        entities : dict[str, tuple[set[tuple[int]], set[str]]], 
        doc: Doc
        )-> tuple[str, Union[list[str],str]]:
        if quote["speaker_index"]:
            speaker_span = literal_eval(quote["speaker_index"])
            speaker_heads_span = self.get_heads_span(speaker_span, doc)
            for entity in entities:
                for mention_heads_span in entities[entity][0]:
                    if has_coverage_for_all(speaker_heads_span, mention_heads_span):
                        titles = [t.capitalize() for t in entities[entity][1]]
                        if titles == []:
                            titles = ""
                        return entity, titles
            # if we found no overlapping mention
            return self.get_non_aligned_speaker_reference(
                speaker_heads_span, doc, speaker_span, entities
            )
        else:
            return self.get_speakerless_reference(quote, entities, doc)

    def get_non_aligned_speaker_reference(
        self, 
        speaker_heads_span: list[tuple[int, int]], 
        doc : Doc, 
        speaker_span: tuple[int, int], 
        entities: dict[str, tuple[set[tuple[int]], set[str]]] 
    )-> tuple[str, str]:
        """
        When no person named entity was found for the speaker
        We look if it does correspond to any person named entity
        And in that case, we return its text

        """
        # We need to deal with coordinated siblings
        # And possessives e.g :  ses voisins
        head_token = doc.char_span(*speaker_heads_span[0]).root
        if self.rules_analyzer.is_potentially_indefinite(head_token):
            return doc.text[speaker_span[0] : speaker_span[1]], ""
        # Self evident references that were not recognised yet
        for entity in entities:
            if are_almost_same(
                entity.lower().strip(),
                doc.text[speaker_span[0] : speaker_span[1]].lower().strip(),
                max_dist=2,
            ):
                titles = [t.capitalize() for t in entities[entity][1]]
                if titles == []:
                    titles = ""
                return entity, titles

        return "", ""

    def get_speakerless_reference(
        self, 
        quote : dict[str, str], 
        entities: dict[str, tuple[set[tuple[int]], set[str]]], 
        doc : Doc):
        # Decide how to deal with floating quotes depending on the
        # inner working of quote extractor
        return "", ""

    def get_heads_span(
        self, 
        span : tuple[int, int], 
        doc : Doc
        ) -> list[tuple[int, int]]:
        """
        Identifiy the spans of the heads of the
        mention span (anaphora and nouns)
        Allows more precise span alignement
        """
        start, end = span
        mention_span = doc.char_span(start, end, alignment_mode="expand")
        main_head = mention_span.root
        if mention_span[:1].sent != mention_span[-1:].sent:
            # Take the head in the first sentence if the span crosses sent boundary
            main_head = doc[mention_span.start : mention_span.sent.end].root
        # Regularise the way the speaker head is chosen
        # Takes the title as the head .
        #  e.g : "Monsieur Jean Maret" -> head is Monsieur
        for i in range(main_head.i, 1, -1):
            if not (
                doc[i].dep_ == "flat:name"
                and doc[i].head == doc[i - 1]
                and doc[i - 1].lemma_.lower() in self.titles_gender_dict
            ):
                break
            main_head = doc[i]
        # get all the siblings heads who are inside span boundary
        siblings_indexes = [
            sibling.i
            for sibling in self.rules_analyzer.get_dependent_siblings(main_head)
            if sibling.idx + len(sibling.text) < end
        ]
        return get_list_of_spans([main_head.i] + siblings_indexes, doc)


def compare_speaker_reference(
    target_quotes : list[dict[str, str]], 
    pred_quotes : list[dict[str, str]]
    ) -> tuple[int, int, int]:
    true_pos, target_human_refs = 0, 0
    for target_quote in target_quotes:
        target_quote_span = literal_eval(target_quote["quote_index"])
        target_reference = target_quote["reference"].replace("ÔøΩ", "é").lower()
        if target_quote["speaker_gender"] == "unknown" or not target_quote["speaker"]:
            continue
        for pred_quote in pred_quotes:
            pred_quote_span = literal_eval(pred_quote["quote_index"])
            # Since it's not possible to have nested quotes
            # We can consider pred and  the same quote when they overlap
            if has_coverage(target_quote_span, pred_quote_span):
                pred_reference = pred_quote["reference"].replace("ÔøΩ", "é").lower()
                if are_almost_same(pred_reference, target_reference):
                    true_pos += 1
                    break
                elif pred_reference:
                    print(
                        f"WRONG REFERENCE : {pred_reference} != {target_reference}",
                        f"(speaker : {target_quote['speaker']}  {target_quote['speaker_index']} )",
                    )
                    break
        target_human_refs += 1
    pred_refs = sum(1 for pq in pred_quotes if pq["reference"])
    return true_pos, target_human_refs, pred_refs


if __name__ == "__main__":
    # In the end we will run everything from here so we need to report all args
    parser = argparse.ArgumentParser(description="Extract quotes from doc(s) and map them to their reference entities, locally or push to db.")
    parser.add_argument("--config_file", type=str, default="config", help="Name of config file")
    parser.add_argument("--db", type=str, default="mediaTrackerTest", help="Database name")
    parser.add_argument("--readcol", type=str, default="quote-extractor-fr-test", help="Collection name")
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
    parser.add_argument("--spacy_model", type=str, default="fr_core_news_md", help="spaCy language model to use for NLP")
    parser.add_argument("--quote_verbs", type=str, default="./rules/quote_verb_list.txt", help="Path to quote verb list for French")
    parser.add_argument("--poolsize", type=int, default=cpu_count(), help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=20, help="Number of articles IDs per chunk being processed concurrently")
    parser.add_argument("--target_dir", type=str, default="", help="Path toe target dir for evaluation. If not specificed, no evaluation is made")

    args = vars(parser.parse_args())

    # ========== Parse config params and arguments ==========
    config_file_name = args["config_file"]
    config_file = importlib.import_module(config_file_name)
    config = config_file.config

    MONGO_ARGS = config["MONGO_ARGS"]
    MAX_BODY_LENGTH = config["NLP"]["MAX_BODY_LENGTH"]

    DB_NAME = args["db"]
    READ_COL = args["readcol"]
    DOC_LIMIT = args["limit"]
    UPDATE_DB = not args["dry_run"]  # Do not update db when we request a dry run
    FORCE_UPDATE = args["force_update"]
    IN_DIR = args["in_dir"] + "/" if args["in_dir"] else ""
    OUT_DIR = args["out_dir"] + "/" if args["out_dir"] else ""
    POOLSIZE = args["poolsize"]
    CHUNKSIZE = args["chunksize"]
    QUOTE_VERBS_FILE = args["quote_verbs"]
    TARGET_DIR = args["target_dir"] + "/" if args["target_dir"] else ""

    date_begin = utils.convert_date(args["begin_date"]) if args["begin_date"] else None
    date_end = utils.convert_date(args["end_date"]) if args["begin_date"] else None

    date_filters = []
    if date_begin:
        date_filters.append({"publishedAt": {"$gte": date_begin}})
    if date_end:
        date_filters.append({"publishedAt": {"$lt": date_end + timedelta(days=1)}})

    if FORCE_UPDATE:
        other_filters = []
    else:
        other_filters = [
            {"quotes": {"$exists": False}},
            {"lastModifier": "mediaCollectors"},
        ]

    doc_id_list = args["ids"] if args["ids"] else None
    outlet_list = args["outlets"] if args["outlets"] else None

    filters = {
        "doc_id_list": doc_id_list,
        "outlets": outlet_list,
        "force_update": FORCE_UPDATE,
        "date_filters": date_filters,
        "other_filters": other_filters,
    }

    print(f"Loading spaCy language model: {args['spacy_model']}...")
    nlp = spacy.load(args["spacy_model"])
    nlp.add_pipe("coreferee")
    print("Finished loading")

    entity_merger = FrenchEntityMerger(nlp)
    quote_merger = FrenchQuoteMerger(nlp)
    db_client = utils.init_client(MONGO_ARGS)
    query = utils.prepare_query(filters)

    if IN_DIR:
        UPDATE_DB = False
        # Add custom read/write logic for local machine here
        file_dict = utils.get_files_from_folder(folder_path=IN_DIR, limit=DOC_LIMIT)
        if TARGET_DIR:
            all_true_pos, total_target_quotes, total_pred_quotes = 0, 0, 0
        for idx, text in file_dict.items():
            print(idx)
            spacy_doc = nlp(utils.preprocess_text(text))
            if OUT_DIR:
                # update out_dir with `quotesUpdated` dict
                utils.write_quotes_local(
                    quote_dict=referenced_quotes, output_dir=OUT_DIR
                )
                pass
            if TARGET_DIR:
                json_file = TARGET_DIR + idx + ".json"
                if not os.path.exists(json_file):
                    continue
                extracted_quotes = json.load(open(json_file, encoding="mac-roman"))
                entities = entity_merger.run(spacy_doc)
                referenced_quotes = quote_merger.run(
                    extracted_quotes, entities, spacy_doc
                )
                true_pos, nb_target_quotes, nb_pred_quotes = compare_speaker_reference(
                    extracted_quotes, referenced_quotes
                )
                all_true_pos += true_pos
                total_target_quotes += nb_target_quotes
                total_pred_quotes += nb_pred_quotes

        if TARGET_DIR:
            recall = all_true_pos / total_target_quotes
            precision = all_true_pos / total_pred_quotes
            print(
                "Correct references : ",
                all_true_pos,
                "; Total Target references :",
                total_target_quotes,
                "; Total Predicted references :",
                total_pred_quotes,
            )
            print(f"Recall : {recall}, Precision : {precision}")
        print(f'Retrieveved {len(file_dict)} files from "{IN_DIR}"')
