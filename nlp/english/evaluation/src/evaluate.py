import json
import os
import argparse
from ast import literal_eval
import re
from pathlib import Path
from statistics import harmonic_mean

from evaluate_quotes import evaluate_quotes

"""
Display performance metrics for each stage of the gender annotation pipeline
Compares the target annotation and the outputs of run_predictions.py
"""

# ------------------ Helper Methods -------------------

def rounding(value: float) -> float:
    return round(value, 3)


def has_coverage(span_1: tuple, span_2: tuple) -> bool:
    """
    Checks if span_1 has at least two overlapping characters
    with span_2
    """
    span_1_char_indexes = set(range(*span_1))
    span_2_char_indexes = set(range(*span_2))
    return len(span_1_char_indexes & span_2_char_indexes) >= 2


def clean_name(name):
    """
    Same method as used in the English entity_gender_annotator.py script.
    Cleans named entities for standardization in encoding and name references.
    Using this function ensures we're comparing apples to apples during evaluation.
    """
    # Remove all special characters from name
    name = re.sub(r'\W', ' ', name).strip()
    # Remove 's from end of names. Frequent patterns found in logs.
    # the ' has been replace with space in last re.sub function
    if name.endswith(' s'):
        name = name[:-2]
    name = re.sub(r'\s+', ' ', name)
    name = name.lower().strip()
    return name

# ------------------ Quote Extractor -------------------

def process_quote_data(quote_data):
    results = []
    for threshold_data in quote_data:
        summed_data = [sum(col) for col in zip(*threshold_data)]
        quote_precision = rounding(
            100 * summed_data[0] / (summed_data[0] + summed_data[2])
        )
        quote_recall = rounding(
            100 * summed_data[0] / (summed_data[0] + summed_data[1])
        )
        quote_f1 = rounding(harmonic_mean([quote_precision, quote_recall]))
        # How accurate are the speaker-quote matches
        speaker_match_accuracy = rounding(100 * summed_data[3] / summed_data[0])
        # How accurate are the verb-quote matches
        verb_match_accuracy = rounding(100 * summed_data[4] / summed_data[0])
        results.append([quote_precision, quote_recall, quote_f1, "-"])
        results.append(["-"] * 3 + [speaker_match_accuracy])
        results.append(["-"] * 3 + [verb_match_accuracy])
    return results


def compare_speakers_and_verbs(target_quotes, pred_quotes):
    speaker_true_pos = verb_true_pos = 0
    nb_target_speakers = nb_target_verbs = 0
    nb_pred_speakers = nb_pred_verbs = 0
    correct_verb_preds = []
    correct_speaker_preds = []
    for target_quote in target_quotes:
        for pred_quote in pred_quotes:
            # print(target_quote["speaker_index"], pred_quote["speaker_index"])
            if (
                target_quote["speaker_index"]
                and pred_quote["speaker_index"]
                and has_coverage(
                    literal_eval(target_quote["speaker_index"]),
                    literal_eval(pred_quote["speaker_index"]),
                )
            ):
                speaker_true_pos += 1
                correct_speaker_preds.append(pred_quote["speaker_index"])
            # print(target_quote["verb_index"],target_quote["verb"],"|", pred_quote["verb_index"],pred_quote["verb"])
            if (
                target_quote["verb_index"]
                and pred_quote["verb_index"]
                and has_coverage(
                    literal_eval(target_quote["verb_index"]),
                    literal_eval(pred_quote["verb_index"]),
                )
            ):
                verb_true_pos += 1
                correct_verb_preds.append(pred_quote["verb_index"])
        if target_quote["verb_index"]:
            nb_target_verbs += 1
        if target_quote["speaker_index"]:
            nb_target_speakers += 1

    for pred_quote in pred_quotes:
        if pred_quote["speaker_index"]:
            nb_pred_speakers += 1
            if pred_quote["speaker_index"] not in correct_speaker_preds and 0:
                print(
                    "INVENTED SPEAKER", pred_quote["speaker"], "|", pred_quote["verb"]
                )
        if pred_quote["verb_index"]:
            nb_pred_verbs += 1
            if pred_quote["verb_index"] not in correct_verb_preds and 0:
                print(
                    "INVENTED VERB |",
                    pred_quote["speaker"],
                    "|",
                    pred_quote["verb"],
                    pred_quote["verb_index"],
                )
    return (
        speaker_true_pos,
        nb_target_speakers,
        nb_pred_speakers,
        verb_true_pos,
        nb_target_verbs,
        nb_pred_verbs,
    )


def evaluate_quote_extractor(target_dir, pred_dir):
    quote_data, _ = evaluate_quotes(target_dir, pred_dir)
    quote_results = process_quote_data(quote_data)

    speaker_true_pos = verb_true_pos = 0
    nb_target_speakers = nb_target_verbs = 0
    nb_pred_speakers = nb_pred_verbs = 0
    for file_name in os.listdir(target_dir):
        # doc_id = os.path.splitext(file_name)[0]
        # print(doc_id)
        target_file = os.path.join(target_dir, file_name)
        pred_file = os.path.join(pred_dir, file_name)
        if not os.path.isfile(target_file) or not os.path.isfile(pred_file):
            continue
        target_quotes = json.load(open(target_file, encoding="utf-8"))
        target_quotes = (
            target_quotes["quotesUpdated"]
            if "quotesUpdated" in target_quotes
            else target_quotes
        )
        pred_quotes = json.load(open(pred_file, encoding="utf-8"))
        pred_quotes = (
            pred_quotes["quotesUpdated"]
            if "quotesUpdated" in pred_quotes
            else pred_quotes
        )

        stats = compare_speakers_and_verbs(target_quotes, pred_quotes)

        speaker_true_pos += stats[0]
        nb_target_speakers += stats[1]
        nb_pred_speakers += stats[2]
        verb_true_pos += stats[3]
        nb_target_verbs += stats[4]
        nb_pred_verbs += stats[5]

    speaker_recall = rounding(100 * speaker_true_pos / nb_target_speakers)
    speaker_precision = rounding(100 * speaker_true_pos / nb_pred_speakers)
    speaker_f1 = rounding(harmonic_mean([speaker_recall, speaker_precision]))
    verb_recall = rounding(100 * verb_true_pos / nb_target_verbs)
    verb_precision = rounding(100 * verb_true_pos / nb_pred_verbs)
    verb_f1 = rounding(harmonic_mean([verb_recall, verb_precision]))
    speakers_verbs_results = [
        [speaker_precision, speaker_recall, speaker_f1, "-"],
        [verb_precision, verb_recall, verb_f1, "-"],
    ]
    return quote_results + speakers_verbs_results

# ------------------ Gender Annotation ----------------------

def compare_list_annotations(target, pred, counts):
    target = {
        k: {clean_name(name) for name in v}
        for k, v in target.items()
        if type(v) == list and k != "quotesUpdated"
    }
    pred = {
        k: {clean_name(name) for name in v}
        for k, v in pred.items()
        if type(v) == list and k != "quotesUpdated"
    }
    for cat in counts:
        true_pos = target[cat] & pred[cat]
        false_neg = target[cat] - pred[cat]
        false_pos = pred[cat] - target[cat]
        counts[cat][0] += len(true_pos)
        counts[cat][1] += len(false_neg)
        counts[cat][2] += len(false_pos)
    return counts


def evaluate_gender_annotator(target_dir, pred_dir):
    counts = {
        "peopleFemale": [0, 0, 0],
        "peopleMale": [0, 0, 0],
        "peopleUnknown": [0, 0, 0],
        "sourcesFemale": [0, 0, 0],
        "sourcesMale": [0, 0, 0],
        "sourcesUnknown": [0, 0, 0],
    }
    for file_name in os.listdir(target_dir):
        target_file = os.path.join(target_dir, file_name)
        pred_file = os.path.join(pred_dir, file_name)
        if not os.path.isfile(target_file) or not os.path.isfile(pred_file):
            continue
        target_annotation = json.load(open(target_file, encoding="utf-8"))
        pred_annotation = json.load(open(pred_file, encoding="utf-8"))
        counts = compare_list_annotations(target_annotation, pred_annotation, counts)

    metrics = []
    for _, v in counts.items():
        recall = rounding(100 * v[0] / (v[0] + v[1])) if (v[0] + v[1]) > 0.0 else "N/A"
        precision = (
            rounding(100 * v[0] / (v[0] + v[2])) if (v[0] + v[2]) > 0.0 else "N/A"
        )
        f1 = (
            rounding(harmonic_mean([recall, precision]))
            if "N/A" not in [recall, precision]
            else "N/A"
        )
        metrics.append([precision, recall, f1])
    return metrics


# ------------------ Gender Ratio ----------------------

def compare_gender_ratio(target_dir, pred_dir):
    target_people_counts = {"male": 0, "female": 0, "unknown": 0}
    target_sources_counts = {"male": 0, "female": 0, "unknown": 0}
    pred_people_counts = {"male": 0, "female": 0, "unknown": 0}
    pred_sources_counts = {"male": 0, "female": 0, "unknown": 0}
    for file_name in os.listdir(target_dir):
        target_file = os.path.join(target_dir, file_name)
        pred_file = os.path.join(pred_dir, file_name)
        if not os.path.isfile(target_file) or not os.path.isfile(pred_file):
            continue
        target_annotation = json.load(open(target_file, encoding="utf-8"))
        pred_annotation = json.load(open(pred_file, encoding="utf-8"))

        target_people_counts["male"] += target_annotation["peopleMaleCount"]
        target_people_counts["female"] += target_annotation["peopleFemaleCount"]
        target_people_counts["unknown"] += target_annotation["peopleUnknownCount"]

        target_sources_counts["male"] += target_annotation["sourcesMaleCount"]
        target_sources_counts["female"] += target_annotation["sourcesFemaleCount"]
        target_sources_counts["unknown"] += target_annotation["sourcesUnknownCount"]

        pred_people_counts["male"] += pred_annotation["peopleMaleCount"]
        pred_people_counts["female"] += pred_annotation["peopleFemaleCount"]
        pred_people_counts["unknown"] += pred_annotation["peopleUnknownCount"]

        pred_sources_counts["male"] += pred_annotation["sourcesMaleCount"]
        pred_sources_counts["female"] += pred_annotation["sourcesFemaleCount"]
        pred_sources_counts["unknown"] += pred_annotation["sourcesUnknownCount"]

    all_ratios = []
    for data in [
        [target_people_counts, pred_people_counts],
        [target_sources_counts, pred_sources_counts],
    ]:
        ratios = []
        for dic in data:
            total_counts = sum(dic.values())
            ratio = [rounding(cat / total_counts) for cat in dic.values()]
            ratios.append(ratio)
        all_ratios.append(ratios)
    return all_ratios

#################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="evaluation of all the steps of the gender annotation pipeline")
    parser.add_argument("--target_dir", type=str, default="./eval/humanAnnotations/", help="Path to read input text files from this directory.")
    parser.add_argument("--pred_dir", type=str, default="./eval/systemAnnotations/V7.0/", help="Path to write JSON quotes to this directory.")
    parser.add_argument('--quote_extraction', action='store_true', help="compute metrics on the quote extractor output")
    parser.add_argument('--gender_annotation', action='store_true', help="compute metrics on the gender annotator on the whole pipeline")
    parser.add_argument('--gender_ratio', action='store_true', help="compare overall gender ratios between target and output of whole pipeline")
    parser.add_argument('--all', action='store_true', help="compute all metrics")
    args = vars(parser.parse_args())

    TARGET_DIR = args["target_dir"]
    PRED_DIR = args["pred_dir"]
    QUOTE_EXTRACTION = args["quote_extraction"]
    GENDER_ANNOTATION = args["gender_annotation"]
    GENDER_RATIO = args["gender_ratio"]

    eval_version = Path(PRED_DIR).name
    print()
    print(f"System evaluation: {eval_version}")

    if args["all"]:
        QUOTE_EXTRACTION = True
        GENDER_ANNOTATION = True
        GENDER_RATIO = True

    results = {}
    if QUOTE_EXTRACTION:
        print("\n\nQuote Extraction")
        print("-" * 40)
        results = evaluate_quote_extractor(
            TARGET_DIR, os.path.join(PRED_DIR, "quotes", "extracted_quotes")
        )
        formatted_row = "{:<20} {:<20} {:<20} {:<20} {:<20}"
        print(
            formatted_row.format(
                "", "Precision (%)", "Recall (%)", "F1-Score (%)", "Accuracy (%)"
            )
        )
        cats = [
            "Quotes: 0.3",
            "Speaker match: 0.3",
            "Verb match: 0.3",
            "Quotes: 0.8",
            "Speaker match: 0.8",
            "Verb match: 0.8",
            "Speakers (indep):",
            "Verbs (indep):",
        ]
        for cat, Row in zip(cats, results):
            print(formatted_row.format(cat, *Row))

    if GENDER_ANNOTATION:
        print("\n\nGender Annotation")
        print("-" * 40)
        results = evaluate_gender_annotator(
            TARGET_DIR, os.path.join(PRED_DIR, "gender_annotation", "entire_pipeline")
        )
        formatted_row = "{:<20} {:<20} {:<20} {:<20}"
        cats = [
            "peopleFemale",
            "peopleMale",
            "peopleUnknown",
            "sourcesFemale",
            "sourcesMale",
            "sourcesUnknown",
        ]
        print(formatted_row.format("", "Precision (%)", "Recall (%)", "F1-Score (%)"))
        for cat, Row in zip(cats, results):
            print(formatted_row.format(cat, *Row))

    if GENDER_RATIO:
        results = compare_gender_ratio(
            TARGET_DIR, os.path.join(PRED_DIR, "gender_annotation", "entire_pipeline")
        )
        formatted_row = "{:<20} {:<20} {:<20} {:<20}"
        cols = ["People", "Sources"]
        for i, col in enumerate(cols):
            print(f"\n\nGender Ratio: {col}")
            print("-" * 40)
            print(formatted_row.format("    ", "Male", "Female", "Unknown"))
            print(formatted_row.format("Human annotations", *results[i][0]))
            print(formatted_row.format(f"System {eval_version}", *results[i][1]))
            print()