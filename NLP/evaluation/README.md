# GGT Evaluation
This folder contains methodology and code for producing the evaluation results as described in the paper.

For consistent and reproducible results, make sure any evaluation run locally uses the **same Python environment that is running in production**.

## Download Data
The raw text data (containing news article text) as well as the human-annotated data is stored on Vault: `GRIM/Manual Annotation/V4.0_Evaluation`.
Download the directories `humanAnnotatedQuotes` and `rawtext` from Vault and place them in their respective paths as per the structure below.

```sh
├── .
|   ├── src
|   |   ├── quote_extractor_v4.0.py
|   |   ├── rawtext
|   |   ├── eval
|   |   |   └── humanAnnotatedQuotes
|   |   └── evaluate_quotes.py
|   |   └── evaluate_ner.py
```

## Set Up Environment
Install Python 3.6+ and follow the below instructions to set up and activate a virtual environment.

```sh
python3 -m venv GRIM-3
source GRIM-3/bin/activate
```
For further development, simply activate the existing environment each time.
```sh
source GRIM-3/bin/activate
```

#### Install dependencies
```sh
pip3 install -r requirements.txt
```

#### `spaCy` language model
**First, make sure that the spaCy version shown in `requirements.txt` is the same as the one running in production**.

Manually download spaCy's large English language model for the quote extraction pipeline - this is a one-time step for this specific virtual environment.
```sh
python3 -m spacy download en_core_web_lg
```
