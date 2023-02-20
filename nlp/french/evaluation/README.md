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
This section assumes that the virtual environment for French NLP has already been set up. The French NLP pipeline uses a third party coreference resolution library named [coreferee](https://github.com/explosion/coreferee), which requires the use of Python 3.9. It is assumed that Python 3.9 exists on the system on which the French NLP code runs.

Make sure that `gcc`, `build-essential` and `python3.9-devel` (on Red Hat/CentOS), or `python3.9-dev` (on ubuntu) are installed on the system. Also, install `python3.9-venv` for managing virtual environments, and ensure `wheel` is installed prior to installing the dependencies (as shown below)


If not done already, install a virtual environment using the `requirements.txt` from the `nlp/french` directory in this repo.

```sh
cd /path_to_code/GenderGapTracker/nlp/french
python3.9 -m venv GRIM-FR
source GRIM-FR/bin/activate
python3.9 -m pip install -U pip wheel  # Upgrade pip and install the wheel package first
python3.9 -m pip install -r requirements.txt
```
```

This installs the correct versions of spaCy, its associated language model, as well as coreferee (for coreference resolution).
