import argparse
import os
import sys
import json
from pathlib import Path
from multiprocessing import Pool, cpu_count
from pathlib import Path
import requests
import spacy
from spacy.pipeline import EntityRuler
import neuralcoref
from tqdm import tqdm

sys.path.insert(1, os.path.realpath(Path(__file__).resolve().parents[2]))

from quote_extractor import QuoteExtractor
from entity_gender_annotator import EntityGenderAnnotator
from config import config
import utils
"""
Runs several predictions on the annotated data
This script must be run before evaluate.py
"""


def get_rawtexts_from_file(filename):
    with open(filename, "r") as f:
        return f.read()


def get_data_from_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def chunker(iterable, chunksize):
    """Yield a smaller chunk of a large iterable"""
    for i in range(0, len(iterable), chunksize):
        yield iterable[i : i + chunksize]


def process_chunks(chunk):
    for idx in chunk:
        rawtext = get_rawtexts_from_file(Path(IN_DIR) / f"{idx}.txt")
        text = utils.preprocess_text(rawtext)
        doc = nlp(text)
        if QUOTE_EXTRACTION:
            print(f"Extracting quotes for {idx}")
            pred_extracted_quotes = quote_extractor.extract_quotes(doc)
            json.dump(
                pred_extracted_quotes,
                open(os.path.join(extracted_quotes_dir, idx + ".json"), "w"),
            )
        if GENDER_ANNOTATION:
            print(f"Extracting quotes and entity genders for {idx}")
            pred_extracted_quotes = quote_extractor.extract_quotes(doc)
            json.dump(
                pred_extracted_quotes,
                open(os.path.join(extracted_quotes_dir, idx + ".json"), "w"),
            )
            pred_annotation = entity_gender_annotator.run(
                text, [], pred_extracted_quotes, []
            )
            pred_annotation["lastModified"] = pred_annotation["lastModified"].strftime(
                "%m/%d/%Y, %H:%M:%S"
            )
            json.dump(
                pred_annotation,
                open(os.path.join(gender_annotation_dir, idx + ".json"), "w"),
            )


def run_predictions():
    """
    Make predictions on quote extraction and entity gender annotation for comparison with gold test set
    """
    num_files = len(common_ids)
    num_chunks = len(list(chunker(common_ids, chunksize=CHUNKSIZE)))
    print(f"Organized {num_files} files into {num_chunks} chunks for concurrent processing...")
    # Process files using a pool of executors
    with Pool(processes=POOLSIZE) as pool:
        for _ in tqdm(pool.imap(process_chunks, chunker(common_ids, chunksize=CHUNKSIZE)), total=num_chunks):
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluation of all the steps of the gender annotation pipeline")
    parser.add_argument("--in_dir", type=str, default="./rawtexts/", help="Path to read input text files from this directory.")
    parser.add_argument("--out_dir", type=str, default="./eval/systemAnnotations/V6.1/", help="Path to dir to output all predictions")
    parser.add_argument("--target_dir", type=str, default="./eval/humanAnnotations/", help="Path to json target files. Serve as anchor for intermediate steps of the pipeline.")
    parser.add_argument('--quote_extraction', action='store_true', help="run quote extractor on text input files")
    parser.add_argument('--gender_annotation', action='store_true', help="run whole the whole pipeline on text on text input files")
    parser.add_argument('--all', action='store_true', help="compute all metrics")
    parser.add_argument('--spacy_model', type=str, default="en_core_web_lg", help="spacy language model")
    parser.add_argument("--poolsize", type=int, default=cpu_count(), help="Size of the concurrent process pool for the given task")
    parser.add_argument("--chunksize", type=int, default=5, help="Number of articles per chunk being processed concurrently")
    args = vars(parser.parse_args())
    IN_DIR = args["in_dir"]
    TARGET_DIR = args["target_dir"]
    PRED_DIR = args["out_dir"]
    QUOTE_EXTRACTION = args["quote_extraction"]
    GENDER_ANNOTATION = args["gender_annotation"]
    POOLSIZE = args["poolsize"]
    CHUNKSIZE = args["chunksize"]
    if args["all"]:
        QUOTE_EXTRACTION = True
        GENDER_ANNOTATION = True

    config["NLP"]["QUOTE_VERBS"] = "../../rules/quote_verb_list.txt"
    config["NLP"]["AUTHOR_BLOCKLIST"] = "../../rules/author_blocklist.txt"
    config["NLP"]["NAME_PATTERNS"] = "../../rules/name_patterns.jsonl"
    config["MONGO_ARGS"]["host"] = "localhost"
    # Load spaCy language model and attach custom entity ruler and coreferee pipes downstream
    print(f"Loading spaCy language model: {args['spacy_model']}...")
    nlp = spacy.load(args["spacy_model"])
    # Add custom named entity rules for non-standard person names that spaCy doesn't automatically identify
    ruler = EntityRuler(nlp, overwrite_ents=True).from_disk(
        config["NLP"]["NAME_PATTERNS"]
    )
    nlp.add_pipe(ruler)
    coref = neuralcoref.NeuralCoref(nlp.vocab, max_dist=200)
    nlp.add_pipe(coref, name="neuralcoref")
    print("Finished loading")

    args["spacy_lang"] = nlp
    session = requests.Session()
    args["session"] = session
    config = {**args, **config}

    quote_extractor = QuoteExtractor(config)
    entity_gender_annotator = EntityGenderAnnotator(config)

    txt_files = [f for f in Path(IN_DIR).glob("*.txt")]
    target_files = [f for f in Path(TARGET_DIR).glob("*.json")]
    common_ids = list(set([p.stem for p in txt_files]) & set([p.stem for p in target_files]))

    extracted_quotes_dir = os.path.join(PRED_DIR, "quotes", "extracted_quotes")
    os.makedirs(extracted_quotes_dir, exist_ok=True)
    gender_annotation_dir = os.path.join(
        PRED_DIR, "gender_annotation", "entire_pipeline"
    )
    os.makedirs(gender_annotation_dir, exist_ok=True)
    run_predictions()
