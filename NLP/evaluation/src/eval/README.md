# Evaluation scripts

## Evaluate quotes
The evaluation script `evaluate_quotes.py` compares each JSON file in the `humanAnnotatedQuotes` directory with its corresponding namesake in the script-generated quotes directory. It takes in two input arguments are provided as follows.

#### Script arguments
```sh
python3 evaluate_quotes.py --help
usage: evaluate_quotes.py [-h] [--true TRUE] [--pred PRED]

optional arguments:
  -h, --help            show this help message and exit
  --true TRUE, -a TRUE  Directory containing human-annotated Data
  --pred PRED, -b PRED  Directory containing new script-generated Data
```

#### Example run command
```sh
python3 evaluate_quotes.py -a humanAnnotatedQuotes -b V5.1
```
### Outputs from quote evaluation
Multiple files are output as follows.

#### `sys.stdout`
Evaluation metrics for quotes, speakers and verbs are printed to the console as shown below.
```sh
Quote Extraction - 0.3, Precision: 84.6%
Quote Extraction - 0.3, Recall: 82.7%
Quote Extraction - 0.3, F1 Score: 83.7%
Speaker Match - 0.3, Accuracy: 86.0%
Verb Match - 0.3, Accuracy: 91.8%
------------------------
Quote Extraction - 0.8, Precision: 77.0%
Quote Extraction - 0.8, Recall: 75.2%
Quote Extraction - 0.8, F1 Score: 76.1%
Speaker Match - 0.8, Accuracy: 86.9%
Verb Match - 0.8, Accuracy: 93.1%
------------------------
```

#### CSV and JSON files
To persist the evaluation results over the long term, CSV and JSON files containing the raw numbers are output to the `./results/humanAnnotatedQuotes-V5.1` directory. These can then be used to populate the **`Comparison Result V4.x.xlsx`** Excel spreadsheet.

Each quote JSON file has the nomenclature `<doc_id>_0.3.json` and `<doc_id>_0.8.json` to indicate the two evaluation thresholds. The CSV files have a similar nomenclature: `quote_results_0.3.csv` and `quote_results_0.8.csv`. 


## Evaluate NER and gender
Named Entities and gender recognition are evaluated using the `evaluate_ner_and_gender.py` script - as mentioned before, evaluating named entities and gender are done in one step because the entities themselves are organized by gender. The script `evaluate_ner_and_gender.py`  compares the named entities extracted by the `entity_gender_annotator` (running on the database) vs. the human-annotated named entities labelled in the file `AnnotationTable_byArticle_withReplacementArticles.xlsx`.

#### Script Arguments
```sh
python3 evaluate_ner_and_gender.py --help
usage: evaluate_ner_and_gender.py [-h] [--true TRUE] [--pred PRED] [--csv CSV]

optional arguments:
  -h, --help            show this help message and exit
  --true TRUE, -a TRUE  Directory containing human-annotated Data
  --pred PRED, -b PRED  Directory containing new script-generated Data
  --csv CSV, -c CSV     CSV file output from MongoDB containing NER fields
```
In this case, the `--true` amd `--pred` arguments are the same as the one used by `quote_extractor.py`, but there is a third argument to indicate the user-specified CSV file with the named entity columns (obtained by running `entity_gender_annotator.py` on the database). The default value for this `--csv` argument is the `db_ner_v5.1.csv` file that was generated in the previous step.

#### Example run command
```sh
python3 evaluate_ner_and_gender.py -a humanAnnotatedQuotes -b V5.1 -c db_ner_v5.1.csv
```

### Outputs from named entity and gender evaluation

#### `sys.stdout`
Evaluation metrics for people and sources based on gender are printed to the console as shown below.

```sh
NER Results:
------------
People Female, Precision: 69.3%
People Female, Recall: 72.7%
People Female, F1 Score: 70.9%
------------
People Male, Precision: 75.1%
People Male, Recall: 89.2%
People Male, F1 Score: 81.6%
------------
Sources Female, Precision: 90.9%
Sources Female, Recall: 61.0%
Sources Female, F1 Score: 73.0%
------------
Sources Male, Precision: 85.8%
Sources Male, Recall: 74.8%
Sources Male, F1 Score: 79.9%
------------

Gender Results:
------------
People female ratio: 24.5%
People male ratio: 73.8%
People unknown ratio: 1.7%
------------
Sources female ratio: 23.5%
Sources male ratio: 72.2%
Sources unknown ratio: 4.2%

```

#### CSV and JSON files
Just as with the quote evaluation, CSV and JSON files containing the raw numbers are output to the `./results/humanAnnotatedQuotes-V5.1` directory. These can then be used to populate the `Comparison Result V5.x.xlsx` Excel spreadsheet.

Each entity JSON file has the nomenclature `<doc_id>_entities.json`. The CSV files have the following nomenclature: `entities_result_detailed.csv` and `entities_result_summary.csv`.

## Long-term Storage
It is recommended to use the CSV outputs from both scripts to keep the master spreadsheet **`Comparison Result VX.X.xlsx`** up to date on Vault. Keeping each GGT version's evaluation results in one sheet allows us to track the progress of the NLP pipeline across different versions.
