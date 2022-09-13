import argparse
import os
import importlib
import sys
import json
from pathlib import Path
import requests

sys.path.insert(1, os.path.realpath(Path(__file__).parents[2]))

import spacy
import coreferee

import utils
from entity_merger import FrenchEntityMerger
from quote_extractor import QuoteExtractor as FrenchQuoteExtractor
from quote_merger import FrenchQuoteMerger
from entity_gender_annotator import FrenchEntityGenderAnnotator
from config import config

"""
Runs several predictions on the annotated data
This script must be run before evaluate.py
"""


def run_predictions(config):
    """
    Make predictions on each step of the pipeline considering the target as
    input from the previous stage.
    For instance : Quote Merging runs the quote merger on the target extracted quotes
    (instead of on the predicted extracted quotes like is done when running the entire pipeline)
    """
    nlp = config["spacy_lang"]
    quote_extractor = FrenchQuoteExtractor(config)
    entity_merger = FrenchEntityMerger(nlp)
    quote_merger = FrenchQuoteMerger(nlp)
    entity_gender_annotator = FrenchEntityGenderAnnotator(config)

    txt_files = utils.get_files_from_folder(IN_DIR)
    target_files = utils.get_files_from_folder(TARGET_DIR, type="json")
    common_docs = set(txt_files.keys()) & set(target_files.keys())

    extracted_quotes_dir = os.path.join(PRED_DIR, "quotes", "extracted_quotes")
    os.makedirs(extracted_quotes_dir, exist_ok=True)
    updated_quotes_dir = os.path.join(PRED_DIR, "quotes", "merged_quotes")
    os.makedirs(updated_quotes_dir, exist_ok=True)
    gender_classification_dir = os.path.join(
        PRED_DIR, "gender_annotation", "gender_classification"
    )
    os.makedirs(gender_classification_dir, exist_ok=True)
    gender_annotation_dir = os.path.join(
        PRED_DIR, "gender_annotation", "entire_pipeline"
    )
    os.makedirs(gender_annotation_dir, exist_ok=True)

    for i, idx in enumerate(common_docs):
        print(f"file {i+1} /  {len(common_docs)}")
        text = utils.preprocess_text(txt_files[idx])
        doc = nlp(text)
        if QUOTE_EXTRACTION:
            pred_extracted_quotes = quote_extractor.extract_quotes(doc)
            json.dump(
                pred_extracted_quotes,
                open(os.path.join(extracted_quotes_dir, idx + ".json"), "w"),
            )
        if QUOTE_MERGING:
            target_quotes = target_files[idx]["quotesUpdated"]
            pred_people = entity_merger.run(doc)
            pred_updated_quotes = quote_merger.run(target_quotes, pred_people, doc)
            json.dump(
                pred_updated_quotes,
                open(os.path.join(updated_quotes_dir, idx + ".json"), "w"),
            )
        if GENDER_CLASSIFICATION:
            target_quotes = target_files[idx]["quotesUpdated"]
            target_people = {p: [set(), set()] for p in target_files[idx]["people"]}
            pred_annotation = entity_gender_annotator.run(
                target_people, target_quotes, []
            )
            pred_annotation["lastModified"] = pred_annotation["lastModified"].strftime(
                "%m/%d/%Y, %H:%M:%S"
            )
            json.dump(
                pred_annotation,
                open(os.path.join(gender_classification_dir, idx + ".json"), "w"),
            )
        if GENDER_ANNOTATION:
            pred_extracted_quotes = quote_extractor.extract_quotes(doc)
            pred_people = entity_merger.run(doc)
            pred_updated_quotes = quote_merger.run(
                pred_extracted_quotes, pred_people, doc
            )
            pred_annotation = entity_gender_annotator.run(
                pred_people, pred_updated_quotes, []
            )
            pred_annotation["lastModified"] = pred_annotation["lastModified"].strftime(
                "%m/%d/%Y, %H:%M:%S"
            )
            json.dump(
                pred_annotation,
                open(os.path.join(gender_annotation_dir, idx + ".json"), "w"),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="evaluation of all the steps of the gender annotation pipeline")
    parser.add_argument("--in_dir", type=str, default="./rawtexts/", help="Path to read input text files from this directory.")
    parser.add_argument("--out_dir", type=str, default="./eval/systemAnnotations/V6.1/", help="Path to dir to output all predictions")
    parser.add_argument("--target_dir", type=str, default="./eval/humanAnnotations/", help="Path to json target files. Serve as anchor for intermediate steps of the pipeline.")
    parser.add_argument('--quote_extraction', action='store_true', help="run quote extractor on text input files")
    parser.add_argument('--quote_merging', action='store_true', help="run quote merger on text files and target quotes")
    parser.add_argument('--gender_classification', action='store_true', help="run gender classification on target quotes and target people")
    parser.add_argument('--gender_annotation', action='store_true', help="run whole the whole pipeline on text on text input files")
    parser.add_argument('--all', action='store_true', help="compute all metrics")
    parser.add_argument('--spacy_model', type=str, default="fr_core_news_lg", help="spacy language model")
    args = vars(parser.parse_args())

    IN_DIR = args["in_dir"]
    TARGET_DIR = args["target_dir"]
    PRED_DIR = args["out_dir"]
    QUOTE_EXTRACTION = args["quote_extraction"]
    QUOTE_MERGING = args["quote_merging"]
    GENDER_CLASSIFICATION = args["gender_classification"]
    GENDER_ANNOTATION = args["gender_annotation"]
    if args["all"]:
        QUOTE_EXTRACTION = True
        QUOTE_MERGING = True
        GENDER_CLASSIFICATION = True
        GENDER_ANNOTATION = True

    config |= args

    config["NLP"]["QUOTE_VERBS"] = "../../rules/quote_verb_list.txt"
    config["NLP"]["AUTHOR_BLOCKLIST"] = "../../rules/author_blocklist.txt"
    config["NLP"]["NAME_PATTERNS"] = "../../rules/name_patterns.jsonl"
    config["MONGO_ARGS"]["host"] = "localhost"
    config["session"] = requests.Session()
    # Load spaCy language model and attach custom entity ruler and coreferee pipes downstream
    config["spacy_lang"] = spacy.load(args["spacy_model"])
    config["spacy_lang"].add_pipe(
        "entity_ruler", config={"overwrite_ents": True}
    ).from_disk(config["NLP"]["NAME_PATTERNS"])
    config["spacy_lang"].add_pipe("coreferee")
    run_predictions(config)
## Prerequisite: Obtain ssh tunnel to the MongoDB database
'''
To run this script locally, it is first required to set up an ssh tunnel that forwards the database connection to the local machine. This step is essential to complete the evaluation because we host a gender lookup cache on our database, which allows us to retrieve existing names and their associated genders.

Set up the database tunnel on a Unix shell as follows. In the example below, `vm12` is the primary database on which the gender cache is hosted. We simply forward the connection from port 27017 on the remote database to the same port on our local machine.

```sh
ssh vm12 -f -N -L 27017:localhost:27017
```

In case database connectivity is not possible, it's possible to rewrite the gender service to only obtain named-based lookups via external gender APIs. However, in such a case, the results might vary from those shown below.
'''