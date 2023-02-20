import os, json, re
import argparse
from ast import literal_eval

import pandas as pd
import Levenshtein as lev
import spacy
from spacy.language import Language
from spacy.tokens import Doc, Span
from coreferee.rules import RulesAnalyzerFactory
from coreferee.data_model import Mention

import utils


def compute_statistics(text_dir, target_dir, output_file=None):
    files = utils.get_files_from_folder(text_dir)
    files_data = []
    files_indexes = []
    for i, doc_name in enumerate(files):
        # print(doc_name)
        text = utils.preprocess_text(files[doc_name])
        json_file = target_dir + doc_name + ".json"
        if not os.path.exists(json_file):
            continue
        quote_objects = json.load(open(json_file, encoding="mac-roman"))
        file_data = get_file_stats(text, quote_objects)

        files_data.append(file_data)
        files_indexes.append(doc_name)
    # print(files_data)
    return process_results(files_data, files_indexes, output_file)


def process_results(files_data, files_indexes, output_file):
    columns = [
        "nouns",
        "proper nouns",
        "other nouns",
        "anaphora",
        "non-covered speakers",
        "speakerless quotes",
        "verbless quotes",
        "unknown speaker's gender",
        "referenceless quotes",
        "self-evident_references",
        "plural speaker",
        "total_quotes",
    ]
    df = pd.DataFrame(files_data, index=files_indexes, columns=columns)
    total = df.sum(numeric_only=True, axis=0)
    mean = df.mean(numeric_only=True, axis=0)
    median = df.median(numeric_only=True, axis=0)
    standard_deviation = df.std(numeric_only=True, axis=0)
    total_proportion = total / total["total_quotes"]

    df.loc["Mean"] = mean
    df.loc["Median"] = median
    df.loc["Standard_Deviation"] = standard_deviation
    df.loc["Total"] = total
    df.loc["Total_Proportion"] = total_proportion

    print(df)
    if output_file:
        df.to_csv(output_file, sep=";")
    return df


def get_file_stats(text, quote_objects):
    doc = NLP(text)
    independent_nouns = (
        substantives
    ) = (
        proper_n
    ) = (
        anaphora
    ) = (
        uncovered_mention
    ) = (
        speakerless
    ) = (
        verbless
    ) = genderless = referenceless = evident_references = plural_speakers = quotes = 0

    for quote_object in quote_objects:
        speaker_index = quote_object["speaker_index"]
        speaker = quote_object["speaker"]
        reference = quote_object["reference"]
        speaker_gender = quote_object["speaker_gender"]
        verb = quote_object["verb"]
        if not verb:
            verbless += 1
        if speaker_gender == "unknown":
            genderless += 1
        if reference:
            pass
        else:
            referenceless += 1

        if speaker_index:
            start, end = literal_eval(speaker_index)
            speaker_span = doc.char_span(start, end, alignment_mode="expand")
            speaker_root = speaker_span.root
            is_mention = False
            if RULES_ANALYZER.is_independent_noun(speaker_root):
                is_mention = True
                independent_nouns += 1
                if speaker_root.pos_ == "PROPN":
                    proper_n += 1
                else:
                    substantives += 1
            elif RULES_ANALYZER.is_potential_anaphor(speaker_root):
                is_mention = True
                anaphora += 1
            else:
                infos_root = [
                    speaker_root,
                    speaker_root.pos_,
                    speaker_root.dep_,
                    speaker_root.morph,
                ]
                print(
                    "NOT COVERED :",
                    speaker,
                    (start, end, speaker_span.start, speaker_span.end),
                    infos_root,
                )
                uncovered_mention += 1
            if RULES_ANALYZER.is_independent_noun(
                speaker_root
            ) and RULES_ANALYZER.is_potential_anaphor(speaker_root):
                print(
                    "DOUBLE",
                    speaker,
                    speaker_root,
                    speaker_root.pos_,
                    speaker_root.dep_,
                    speaker_root.morph,
                    sep="|",
                )

            if reference and lev.distance(speaker.lower(), reference.lower()) <= 2:
                evident_references += 1

            masc, fem, sing, plur = RULES_ANALYZER.get_gender_number_info(speaker_root)
            siblings = RULES_ANALYZER.get_dependent_siblings(speaker_root)
            if is_mention and (
                (plur and not sing) or (siblings and siblings[-1].idx <= end)
            ):
                # print("PLURAL :", speaker)
                plural_speakers += 1
        else:
            speakerless += 1
        quotes += 1
    data = (
        independent_nouns,
        proper_n,
        substantives,
        anaphora,
        uncovered_mention,
        speakerless,
        verbless,
        genderless,
        referenceless,
        evident_references,
        plural_speakers,
        quotes,
    )
    return data


NLP = spacy.load("fr_core_news_lg")
RULES_ANALYZER = RulesAnalyzerFactory.get_rules_analyzer(NLP)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Computes statistics about the quotes and their speakers and write them to csv")
    parser.add_argument("--text_dir", type=str, help="Path to the texts directory")
    parser.add_argument("--target_dir", type=str, help="Path to the target directory")
    parser.add_argument("--output_file", type=str, default="", help="Path to the output csv file")
    args = parser.parse_args()
    TEXT_DIR = args.text_dir
    TARGET_DIR = args.target_dir
    OUTPUT_FILE = args.output_file
    compute_statistics(TEXT_DIR, TARGET_DIR, OUTPUT_FILE)
