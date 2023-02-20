# English GGT Evaluation
This folder contains methodology and code for evaluating the results of the English pipeline.

For consistent and reproducible results, make sure any evaluation run locally uses the **same Python environment that is running in production**.

## Download Data
The raw text data containing news article text, as well as the human-annotated data, is made available upon request (please contact Maite Taboada at [mtaboada@sfu.ca](mailto:mtaboada@sfu.ca)).
Obtain the directories named `humanAnnotations` and `rawtext` and place them in their respective paths as per the structure below.

```sh
├── .
|   ├── src
|   |   ├── rawtexts
|   |   ├── eval
|   |   |   └── humanAnnotations
|   |   └── evaluate.py
|   |   └── run_predictions.py
```

## Set Up Environment
This section assumes that the English NLP environment in `../nlp/english` has already been set up, as the dashboard has a dependency on the English NLP modules, specifically the entity gender annotator for NER and coreference resolution. **Just like in the English NLP pipeline**, the dash app requires Python 3.6 for legacy reasons -- it uses spaCy 2.1.3 and `neuralcoref` for performing coreference resolution, which, unfortunately, are not installable on higher versions of spaCy or Python.


If not done already, install a virtual environment using the `requirements.txt` from the `../nlp/english` directory in this repo.

```sh
cd /path_to_code/GenderGapTracker/nlp/english
python3 -m venv GRIM-EN   # python3 -> python3.6 for legacy reasons (neuralcoref)
source GRIM-EN/bin/activate
python3 -m pip install -U pip wheel  # Upgrade pip and install latest wheel package first
python3 -m pip install -r requirements.txt
```

#### `spaCy` language model
**First, make sure that the spaCy version shown in `requirements.txt` is the same as the one running in production**.

Manually download spaCy's large English language model for the quote extraction pipeline - this is a one-time step for this specific virtual environment.
```sh
python3 -m spacy download en_core_web_lg
```
