# GGT Evaluation
This folder contains methodology and code for producing the evaluation results as described in the paper.

For consistent and reproducible results, make sure any evaluation run locally uses the **same Python environment that is running in production**.

## Download Data
The raw data for evaluation (containing news article text) as well as our human-annotated data can be made available for reproducibility and research purposes, upon signing a license agreement.
First, download the directories `humanAnnotatedQuotes` and `rawtext.zip` from our cloud storage and place them in their respective paths as per the structure shown below.

```sh
├── .
|   ├── src
|   |   ├── quote_extractor_latest.py
|   |   ├── quote_verb_list.txt
|   |   ├── rawtext.zip
|   |   ├── eval
|   |   |   └── humanAnnotatedQuotes
|   |   └── evaluate_quotes.py
|   |   └── evaluate_ner.py
```

## Set Up Environment
Install Python 3.6+ and follow the below instructions to set up and activate a virtual environment.

```sh
python3 -m venv venv
source venv/bin/activate
```
For further development, simply activate the existing environment each time.
```sh
source venv/bin/activate
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
