import argparse
import os
import json
import pandas as pd


def clean_id(id_str):
    return id_str.lower().replace('objectid', '').replace('(', '').replace(')', '').strip()


# Calculate precision and recall for each two string arrays
def get_array_match_as_set(array_true, array_pred):

    array_true_processed = [x.lower().strip() for x in array_true]
    array_pred_processed = [x.lower().strip() for x in array_pred]

    set_a = set(array_true_processed)
    set_b = set(array_pred_processed)

    n_a = len(array_true_processed)
    n_b = len(array_pred_processed)
    intersect = set_a.intersection(set_b)
    union = set_a.union(set_b)
    if len(union) == 0:
        score = 1
    else:
        score = len(intersect) / len(union)

    true_positive = len(intersect)
    false_positive = len(array_pred_processed) - true_positive
    false_negative = len(array_true_processed) - true_positive
    if (true_positive + false_positive) == 0:
        precision = 0
    else:
        precision = true_positive / (true_positive + false_positive)

    if (true_positive + false_negative) == 0:
        recall = 0
    else:
        recall = true_positive / (true_positive + false_negative)

    if (precision + recall) == 0:
        f1_score = 0
    else:
        f1_score = 2 * precision * recall / (precision + recall)
    res_obj = {
        'n_a': n_a,
        'n_b': n_b,
        'score': round(score, 2),
        'a': array_true_processed,
        'b': array_pred_processed,
        'intersect': list(intersect),
        'union': list(union),
        'true_positive': true_positive,
        'false_positive': false_positive,
        'false_negative': false_negative,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'remaining_a': list(set_a.difference(set_b)),
        'remaining_b': list(set_b.difference(set_a))

    }
    return res_obj


def get_list_from_string(lst_in_str):
    if lst_in_str is None:
        return []
    try:
        lst = eval(lst_in_str)
        return lst
    except:
        # print('!!! ', lst_in_str)
        return []


def compare_csv_files(ra, rb):
    people_a = get_list_from_string(ra['people'])
    people_b = get_list_from_string(rb['people'])
    people_res = get_array_match_as_set(people_a, people_b)

    peopleFemale_a = get_list_from_string(ra['peopleFemale'])
    peopleFemale_b = get_list_from_string(rb['peopleFemale'])
    peopleFemale_res = get_array_match_as_set(peopleFemale_a, peopleFemale_b)

    peopleMale_a = get_list_from_string(ra['peopleMale'])
    peopleMale_b = get_list_from_string(rb['peopleMale'])
    peopleMale_res = get_array_match_as_set(peopleMale_a, peopleMale_b)

    authorsFemale_a = get_list_from_string(ra['authorsFemale'])
    authorsFemale_b = get_list_from_string(rb['authorsFemale'])
    authorsFemale_res = get_array_match_as_set(authorsFemale_a, authorsFemale_b)

    authorsMale_a = get_list_from_string(ra['authorsMale'])
    authorsMale_b = get_list_from_string(rb['authorsMale'])
    authorsMale_res = get_array_match_as_set(authorsMale_a, authorsMale_b)

    authorsUnknown_a = get_list_from_string(ra['authorsUnknown'])
    authorsUnknown_b = get_list_from_string(rb['authorsUnknown'])
    authorsUnknown_res = get_array_match_as_set(authorsUnknown_a, authorsUnknown_b)

    sourcesFemale_a = get_list_from_string(ra['sourcesFemale'])
    sourcesFemale_b = get_list_from_string(rb['sourcesFemale'])
    sourcesFemale_res = get_array_match_as_set(sourcesFemale_a, sourcesFemale_b)

    sourcesMale_a = get_list_from_string(ra['sourcesMale'])
    sourcesMale_b = get_list_from_string(rb['sourcesMale'])
    sourcesMale_res = get_array_match_as_set(sourcesMale_a, sourcesMale_b)

    res_obj = {
        'people': people_res,
        'peopleFemale': peopleFemale_res,
        'peopleMale': peopleMale_res,
        'authorsFemale': authorsFemale_res,
        'authorsMale': authorsMale_res,
        'authorsUnknown': authorsUnknown_res,
        'sourcesFemale': sourcesFemale_res,
        'sourcesMale': sourcesMale_res,
        'sourcesFemaleCount_a': len(ra['sourcesFemale']),
        'sourcesMaleCount_a': len(ra['sourcesMale']),
        'sourcesUnknownCount_a': len(ra['sourcesUnknown']),
        'sourcesFemaleCount_b': len(rb['sourcesFemale']),
        'sourcesMaleCount_b': len(rb['sourcesMale']),
        'sourcesUnknownCount_b': len(rb['sourcesUnknown']),
        'peopleFemaleCount_a': len(ra['peopleFemale']),
        'peopleMaleCount_a': len(ra['peopleMale']),
        'peopleUnknownCount_a': len(ra['peopleUnknown']),
        'peopleFemaleCount_b': len(rb['peopleFemale']),
        'peopleMaleCount_b': len(rb['peopleMale']),
        'peopleUnknownCount_b': len(rb['peopleUnknown'])
    }
    return res_obj


def evaluate(csv_db_data):
    ###---- Evaluate named entities
    important_cols = [
        '_id', 'authorsFemale', 'authorsMale', 'authorsUnknown', 'people', 'peopleFemale',
        'peopleMale', 'peopleUnknown', 'sourcesFemale', 'sourcesMale', 'sourcesUnknown'
    ]

    csv_a = pd.read_excel(os.path.join('./', 'AnnotationTable_byArticle_withReplacementArticles.xlsx'), 0)[important_cols]
    csv_b = pd.read_csv(os.path.join('./', csv_db_data), index_col=None)[important_cols]
    csv_a['_id'] = csv_a.apply(lambda row: clean_id(row['_id']), axis=1)
    csv_b['_id'] = csv_b.apply(lambda row: clean_id(row['_id']), axis=1)

    result_list = []
    for r in csv_a['_id']:
        a_row = csv_a[csv_a['_id'] == r]
        b_row = csv_b[csv_b['_id'] == r]
        if len(a_row) == 1 and len(b_row) == 1:
            # print('Evaluating ', r)
            res = compare_csv_files(a_row.iloc[0], b_row.iloc[0])
            res['id'] = r
            result_list.append(res)
            res = json.dumps(res, indent=4, sort_keys=True)
            output_file = open(os.path.join(results_dir, r + '_entities.json'), 'w+')
            output_file.write(res)
            output_file.close()
        else:
            print('Skipping ', r)

    result_df = pd.json_normalize(result_list)
    result_df = result_df.sort_values(by=['id'])

    result_df.to_csv(os.path.join(results_dir, 'entities_result_detailed.csv'), index=False)

    summary_columns = [
        'id',
        'sourcesFemale.true_positive', 'sourcesFemale.false_positive', 'sourcesFemale.false_negative',
        'sourcesMale.true_positive', 'sourcesMale.false_positive', 'sourcesMale.false_negative',
        'sourcesFemaleCount_a', 'sourcesMaleCount_a', 'sourcesUnknownCount_a',
        'sourcesFemaleCount_b', 'sourcesMaleCount_b', 'sourcesUnknownCount_b',
        'peopleFemale.true_positive', 'peopleFemale.false_positive', 'peopleFemale.false_negative',
        'peopleMale.true_positive', 'peopleMale.false_positive', 'peopleMale.false_negative',
        'peopleFemaleCount_a', 'peopleMaleCount_a', 'peopleUnknownCount_a',
        'peopleFemaleCount_b', 'peopleMaleCount_b', 'peopleUnknownCount_b',
        'authorsFemale.n_a', 'authorsMale.n_a', 'authorsUnknown.n_a',
        'authorsFemale.n_b', 'authorsMale.n_b', 'authorsUnknown.n_b']

    result_df_summary = result_df[summary_columns]
    result_df_summary.to_csv(os.path.join(results_dir, 'entities_result_summary.csv'), index=False)
    print('\nNER Results:\n------------')
    print_ner_results(result_df_summary)
    print('\nGender Results:\n------------')
    print_gender_results(result_df_summary)


def print_gender_results(result_df):
    people_total_count = sum(
        result_df['peopleFemaleCount_b'] + result_df['peopleMaleCount_b'] + result_df['peopleUnknownCount_b']
    )
    sources_total_count = sum(
        result_df['sourcesFemaleCount_b'] + result_df['sourcesMaleCount_b'] + result_df['sourcesUnknownCount_b']
    )
    people_female_ratio = sum(result_df['peopleFemaleCount_b']) / people_total_count
    people_male_ratio = sum(result_df['peopleMaleCount_b']) / people_total_count
    people_unknown_ratio = sum(result_df['peopleUnknownCount_b']) / people_total_count
    sources_female_ratio = sum(result_df['sourcesFemaleCount_b']) / sources_total_count
    sources_male_ratio = sum(result_df['sourcesMaleCount_b']) / sources_total_count
    sources_unknown_ratio = sum(result_df['sourcesUnknownCount_b']) / sources_total_count
    # Print results
    print(f"People female ratio: {100*people_female_ratio:.1f}%")
    print(f"People male ratio: {100*people_male_ratio:.1f}%")
    print(f"People unknown ratio: {100*people_unknown_ratio:.1f}%")
    print('------------')
    print(f"Sources female ratio: {100*sources_female_ratio:.1f}%")
    print(f"Sources male ratio: {100*sources_male_ratio:.1f}%")
    print(f"Sources unknown ratio: {100*sources_unknown_ratio:.1f}%")


def get_precision_or_recall(df, true_colname, false_colname):
    precision_or_recall = sum(df[true_colname]) / (sum(df[true_colname]) + sum(df[false_colname]))
    return precision_or_recall


def get_f1_score(precision, recall):
    return 2 * precision * recall / (precision + recall)


def print_ner_results(df):
    people_female_precision = get_precision_or_recall(df, 'peopleFemale.true_positive', 'peopleFemale.false_positive')
    people_female_recall = get_precision_or_recall(df, 'peopleFemale.true_positive', 'peopleFemale.false_negative')
    people_female_f1_score = get_f1_score(people_female_precision, people_female_recall)
    people_male_precision = get_precision_or_recall(df, 'peopleMale.true_positive', 'peopleMale.false_positive')
    people_male_recall = get_precision_or_recall(df, 'peopleMale.true_positive', 'peopleMale.false_negative')
    people_male_f1_score = get_f1_score(people_male_precision, people_male_recall)

    print(f"People Female, Precision: {100*people_female_precision:.1f}%")
    print(f"People Female, Recall: {100*people_female_recall:.1f}%")
    print(f"People Female, F1 Score: {100*people_female_f1_score:.1f}%")
    print("------------")
    print(f"People Male, Precision: {100*people_male_precision:.1f}%")
    print(f"People Male, Recall: {100*people_male_recall:.1f}%")
    print(f"People Male, F1 Score: {100*people_male_f1_score:.1f}%")
    print("------------")

    sources_female_precision = get_precision_or_recall(df, 'sourcesFemale.true_positive', 'sourcesFemale.false_positive')
    sources_female_recall = get_precision_or_recall(df, 'sourcesFemale.true_positive', 'sourcesFemale.false_negative')
    sources_female_f1_score = get_f1_score(sources_female_precision, sources_female_recall)
    sources_male_precision = get_precision_or_recall(df, 'sourcesMale.true_positive', 'sourcesMale.false_positive')
    sources_male_recall = get_precision_or_recall(df, 'sourcesMale.true_positive', 'sourcesMale.false_negative')
    sources_male_f1_score = get_f1_score(sources_male_precision, sources_male_recall)

    print(f"Sources Female, Precision: {100*sources_female_precision:.1f}%")
    print(f"Sources Female, Recall: {100*sources_female_recall:.1f}%")
    print(f"Sources Female, F1 Score: {100*sources_female_f1_score:.1f}%")
    print("------------")
    print(f"Sources Male, Precision: {100*sources_male_precision:.1f}%")
    print(f"Sources Male, Recall: {100*sources_male_recall:.1f}%")
    print(f"Sources Male, F1 Score: {100*sources_male_f1_score:.1f}%")
    print("------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--true", "-a", type=str, default="humanAnnotatedQuotes", help="Directory containing human-annotated Data")
    parser.add_argument("--pred", "-b", type=str, default="V4.0", help="Directory containing new script-generated Data")
    parser.add_argument("--csv", "-c", type=str, default="db_ner_v4.0.csv",
                        help="CSV file output from MongoDB containing NER fields")
    args = parser.parse_args()

    QUOTE_MATCH_THRESHOLDS = [0.3, 0.8]

    source_A = args.true
    source_B = args.pred
    csv_db_data = args.csv

    base_dir = "./"

    folder_A = os.path.join(base_dir, source_A)
    folder_B = os.path.join(base_dir, source_B)
    files_A = [x for x in os.listdir(folder_A) if x.endswith('json')]
    files_B = [x for x in os.listdir(folder_B) if x.endswith('json')]

    results_dir = os.path.join(base_dir, 'results', source_A + "-" + source_B)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    evaluate(csv_db_data)
