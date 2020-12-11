# Evaluation scripts

## Evaluate quotes
The evaluation script `evaluate_quotes.py` compares each JSON file in the `humanAnnotatedQuotes` directory with its corresponding namesake in the script-generated quotes directory (`./V5.3` in this case). It takes in two input arguments as follows.

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
python3 evaluate_quotes.py --true humanAnnotatedQuotes --pred V5.3
```
This outputs the quotes to a directory named after the version of the code.

**NOTE**: Make sure to use the correct version for the script and name the directory containing quotes accordingly, otherwise it might lead to confusion downstream. The next step uses the directory name from this step, which is why it is important to keep track of the versions we are evaluating.

### Outputs from quote evaluation
Multiple files are output from the quote evaluation script as follows.

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
To persist the evaluation results, CSV and JSON files containing the raw numbers are output to the `./results/humanAnnotatedQuotes-V5.3` directory. These were used to populate the **`Comparison Result V5.3.xlsx`** spreadsheet present in this directory.

Each quote JSON file has the nomenclature `<doc_id>_0.3.json` and `<doc_id>_0.8.json` to indicate the two evaluation thresholds we use in the paper. The CSV files have a similar nomenclature: `quote_results_0.3.csv` and `quote_results_0.8.csv`.


## Evaluate NER and gender
Named Entities and gender prediction are evaluated using the `evaluate_ner_and_gender.py` script -- note that evaluating the named entities and gender are done all at once (and not separately) because the entities themselves are organized by gender. The `evaluate_ner_and_gender.py` script compares the named entities extracted by the running our entity gender annotator vs. the human-annotated named entities in the file `AnnotationTable_byArticle_withReplacementArticles.xlsx`.

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
The`--true` amd `--pred` arguments are the similar to those seen in the quote evaluation script. The third argument, `--csv`, is used to specify the name of the CSV file with the named entity results (obtained by running `entity_gender_annotator.py` on the database). The default value for this `--csv` argument is the `db_ner_v5.3.csv` file present in this directory, obtained from our V5.3 evaluation.

#### Example run command
```sh
python3 evaluate_ner_and_gender.py --true humanAnnotatedQuotes --pred V5.3 --csv db_ner_v5.3.csv
```

### Outputs from named entity and gender evaluation

#### `sys.stdout`
Evaluation metrics for people and sources based on gender are printed to the console as shown below.

```sh
NER Results:
------------
People Female, Precision: 72.4%
People Female, Recall: 77.6%
People Female, F1 Score: 74.9%
------------
People Male, Precision: 77.4%
People Male, Recall: 92.1%
People Male, F1 Score: 84.1%
------------
Sources Female, Precision: 94.6%
Sources Female, Recall: 64.6%
Sources Female, F1 Score: 76.8%
------------
Sources Male, Precision: 87.7%
Sources Male, Recall: 76.5%
Sources Male, F1 Score: 81.7%
------------

Gender Results:
------------
People female ratio: 24.8%
People male ratio: 73.5%
People unknown ratio: 1.6%
------------
Sources female ratio: 23.8%
Sources male ratio: 72.0%
Sources unknown ratio: 4.2%

```

#### CSV and JSON files
Just as with the quote evaluation, CSV and JSON files containing the raw numbers are output to the `./results/humanAnnotatedQuotes-V5.3` directory. These were then used to populate the `Comparison Result V5.3.xlsx` spreadsheet present in this directory.

Each entity JSON file has the nomenclature `<doc_id>_entities.json`. The CSV files have the following nomenclature: `entities_result_detailed.csv` and `entities_result_summary.csv`.

## Evaluation summary sheet
The master spreadsheet **`Comparison Result V5.3.xlsx`** contains the results of our latest evaluation stage, V5.3, as well as a history of the improvements made across the various versions of the GGT software.
