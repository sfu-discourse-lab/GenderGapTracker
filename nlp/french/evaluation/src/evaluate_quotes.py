import argparse
import os
import json
import pandas as pd


"""
Functions used in the main evaluate.py script
"""
##------- Functions to evaluate quote extraction
def get_index(index_string):
    try:
        indices = index_string.replace("(", "").replace(")", "").strip().split(",")
        indices = [int(x.strip()) for x in indices if len(x.strip()) > 0]
        if len(indices) != 2:
            return None
        return indices
    except:
        return None


def calc_index_match_score(indx1, indx2):
    if indx1 is None or indx2 is None:
        return 0
    else:
        indx1_set = set(range(indx1[0], indx1[1]))
        indx2_set = set(range(indx2[0], indx2[1]))
        # score = len(indx1_set.intersection(indx2_set)) / len(indx1_set.union(indx2_set))
        # We changed the score definition to make it assymetric and consider first item as reference.
        if (len(indx1_set) == 0) or (len(indx2_set) == 0):
            score = 0
        else:
            score = len(indx1_set.intersection(indx2_set)) / len(indx1_set)
        return score


def compare_quotes(q1, q2):

    # Compute Match Score
    q1_index = get_index(q1["quote_index"])
    q2_index = get_index(q2["quote_index"])
    quote_match_score = calc_index_match_score(q1_index, q2_index)

    # Compare speakers
    s1_index = get_index(q1["speaker_index"])
    s2_index = get_index(q2["speaker_index"])
    speaker_1 = q1["speaker"]
    # speaker_2 = q2['speaker']
    speaker_match_score = calc_index_match_score(s1_index, s2_index)

    # Compare verbs
    v1 = q1["verb"].lower().strip()
    v2 = q2["verb"].lower().strip()
    verb_match = v1 == v2

    # score > 0 means if the span of speaker and the annotated speaker has overlap.
    # because we have a bigger span including speakers title in the extracted speaker
    speaker_match_cond_1 = speaker_match_score > 0
    speaker_match_cond_2 = (
        "is_floating_quote" in q2.keys()
        and q2["is_floating_quote"]
        and len(speaker_1.strip()) == 0
    )
    speaker_match = speaker_match_cond_1 or speaker_match_cond_2
    match_score = quote_match_score

    res_obj = {
        "q_a": q1,
        "q_b": q2,
        "quote_match_score": round(quote_match_score, 2),
        "speaker_match": speaker_match,
        "verb_match": verb_match,
        "match_score": round(match_score, 2),
    }

    return match_score, res_obj


def find_best_match_quote(quote, quote_list, match_threshold):
    remaining_quotes = []
    best_quote = None
    best_stats = None
    max_score = 0

    # Find best match
    for q in quote_list:
        score, stats = compare_quotes(quote, q)
        if score > match_threshold and score > max_score:
            max_score = score
            best_quote = q
            best_stats = stats

    # Find remaining quotes
    for q in quote_list:
        if q != best_quote:
            remaining_quotes.append(q)

    return best_quote, best_stats, remaining_quotes


def round_list(lst, digits):
    return [round(x, digits) for x in lst]


def compare_res(quotes_a, quotes_b, min_threshold):
    #  number of quotes
    n_quotes_a = len(quotes_a)
    n_quotes_b = len(quotes_b)
    n_speaker_match = 0
    n_verb_match = 0
    true_positive = 0
    false_positive = 0
    false_negative = 0
    stats = []
    remaining_quotes_a = []
    remaining_quotes_b = quotes_b

    for q_a in quotes_a:
        best_quote, best_stats, remaining_quotes_b = find_best_match_quote(
            q_a, remaining_quotes_b, min_threshold
        )
        if best_quote is not None:
            true_positive += 1
            if best_stats["speaker_match"]:
                n_speaker_match += 1
            if best_stats["verb_match"]:
                n_verb_match += 1
            stats.append(best_stats)
        else:
            false_negative += 1
            remaining_quotes_a.append(q_a)

    false_positive = len(remaining_quotes_b)

    res_obj = {
        "n_quotes_a": n_quotes_a,
        "n_quotes_b": n_quotes_b,
        "n_speaker_match": n_speaker_match,
        "n_verb_match": n_verb_match,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "stats": stats,
        "remaining_a": remaining_quotes_a,
        "remaining_b": remaining_quotes_b,
    }

    return res_obj


def evaluate_quotes(folder_A, folder_B, quote_match_thresholds=[0.3, 0.8]):
    files_A = [x for x in os.listdir(folder_A) if x.endswith("json")]

    all_results = []
    result_dfs = []
    for min_threshold in quote_match_thresholds:
        all_docs_comp_res = []
        for f_a in files_A:
            try:
                doc_id = f_a[0:-5]
                file_a = open(os.path.join(folder_A, f_a), "r", encoding="utf-8")
                json_a = json.loads("\n".join(file_a.readlines()))
                json_a = (
                    json_a["quotesUpdated"] if "quotesUpdated" in json_a else json_a
                )
                file_a.close()

                file_b = open(os.path.join(folder_B, f_a), "r", encoding="utf-8")
                json_b = json.loads("\n".join(file_b.readlines()))
                json_b = (
                    json_b["quotesUpdated"] if "quotesUpdated" in json_b else json_b
                )
                file_b.close()

                comp_res = compare_res(json_a, json_b, min_threshold)
                comp_res["id"] = f_a.replace(".json", "")

                all_docs_comp_res.append(comp_res)
            except FileNotFoundError:
                print(f"[{f_a} not found]\n")
                pass
            except Exception as e:
                print(doc_id, " Error!", e, "\n", "-" * 20)

        subdata = [
            [
                doc_comp_res["true_positive"],
                doc_comp_res["false_negative"],
                doc_comp_res["false_positive"],
                doc_comp_res["n_speaker_match"],
                doc_comp_res["n_verb_match"],
            ]
            for doc_comp_res in all_docs_comp_res
        ]

        all_results.append(subdata)
        df = pd.json_normalize(all_docs_comp_res)
        df = df.sort_values(by=["id"])
        df = df[
            [
                "id",
                "true_positive",
                "false_negative",
                "false_positive",
                "n_quotes_a",
                "n_quotes_b",
                "n_speaker_match",
                "n_verb_match",
                "remaining_a",
                "remaining_b",
                "stats",
            ]
        ]
        result_dfs.append(df)
    return all_results, result_dfs


def print_results(df, min_threshold):
    """Print the validation results to sys.stdout"""
    # Precision, recall and F1-scores
    precision = sum(df["true_positive"]) / (
        sum(df["true_positive"]) + sum(df["false_positive"])
    )
    recall = sum(df["true_positive"]) / (
        sum(df["true_positive"]) + sum(df["false_negative"])
    )
    f1_score = 2 * precision * recall / (precision + recall)
    speaker_match = sum(df["n_speaker_match"]) / sum(df["true_positive"])
    verb_match = sum(df["n_verb_match"]) / sum(df["true_positive"])

    print("\n------------------------")
    print(f"Quote Extraction - {min_threshold}, Precision: {100*precision:.3f}%")
    print(f"Quote Extraction - {min_threshold}, Recall: {100*recall:.3f}%")
    print(f"Quote Extraction - {min_threshold}, F1 Score: {100*f1_score:.3f}%")
    print(f"Speaker Match - {min_threshold}, Accuracy: {100*speaker_match:.3f}%")
    print(f"Verb Match - {min_threshold}, Accuracy: {100*verb_match:.3f}%")
    print("------------------------\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--true", "-a", type=str, default="eval/humanAnnotations", help="Directory containing human-annotated Data")
    parser.add_argument("--pred", "-b", type=str, default="eval/systemAnnotations/V6.0/quotes/extracted_quotes",
                        help="Directory containing new script-generated Data")
    args = parser.parse_args()
    source_A = args.true
    source_B = args.pred

    quote_match_thresholds = [0.3, 0.8]

    # Run quote evaluation
    _, final_dfs = evaluate_quotes(source_A, source_B, quote_match_thresholds)

    for i, df in enumerate(final_dfs):
        print_results(df, quote_match_thresholds[i])
