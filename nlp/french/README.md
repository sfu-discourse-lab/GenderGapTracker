# French NLP pipeline
## Set up environment
The French NLP pipeline uses a third party coreference resolution library named [coreferee](https://github.com/explosion/coreferee), which requires the use of Python 3.9. It is assumed that Python 3.9 exists on the system on which the French NLP code runs.

Make sure that `gcc`, `build-essential` and `python3.9-devel` (on Red Hat/CentOS), or `python3.9-dev` (on ubuntu) are installed on the system. Also, install `python3.9-venv` for managing virtual environments, and ensure `wheel` is installed prior to installing the dependencies (as shown below)

```sh
python3.9 - venv GRIM-FR
```

Activate the environment and install the dependencies:

```
source GRIM-FR/bin/activate
python3.9 -m pip install -U pip wheel  # Upgrade pip and install the wheel package first
python3.9 -m pip install -r requirements.txt
```
## Run gender recognition service
This script starts a Flask server that provides routes for other modules to access the gender recognition service. All parameters for the gender API services are in the file `config.py`. For testing this code locally, run this script with the default parameters:

```sh
cd ../english
python3.9 gender_recognition.py
```

## Quote extractor
Extract `quotes` from the database or from local files. Save the output locally, or update the database directly.

### Default mode
By default, the quote extractor only works on articles that weren't processed earlier (i.e., new articles that are freshly scraped with `lastModifier = mediaCollectors`).

```sh
python3.9 quote_extractor.py --db mediaTracker --readcol media --limit 0
```
`--limit 0` (which is the default setting) means no limitation, and the script runs on all documents in the database. 

### Force update
To force-update the results and overwrite existing data for all articles, use the `--force_update` argument.
```sh
python3.9 quote_extractor.py --db mediaTracker --readcol media --force_update  --limit 10
```
`--limit 10` means that the script will process just 10 documents, which is useful during testing.

### Specify time period
We can easily limit the quote extraction process to only articles from a specified time period.

```sh
python3.9 quote_extractor.py --db mediaTracker --readcol media --force_update --begin_date 2021-12-01 --end_date 2021-12-31
```

For the full list of optional arguments, type the following:

```sh
python3.9 quote_extractor.py --help
```
## Quote highlighter
Take an input text, a set of corresponding predicted `quotes` (usually output data from the quote extractor) and optionally target `quotes` to compare against and output HTML files highlighting the quotes and speakers in the text.

Example commands:
```
python3.9 quote_highlighter.py --text-base=./input/ --prediction-base=./predictions/ --no-target --html-base=./html/
```
Optional arguments:
```
  -h, --help            show this help message and exit
  --text-base TEXT_BASE
                        Where the text which the quotes were extracted from is stored.
  --html-base HTML_BASE
                        Where to store the output HTML.
  --target-base TARGET_BASE
                        Where the (annotated) target quotes are stored.
  --prediction-base PREDICTION_BASE
                        Where the predicted quotes are stored.
  --no-target, -n       Don't highlight target quotes/speakers
```

---
## Entity gender annotator

Once the quotes have been extracted and written to the DB, we can then run the entity gender annotation script. This script utilizes the quotes (stored as a list) from each article, performs NER on them, and then merges the extracted named entities with the speakers of the quotes. In addition, we also perform quote merging to match the merged named entities to the speaker of a quote, wherever possible.

### Default mode
Just like the quote extractor, the entity gender annotator by default only works on articles that weren't processed earlier (i.e.,articles that were just processed by quote extractor, with `lastModifier = quote_extractor`).

```sh
python3.9 entity_gender_annotator.py --db mediaTracker --readcol media
```
Note that the gender recognition Flask server (from the previous step) must be started and running in production *before* the entity-gender annotator script can be run.

### Force update

To force-update the results and overwrite existing data for all articles, use the `--force_update` argument.

```sh
python3.9 entity_gender_annotator.py --db mediaTracker --readcol media --force_update
```

### Specify write collection
**It is strongly recommended** to use the `--writecol` argument when running the script on a large collection. This is so that even if the NLP operations take many days to run, the database statistics will not pick up partially completed results, and we can then run the `merge_collections.py` script to move the NLP results from the `newmedia` to the `media` collection.

```sh
python3.9 entity_gender_annotator.py --force_update --db mediaTracker --readcol media --writecol newmedia
```


### Specify time period
We can easily limit the quote extraction process to only articles from a specified time period.

```sh
python3.9 entity_gender_annotator.py --db mediaTracker --readcol media --force_update --begin_date 2020-01-01 --end_date 2020-01-31
```

For further help options, type the following:

```sh
python3.9 entity_gender_annotator.py --help
```

## Note on multiprocessing
As of spaCy 3.2.x and coreferee 1.3.1, multiprocessing is **not** supported (due to the inability of coreferee to share data between forked processes). As a result, we are unable to speed up the performance of the French entity gender annotator by dividing the computation across separate processes -- **this might change in a future version** when there are updates to the coreference algorithm within base spaCy.