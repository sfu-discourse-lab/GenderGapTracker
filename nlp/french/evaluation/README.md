# French GGT Evaluation
This folder contains methodology and code for evaluating the results of the French pipeline.

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
Install Python 3.9+ and follow the below instructions to set up and activate a virtual environment.

```sh
python3 -m venv GRIM-FR
source GRIM-3/bin/activate
```
For further development, simply activate the existing environment each time.
```sh
source GRIM-FR/bin/activate
```

#### Install dependencies
**First, make sure that the spaCy version shown in `requirements-py39.txt` is the same as the one running in production**

```sh
$ cd WomenInMedia/nlp/french
$ python3 -m pip install -r requirements-py39.txt
```

This installs the correct versions of spaCy, its associated language model, as well as coreferee (for coreference resolution).
